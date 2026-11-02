import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.function.Consumer;

import com.ccp.constants.CcpOtherConstants;
import com.ccp.decorators.CcpJsonRepresentation;
import com.ccp.dependency.injection.CcpDependencyInjection;
import com.ccp.dependency.injection.CcpInstanceProvider;
import com.ccp.especifications.db.bulk.CcpBulkItem;
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
import com.vis.business.recruiter.resumes.VisBusinessInviteLegacyCandidates;
import com.vis.business.recruiter.resumes.VisRecruiterResumesFields;
import com.vis.entities.VisEntityRecruiterResumes;

/**
 * Convite único aos candidatos do índice legado {@code profissionais2}, rodado no deploy
 * ({@code VisBusinessInviteLegacyCandidates}). Rodar pelo {@code executaConviteDeCurriculos.bat}, na raiz do workspace.
 *
 * <ul>
 * <li>{@code simular [quantidade]}: nada sai daqui, os e-mails vão para {@code c:\logs\email\<destinatário>}, e quem foi
 * simulado não conta como convidado. Padrão: 3 e-mails.</li>
 * <li>{@code enviar <endereço do front> [quantidade]}: envia pelo SendGrid. O endereço precisa ser https. Cada e-mail aceito
 * grava o SHA-1 do destinatário em {@code c:\logs\convite-curriculos\convidados.txt}, e por isso rodar de novo continua de
 * onde parou, sem repetir ninguém.</li>
 * </ul>
 */
public class InviteLegacyCandidates {

	private static final Path INVITED_FILE = Path.of("c:/logs/convite-curriculos/convidados.txt");

	private static final String SIMULATION_ADDRESS = "http://localhost:3000";

	private static final int SIMULATED_EMAILS = 3;

	public static void main(String[] args) throws IOException {
		boolean send = args.length > 0 && "enviar".equals(args[0]);
		boolean simulate = args.length > 0 && "simular".equals(args[0]);
		if(false == send && false == simulate) {
			System.out.println("Uso: simular [quantidade] | enviar <endereco https do front> [quantidade]");
			System.exit(1);
		}
		if(send && (args.length < 2 || false == args[1].startsWith("https://"))) {
			System.out.println("Para enviar, informe o endereco https do front: o link do formulario sai dele.");
			System.exit(1);
		}

		CcpInstanceProvider<?> email = send ? CcpSendGridEmailProvider.INSTANCE : CcpLocalInstances.email;
		CcpDependencyInjection.loadAllDependencies(
				CcpGsonJsonHandler.INSTANCE,
				email,
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

		List<CcpBulkItem> seeds = VisEntityRecruiterResumes.INSTANCE.getInvitationSeeds();
		for (CcpBulkItem seed : seeds) {
			seed.entity.save(seed.json);
		}

		String frontendUrl = send ? args[1] : SIMULATION_ADDRESS;
		int quantityPosition = send ? 2 : 1;
		boolean quantityGiven = args.length > quantityPosition;
		int defaultQuantity = send ? Integer.MAX_VALUE : SIMULATED_EMAILS;
		int limit = quantityGiven ? Integer.parseInt(args[quantityPosition]) : defaultQuantity;

		Files.createDirectories(INVITED_FILE.getParent());
		Set<String> alreadyInvited = new HashSet<>();
		if(send && Files.exists(INVITED_FILE)) {
			alreadyInvited.addAll(Files.readAllLines(INVITED_FILE, StandardCharsets.UTF_8));
		}
		Consumer<String> onInvited = send ? InviteLegacyCandidates::recordInvited : hash -> {};

		CcpJsonRepresentation input = CcpOtherConstants.EMPTY_JSON.put(VisRecruiterResumesFields.frontendUrl, frontendUrl);
		CcpJsonRepresentation counters = new VisBusinessInviteLegacyCandidates(alreadyInvited, onInvited, limit).execute(input);
		System.out.println("OK " + counters);
		System.exit(0);
	}

	private static void recordInvited(String emailHash) {
		try {
			String line = emailHash + System.lineSeparator();
			Files.writeString(INVITED_FILE, line, StandardCharsets.UTF_8, StandardOpenOption.CREATE, StandardOpenOption.APPEND);
		} catch (IOException e) {
			// sem o registro, uma nova execucao repetiria este destinatario: melhor parar
			throw new RuntimeException(e);
		}
	}
}
