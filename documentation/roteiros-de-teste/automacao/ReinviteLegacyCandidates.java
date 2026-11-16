import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

import com.ccp.constants.CcpOtherConstants;
import com.ccp.decorators.CcpEmailDecorator;
import com.ccp.decorators.CcpFieldName;
import com.ccp.decorators.CcpJsonRepresentation;
import com.ccp.decorators.CcpStringDecorator;
import com.ccp.dependency.injection.CcpDependencyInjection;
import com.ccp.especifications.db.query.CcpQueryOptions;
import com.ccp.especifications.db.utils.entity.CcpEntity;
import com.ccp.hash.CcpHashAlgorithm;
import com.ccp.implementations.db.bulk.elasticsearch.CcpElasticSerchDbBulk;
import com.ccp.implementations.db.crud.elasticsearch.CcpElasticSearchCrud;
import com.ccp.implementations.db.query.elasticsearch.CcpElasticSearchQueryExecutor;
import com.ccp.implementations.db.utils.elasticsearch.CcpElasticSearchDbRequest;
import com.ccp.implementations.email.sendgrid.CcpSendGridEmailProvider;
import com.ccp.implementations.http.apache.mime.CcpApacheMimeHttp;
import com.ccp.implementations.json.gson.CcpGsonJsonHandler;
import com.ccp.implementations.password.mindrot.CcpMindrotPasswordHandler;
import com.ccp.local.testings.implementations.CcpLocalInstances;
import com.ccp.local.testings.implementations.cache.CcpLocalCacheInstances;
import com.jn.entities.JnEntityEmailSuppressed;
import com.jn.json.fields.validation.JnJsonCommonsFields;
import com.vis.business.recruiter.resumes.VisBusinessBuildLegacyCandidateTable;
import com.vis.business.recruiter.resumes.VisBusinessInviteLegacyCandidates;
import com.vis.business.recruiter.resumes.VisRecruiterResumesFields;
import com.vis.entities.VisEntityResume;

/**
 * Refaz (2026-11-15) o convite aos candidatos do índice legado {@code profissionais2}, só contra produção: os candidatos
 * vêm de um arquivo lido do Elasticsearch 7.4 do legado ({@code ler-candidatos-do-legado.py}); quem já tem currículo
 * ({@code vis_resume} e {@code vis_inactive_resume}), a supressão do SendGrid ({@code jn_email_suppressed}), o template,
 * os parâmetros de envio e o dicionário de skills são os de produção, pela {@code application_properties} que o
 * {@code reenviar-convite-aos-candidatos-do-legado.ps1} aponta para o túnel. Nada é gravado no Elasticsearch local.
 *
 * <p>Ficam de fora: endereço inválido, quem já tem currículo em produção, quem está suprimido em produção e quem já foi
 * reconvidado (o arquivo de controle). A tabela e o envio são os do convite original
 * ({@code VisBusinessBuildLegacyCandidateTable} e {@code VisBusinessInviteLegacyCandidates.sendTheInvitation}, este por
 * reflexão porque é de pacote): uma falha do provedor para tudo, e a próxima execução continua de onde parou.
 *
 * <p>Uso: {@code <arquivo dos candidatos> <endereço https do front> <arquivo de controle> [quantidade]}; quantidade 0 só
 * conta, sem enviar.
 */
public class ReinviteLegacyCandidates {

	public static void main(String[] args) throws Exception {
		if(args.length < 3 || false == args[1].startsWith("https://")) {
			System.out.println("Uso: <arquivo dos candidatos> <endereco https do front> <arquivo de controle> [quantidade]");
			System.exit(1);
		}
		String candidatesText = Files.readString(Path.of(args[0]), StandardCharsets.UTF_8);
		String frontendUrl = args[1];
		Path controlFile = Path.of(args[2]);
		int limit = args.length > 3 ? Integer.parseInt(args[3]) : Integer.MAX_VALUE;

		CcpDependencyInjection.loadAllDependencies(
				CcpGsonJsonHandler.INSTANCE,
				CcpSendGridEmailProvider.INSTANCE,
				CcpLocalInstances.instantMessenger,
				CcpLocalInstances.syncMensageriaListener,
				CcpLocalCacheInstances.mock,
				CcpMindrotPasswordHandler.INSTANCE,
				CcpElasticSerchDbBulk.INSTANCE,
				CcpApacheMimeHttp.INSTANCE,
				CcpElasticSearchDbRequest.INSTANCE,
				CcpElasticSearchCrud.INSTANCE,
				CcpElasticSearchQueryExecutor.INSTANCE
		);

		Files.createDirectories(controlFile.getParent());
		Set<String> alreadyReinvited = new HashSet<>();
		if(Files.exists(controlFile)) {
			alreadyReinvited.addAll(Files.readAllLines(controlFile, StandardCharsets.UTF_8));
		}
		Set<String> withResume = getEmailsWithResume();
		String resumeFormLink = frontendUrl + "/meus-dados/sobre-mim";

		List<CcpJsonRepresentation> candidates = new CcpJsonRepresentation(candidatesText).getAsJsonList(new CcpFieldName("candidates"));
		Set<String> seen = new HashSet<>();
		int invalid = 0, hasResume = 0, reinvitedBefore = 0, suppressed = 0, repeated = 0, sent = 0;
		int pending = 0;
		for (CcpJsonRepresentation candidate : candidates) {
			String email = candidate.getAsString(VisBusinessBuildLegacyCandidateTable.Legacy.id).trim().toLowerCase();
			CcpEmailDecorator emailDecorator = new CcpStringDecorator(email).email();
			if(false == emailDecorator.isValid()) {
				invalid++;
				continue;
			}
			String emailHash = emailDecorator.hash().asString(CcpHashAlgorithm.SHA1);
			if(false == seen.add(emailHash)) {
				repeated++;
				continue;
			}
			if(withResume.contains(emailHash)) {
				hasResume++;
				continue;
			}
			if(alreadyReinvited.contains(emailHash)) {
				reinvitedBefore++;
				continue;
			}
			CcpJsonRepresentation suppressionKey = CcpOtherConstants.EMPTY_JSON.put(JnJsonCommonsFields.email, email);
			if(JnEntityEmailSuppressed.ENTITY.exists(suppressionKey)) {
				suppressed++;
				continue;
			}
			// alem da quantidade pedida (0 = so contar), o candidato fica para a proxima execucao
			if(sent >= limit) {
				pending++;
				continue;
			}
			CcpJsonRepresentation candidateToInvite = candidate
					.put(VisBusinessBuildLegacyCandidateTable.Legacy.id, email)
					.put(VisRecruiterResumesFields.emailHash, emailHash);
			CcpJsonRepresentation tableInput = CcpOtherConstants.EMPTY_JSON
					.put(VisRecruiterResumesFields.legacyCandidate, candidateToInvite)
					.put(JnJsonCommonsFields.email, email)
					.put(VisRecruiterResumesFields.frontendUrl, frontendUrl);
			CcpJsonRepresentation withTable = VisBusinessBuildLegacyCandidateTable.INSTANCE.execute(tableInput);
			String resumesTable = withTable.getAsString(VisRecruiterResumesFields.resumesTable);
			sendTheInvitation(email, resumesTable, resumeFormLink);
			Files.writeString(controlFile, emailHash + System.lineSeparator(), StandardCharsets.UTF_8, StandardOpenOption.CREATE, StandardOpenOption.APPEND);
			sent++;
			if(sent % 250 == 0) {
				System.out.println("enviados ate agora: " + sent);
			}
		}
		System.out.println("OK candidatosDoLegado=" + candidates.size() + " invalidos=" + invalid + " repetidos=" + repeated
				+ " jaTemCurriculo=" + hasResume + " jaReconvidados=" + reinvitedBefore + " suprimidos=" + suppressed + " enviados=" + sent + " pendentes=" + pending);
		System.exit(0);
	}

	/** O convite original: uma falha do provedor lança e para a execução. */
	private static void sendTheInvitation(String email, String resumesTable, String resumeFormLink) throws Exception {
		Method method = VisBusinessInviteLegacyCandidates.class.getDeclaredMethod("sendTheInvitation", String.class, String.class, String.class);
		method.setAccessible(true);
		try {
			method.invoke(null, email, resumesTable, resumeFormLink);
		} catch (InvocationTargetException e) {
			Throwable cause = e.getCause();
			if(cause instanceof Exception) {
				throw (Exception) cause;
			}
			throw e;
		}
	}

	/** Os hashes dos e-mails de todo currículo de produção, ativo ou inativo. */
	private static Set<String> getEmailsWithResume() {
		CcpEntity inactiveResume = VisEntityResume.ENTITY.getTwinEntity();
		CcpEntity[] resumeEntities = {VisEntityResume.ENTITY, inactiveResume};
		Set<String> emails = new HashSet<>();
		String emailField = VisEntityResume.Fields.email.getValue();
		CcpQueryOptions.INSTANCE.matchAll().selectFrom(resumeEntities)
			.consumeQueryResult("5m", 200, resume -> emails.add(resume.getAsString(VisEntityResume.Fields.email)), emailField);
		System.out.println("curriculos em producao (ativos e inativos): " + emails.size());
		return emails;
	}
}
