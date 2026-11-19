import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

import com.ccp.constants.CcpOtherConstants;
import com.ccp.decorators.CcpFieldName;
import com.ccp.decorators.CcpJsonRepresentation;
import com.ccp.dependency.injection.CcpDependencyInjection;
import com.ccp.especifications.email.CcpEmailProvider;
import com.ccp.especifications.http.CcpHttpContentType;
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
import com.jn.entities.JnEntityEmailParametersToSend;
import com.jn.entities.JnEntityEmailSuppressed;
import com.jn.entities.JnEntityEmailTemplateMessage;
import com.jn.json.fields.validation.JnJsonCommonsFields;
import com.jn.utils.JnSystemProperties;
import com.vis.business.recruiter.resumes.VisBusinessRenderResumesTable;
import com.vis.business.recruiter.resumes.VisBusinessSendResumesToRecruiters;
import com.vis.business.recruiter.resumes.VisRecruiterResumesFields;
import com.vis.entities.VisEntityRecruiter;
import com.vis.json.transformers.VisJsonTransformerRecruiterDomain;
import com.vis.json.transformers.VisJsonTransformerRecruiterProfessional;
import com.vis.messages.VisMessages;

/**
 * Skill ccp-curriculos-para-uma-vaga (2026-11-19): o e-mail de curriculos aos recrutadores so com os curriculos do
 * arquivo de dados, com a abertura e o assunto trocados pelos dados, aos destinatarios dados. Regras de linhas, links
 * assinados, tabela e descadastro sao as do processo diario (VisBusinessSendResumesToRecruiters, por reflexao); o resto
 * do corpo e o template de producao. Nao grava nada em producao (nem a marca de enviado, nem a lista "Ver todos").
 * Uso: <dados> <front> <api> <arquivo html da abertura> <prefixo da previa> <enviar|simular> <arquivo do assunto> <e-mail>...
 */
public class SendJobResumes {

	public static void main(String[] args) throws Exception {
		String dataText = Files.readString(Path.of(args[0]), StandardCharsets.UTF_8);
		String frontendUrl = args[1];
		String visApiUrl = args[2];
		String intro = Files.readString(Path.of(args[3]), StandardCharsets.UTF_8);
		String preview = args[4];
		boolean send = "enviar".equals(args[5]);
		// sem o BOM que o Set-Content -Encoding utf8 do PowerShell 5.1 grava
		String customSubject = Files.readString(Path.of(args[6]), StandardCharsets.UTF_8).replace("﻿", "").trim();
		CcpDependencyInjection.loadAllDependencies(CcpGsonJsonHandler.INSTANCE, CcpSendGridEmailProvider.INSTANCE,
				CcpLocalInstances.instantMessenger, CcpLocalInstances.syncMensageriaListener, CcpLocalCacheInstances.mock,
				CcpMindrotPasswordHandler.INSTANCE, CcpElasticSerchDbBulk.INSTANCE, CcpApacheMimeHttp.INSTANCE,
				CcpElasticSearchDbRequest.INSTANCE, CcpElasticSearchCrud.INSTANCE, CcpElasticSearchQueryExecutor.INSTANCE);

		CcpJsonRepresentation data = new CcpJsonRepresentation(dataText);
		List<CcpJsonRepresentation> resumes = data.getAsJsonList(new CcpFieldName("resumes"));
		CcpJsonRepresentation rankings = data.getInnerJson(new CcpFieldName("rankings"));
		Map<String, long[]> resumeDates = new HashMap<>();
		CcpJsonRepresentation dates = data.getInnerJson(new CcpFieldName("dates"));
		for (String key : dates.fieldSet()) {
			List<Object> pair = dates.getAsObjectList(new CcpFieldName(key));
			resumeDates.put(key, new long[] {((Number) pair.get(0)).longValue(), ((Number) pair.get(1)).longValue()});
		}
		Map<String, Long> lastViewByPair = new HashMap<>();
		CcpJsonRepresentation views = data.getInnerJson(new CcpFieldName("lastViewByPair"));
		for (String key : views.fieldSet()) {
			lastViewByPair.put(key, views.getAsDoubleNumber(new CcpFieldName(key)).longValue());
		}
		Map<String, String> aliasByPair = new HashMap<>();
		CcpJsonRepresentation aliases = data.getInnerJson(new CcpFieldName("aliasByPair"));
		for (String key : aliases.fieldSet()) {
			aliasByPair.put(key, aliases.getAsString(new CcpFieldName(key)));
		}
		List<String> inactivePairsList = data.getOrDefault(new CcpFieldName("inactivePairs"), () -> List.of());
		Set<String> inactivePairs = new HashSet<>(inactivePairsList);
		System.out.println("curriculos no arquivo=" + resumes.size());

		Object viewsByResume = call("getViewsByResume", new Class<?>[] {Map.class}, lastViewByPair);
		Object resumesOfTheEmail = call("getResumesOfTheEmail", new Class<?>[] {List.class, CcpJsonRepresentation.class, Map.class, Map.class},
				resumes, rankings, resumeDates, viewsByResume);

		String templateId = VisMessages.VisNotifyRecruiterAboutResumes.class.getName();
		CcpJsonRepresentation templateKey = CcpOtherConstants.EMPTY_JSON
				.put(JnEntityEmailTemplateMessage.Fields.templateId, templateId)
				.put(JnEntityEmailTemplateMessage.Fields.language, "portuguese");
		CcpJsonRepresentation template = JnEntityEmailTemplateMessage.ENTITY.getOneById(templateKey);
		CcpJsonRepresentation parameters = JnEntityEmailParametersToSend.ENTITY.getOneById(
				CcpOtherConstants.EMPTY_JSON.put(JnEntityEmailParametersToSend.Fields.templateId, templateId));
		String sender = parameters.getAsString(JnEntityEmailParametersToSend.Fields.sender);
		String bodyTemplate = template.getAsString(JnEntityEmailTemplateMessage.Fields.message);
		int bodyStart = bodyTemplate.indexOf("<body>") + "<body>".length();
		int bannerStart = bodyTemplate.indexOf("<p style=\"background-color");
		if(bodyStart < 6 || bannerStart < bodyStart) {
			throw new IllegalStateException("template de producao mudou: abertura nao encontrada");
		}
		String customBody = bodyTemplate.substring(0, bodyStart) + intro + bodyTemplate.substring(bannerStart);

		int exitCode = 0;
		for (int i = 7; i < args.length; i++) {
			String email = args[i].trim().toLowerCase();
			boolean suppressed = JnEntityEmailSuppressed.ENTITY.exists(CcpOtherConstants.EMPTY_JSON.put(JnEntityEmailSuppressed.Fields.email, email));
			if(suppressed) {
				System.out.println("destinatario " + (i - 6) + ": SUPRIMIDO no SendGrid, nao enviado");
				exitCode = 4;
				continue;
			}
			CcpJsonRepresentation recruiterEmail = CcpOtherConstants.EMPTY_JSON.put(VisEntityRecruiter.Fields.email, email);
			CcpJsonRepresentation recruiter = VisJsonTransformerRecruiterDomain.INSTANCE.execute(
					VisJsonTransformerRecruiterProfessional.INSTANCE.execute(recruiterEmail));
			Object emailHash = call("getEmailHash", new Class<?>[] {String.class}, email);
			@SuppressWarnings("unchecked")
			List<CcpJsonRepresentation> rowsWithSubjectItems = (List<CcpJsonRepresentation>) call("getRowsOfTheRecruiter",
					new Class<?>[] {CcpJsonRepresentation.class, String.class, List.class, Map.class, Map.class, Set.class},
					recruiter, emailHash, resumesOfTheEmail, lastViewByPair, aliasByPair, inactivePairs);
			if(rowsWithSubjectItems.isEmpty()) {
				System.out.println("destinatario " + (i - 6) + ": nenhuma linha, nao enviado");
				exitCode = 2;
				continue;
			}
			CcpJsonRepresentation subjectValues = (CcpJsonRepresentation) call("getSubjectValues", new Class<?>[] {List.class}, rowsWithSubjectItems);
			List<CcpJsonRepresentation> rows = new ArrayList<>();
			for (CcpJsonRepresentation row : rowsWithSubjectItems) {
				rows.add(row.removeFields(VisRecruiterResumesFields.subjectItems));
			}
			CcpJsonRepresentation tableInput = CcpOtherConstants.EMPTY_JSON
					.put(VisRecruiterResumesFields.resumes, rows)
					.put(JnJsonCommonsFields.email, email)
					.put(VisRecruiterResumesFields.frontendUrl, frontendUrl)
					.put(JnJsonCommonsFields.language, "portuguese");
			String resumesTable = VisBusinessRenderResumesTable.INSTANCE.execute(tableInput).getAsString(VisRecruiterResumesFields.resumesTable);
			String unsubscribeLink = (String) call("getUnsubscribeLink", new Class<?>[] {String.class, String.class}, email, frontendUrl);
			CcpJsonRepresentation emailHeaders = (CcpJsonRepresentation) call("getEmailHeaders", new Class<?>[] {String.class, String.class}, email, visApiUrl);
			CcpJsonRepresentation values = subjectValues
					.put(VisRecruiterResumesFields.resumesTable, resumesTable)
					.put(VisRecruiterResumesFields.seeAll, "")
					.put(VisRecruiterResumesFields.unsubscribeLink, unsubscribeLink)
					.put(VisRecruiterResumesFields.totalOfResumes, rows.size())
					.put(JnJsonCommonsFields.subject, customSubject)
					.put(JnJsonCommonsFields.message, customBody);
			String subject = values.getAsStringDecorator(JnJsonCommonsFields.subject).text().resolveTemplate(values).content;
			String message = values.getAsStringDecorator(JnJsonCommonsFields.message).text().resolveTemplate(values).content;
			Files.writeString(Path.of(preview + "-" + (i - 6) + ".html"), "<!-- " + subject + " -->\n" + message, StandardCharsets.UTF_8);
			if(false == send) {
				System.out.println("destinatario " + (i - 6) + ": simulado linhas=" + rows.size() + " assunto=" + subject);
				continue;
			}
			CcpEmailProvider provider = CcpDependencyInjection.getDependency(CcpEmailProvider.class);
			provider.sendSimpleTextEmailMessage(JnSystemProperties.INSTANCE.tokenEmailValue(), JnSystemProperties.INSTANCE.urlEmailValue(),
					templateId, sender, subject, message, CcpHttpContentType.TEXT_HTML, emailHeaders, email);
			System.out.println("destinatario " + (i - 6) + ": OK enviado linhas=" + rows.size() + " assunto=" + subject);
		}
		System.exit(exitCode);
	}

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
