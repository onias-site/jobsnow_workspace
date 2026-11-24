import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import com.ccp.constants.CcpOtherConstants;
import com.ccp.decorators.CcpFieldName;
import com.ccp.decorators.CcpJsonRepresentation;
import com.ccp.dependency.injection.CcpDependencyInjection;
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
import com.jn.entities.JnEntityEmailMessageSent;
import com.jn.json.fields.validation.JnJsonCommonsFields;
import com.jn.business.messages.JnMessageSenderExceptionHandler;
import com.jn.business.messages.JnMessageType;
import com.jn.messages.JnSendMessageToUser;
import com.vis.business.recruiter.resumes.VisBusinessRenderResumesTable;
import com.vis.business.recruiter.resumes.VisBusinessSendResumesToRecruiters;
import com.vis.business.recruiter.resumes.VisRecruiterResumesFields;
import com.vis.messages.VisMessages;

/**
 * Manda a outro endereço uma cópia do e-mail de currículos ({@code VisNotifyRecruiterAboutResumes}) que um recrutador
 * recebeu hoje (2026-11-24, pedido do usuário: "quero ver o que ele viu"). As linhas vêm do que o próprio envio gravou
 * em produção para o recrutador ({@code vis_recruiter_resumes} de hoje: ordem, "você nunca visualizou", última
 * visualização, apelido) e o assunto é o gravado em {@code jn_email_message_sent}, de onde saem {@code topSkills} e
 * {@code otherSkills}. Monta a mensagem como {@code VisBusinessSendResumesToRecruiters.sendTheEmail}, com o destinatário
 * da cópia no lugar do recrutador.
 *
 * <p>O token de cada currículo continua o assinado para o recrutador original, e o link leva o e-mail da cópia: a
 * assinatura não confere, então um clique não grava visualização em nome de ninguém nem avisa o candidato. "Ver todos" e
 * "descadastrar" são os do destinatário da cópia. Nada é gravado na lista "Ver todos" do destinatário; a marca de "já
 * enviado hoje" dele é apagada antes, para o envio não ser barrado.
 *
 * <p>Uso: {@code <e-mail da cópia> <arquivo lido de produção> <endereço do front> <endereço da API vis>}
 */
public class SendCopyOfRecruiterEmail {

	public static void main(String[] args) throws Exception {
		if(args.length < 4) {
			System.out.println("Uso: <e-mail da copia> <arquivo lido de producao> <endereco do front> <endereco da API vis>");
			System.exit(1);
		}
		String email = args[0].trim().toLowerCase();
		String dataText = Files.readString(Path.of(args[1]), StandardCharsets.UTF_8);
		String frontendUrl = args[2];
		String visApiUrl = args[3];

		loadDependencies();

		CcpJsonRepresentation data = new CcpJsonRepresentation(dataText);
		CcpJsonRepresentation recruiterResumes = data.getInnerJson(new CcpFieldName("vis_recruiter_resumes"));
		CcpJsonRepresentation sent = data.getInnerJson(new CcpFieldName("jn_email_message_sent"));
		List<CcpJsonRepresentation> rows = recruiterResumes.getAsJsonList(new CcpFieldName("resumes"));
		String subject = sent.getAsString(new CcpFieldName("subject"));

		Pattern subjectPattern = Pattern.compile("^\\[DE GRAÇA!!!\\] (\\d+) currículos de (.*) e mais outras (\\d+) habilidades gratuitos pra você!!!$");
		Matcher matcher = subjectPattern.matcher(subject);
		boolean unknownSubject = false == matcher.matches();
		if(unknownSubject) {
			System.out.println("Assunto em formato desconhecido: nada enviado.");
			System.exit(2);
		}
		int totalInTheSubject = Integer.parseInt(matcher.group(1));
		String topSkills = matcher.group(2);
		int otherSkills = Integer.parseInt(matcher.group(3));
		int total = rows.size();
		if(totalInTheSubject != total) {
			System.out.println("O assunto fala em " + totalInTheSubject + " curriculos e a lista tem " + total + ": nada enviado.");
			System.exit(2);
		}

		int shown = Math.min(VisBusinessSendResumesToRecruiters.RESUMES_IN_THE_EMAIL, total);
		List<CcpJsonRepresentation> rowsOfTheEmail = rows.subList(0, shown);
		Object language = getField("LANGUAGE");
		CcpJsonRepresentation tableInput = CcpOtherConstants.EMPTY_JSON
				.put(VisRecruiterResumesFields.resumes, rowsOfTheEmail)
				.put(JnJsonCommonsFields.email, email)
				.put(VisRecruiterResumesFields.frontendUrl, frontendUrl)
				.put(JnJsonCommonsFields.language, language);
		CcpJsonRepresentation withTable = VisBusinessRenderResumesTable.INSTANCE.execute(tableInput);
		String resumesTable = withTable.getAsString(VisRecruiterResumesFields.resumesTable);

		String seeAllUrl = (String) call("getSeeAllUrl", new Class<?>[] {String.class, String.class}, email, frontendUrl);
		String seeAll = (String) call("getSeeAll", new Class<?>[] {int.class, int.class, String.class}, shown, total, seeAllUrl);
		String unsubscribeLink = (String) call("getUnsubscribeLink", new Class<?>[] {String.class, String.class}, email, frontendUrl);
		CcpJsonRepresentation emailHeaders = (CcpJsonRepresentation) call("getEmailHeaders", new Class<?>[] {String.class, String.class}, email, visApiUrl);

		CcpJsonRepresentation message = CcpOtherConstants.EMPTY_JSON
				.put(JnJsonCommonsFields.email, email)
				.put(JnJsonCommonsFields.language, language)
				.put(VisRecruiterResumesFields.resumesTable, resumesTable)
				.put(VisRecruiterResumesFields.seeAll, seeAll)
				.put(VisRecruiterResumesFields.seeAllUrl, seeAllUrl)
				.put(VisRecruiterResumesFields.unsubscribeLink, unsubscribeLink)
				.put(VisRecruiterResumesFields.totalOfResumes, total)
				.put(JnJsonCommonsFields.emailHeaders, emailHeaders)
				.put(VisRecruiterResumesFields.topSkills, topSkills)
				.put(VisRecruiterResumesFields.otherSkills, otherSkills);

		String templateId = VisMessages.VisNotifyRecruiterAboutResumes.class.getName();
		CcpJsonRepresentation sentMark = CcpOtherConstants.EMPTY_JSON
				.put(JnEntityEmailMessageSent.Fields.subjectType, templateId)
				.put(JnEntityEmailMessageSent.Fields.email, email);
		boolean sentToday = JnEntityEmailMessageSent.ENTITY.exists(sentMark);
		if(sentToday) {
			JnEntityEmailMessageSent.ENTITY.delete(sentMark);
		}

		JnMessageType[] messageTypes = {JnMessageType.email};
		new JnSendMessageToUser().sendAllMessages(message, templateId, messageTypes, JnMessageSenderExceptionHandler.LENIENT);

		boolean accepted = JnEntityEmailMessageSent.ENTITY.exists(sentMark);
		long neverViewed = rowsOfTheEmail.stream().filter(row -> false == row.getOrDefault(VisRecruiterResumesFields.viewed, () -> false)).count();
		System.out.println((accepted ? "OK " : "FALHOU ") + "copia linhas=" + total + " noEmail=" + shown + " nuncaVisualizadosNoEmail=" + neverViewed);
		CcpJsonRepresentation savedMark = accepted ? JnEntityEmailMessageSent.ENTITY.getOneById(sentMark) : CcpOtherConstants.EMPTY_JSON;
		String sentSubject = savedMark.getOrDefault(JnEntityEmailMessageSent.Fields.subject, () -> "");
		System.out.println("assunto igual ao original: " + subject.equals(sentSubject));
		System.exit(accepted ? 0 : 3);
	}

	/** Produção: Elasticsearch e SendGrid de verdade; mensageria síncrona no próprio processo e cache só em memória. */
	private static void loadDependencies() {
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
	}

	private static Object getField(String name) throws Exception {
		java.lang.reflect.Field field = VisBusinessSendResumesToRecruiters.class.getDeclaredField(name);
		field.setAccessible(true);
		return field.get(null);
	}

	/** Chama um método estático, de pacote ou privado, do processo diário. */
	private static Object call(String name, Class<?>[] parameterTypes, Object... arguments) throws Exception {
		Method method = VisBusinessSendResumesToRecruiters.class.getDeclaredMethod(name, parameterTypes);
		method.setAccessible(true);
		try {
			return method.invoke(null, arguments);
		} catch (InvocationTargetException e) {
			Throwable cause = e.getCause();
			if(cause instanceof Exception) {
				throw (Exception) cause;
			}
			throw e;
		}
	}
}
