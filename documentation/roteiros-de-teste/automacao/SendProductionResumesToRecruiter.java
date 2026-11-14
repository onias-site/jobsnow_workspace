import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

import com.ccp.constants.CcpOtherConstants;
import com.ccp.decorators.CcpFieldName;
import com.ccp.decorators.CcpJsonRepresentation;
import com.ccp.dependency.injection.CcpDependencyInjection;
import com.ccp.dependency.injection.CcpInstanceProvider;
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
import com.vis.business.recruiter.resumes.VisBusinessSendResumesToRecruiters;
import com.vis.entities.VisEntityRecruiter;
import com.vis.entities.VisEntityRecruiterResumes;
import com.vis.json.transformers.VisJsonTransformerRecruiterDomain;
import com.vis.json.transformers.VisJsonTransformerRecruiterProfessional;
import com.vis.messages.VisMessages;

/**
 * Envia a um único recrutador o e-mail de currículos ({@code VisNotifyRecruiterAboutResumes}) com TODOS os currículos de
 * {@code vis_resume} de produção, e não só os alterados nos últimos 7 dias. Os dados de produção chegam por um arquivo,
 * gravado antes pelo {@code ler-curriculos-de-producao.py} (só leitura, pelo túnel): este processo roda contra o
 * Elasticsearch local e nada grava em produção.
 *
 * <p>As regras são as do processo diário ({@code VisBusinessSendResumesToRecruiters}), chamadas por reflexão porque são
 * de pacote: ordem dos currículos, {@code notAllowedCompany} do domínio do recrutador, última visualização, apelido, links
 * assinados e descadastro. O que muda: não há janela de 7 dias, fim de semana, fila nem limite diário, e o recrutador não
 * precisa estar em {@code vis_recruiter}.
 *
 * <p>Para os links funcionarem em produção, a {@code application_properties} deste processo precisa do
 * {@code recruiterLinksSecret} de produção, além da chave do SendGrid: quem cuida disso é o
 * {@code enviar-curriculos-de-producao-a-um-recrutador.ps1}, por onde este executor deve ser rodado.
 *
 * <p>A marca local de "já enviado hoje" deste e-mail a este destinatário é apagada antes do envio, para o executor poder
 * rodar mais de uma vez no dia (simular e depois enviar). O template e os parâmetros de envio são os do Elasticsearch
 * local. A lista completa ({@code vis_recruiter_resumes}) é gravada pelo envio no local; no modo enviar ela também vai
 * para um arquivo, que o {@code .ps1} grava em produção (modo {@code gravar-lista}, com o Elasticsearch de produção pelo
 * túnel): sem isso o link "ver todos" do e-mail abria a tela vazia (404) em produção (corrigido em 2026-11-12). Esta é a
 * única gravação em produção, um registro descartável diário do próprio recrutador.
 *
 * <p>Uso: {@code simular|enviar <e-mail do recrutador> <arquivo dos dados de produção> <endereço do front> <endereço da API vis> [arquivo da lista]}
 * e {@code gravar-lista <e-mail do recrutador> <arquivo da lista>}
 */
public class SendProductionResumesToRecruiter {

	public static void main(String[] args) throws Exception {
		boolean saveTheList = "gravar-lista".equals(args[0]);
		if(saveTheList) {
			saveTheListOfTheScreenSeeAll(args);
			return;
		}
		boolean send = "enviar".equals(args[0]);
		boolean simulate = "simular".equals(args[0]);
		if((false == send && false == simulate) || args.length < 5) {
			System.out.println("Uso: simular|enviar <e-mail do recrutador> <arquivo dos dados de producao> <endereco do front> <endereco da API vis> [arquivo da lista]");
			System.out.println("     gravar-lista <e-mail do recrutador> <arquivo da lista>");
			System.exit(1);
		}
		String email = args[1].trim().toLowerCase();
		String productionDataText = Files.readString(Path.of(args[2]), StandardCharsets.UTF_8);
		String frontendUrl = args[3];
		String visApiUrl = args[4];

		CcpInstanceProvider<?> emailProvider = send ? CcpSendGridEmailProvider.INSTANCE : CcpLocalInstances.email;
		loadDependencies(emailProvider);

		CcpJsonRepresentation productionData = new CcpJsonRepresentation(productionDataText);
		List<CcpJsonRepresentation> resumes = productionData.getAsJsonList(new CcpFieldName("resumes"));
		CcpJsonRepresentation rankings = productionData.getInnerJson(new CcpFieldName("rankings"));
		Map<String, long[]> resumeDates = getResumeDates(productionData.getInnerJson(new CcpFieldName("dates")));
		Map<String, Long> lastViewByPair = getLastViewByPair(productionData.getInnerJson(new CcpFieldName("lastViewByPair")));
		Map<String, String> aliasByPair = getAliasByPair(productionData.getInnerJson(new CcpFieldName("aliasByPair")));
		if(resumes.isEmpty()) {
			System.out.println("Nenhum curriculo em vis_resume de producao: nada a enviar.");
			System.exit(2);
		}

		Object viewsByResume = call("getViewsByResume", new Class<?>[] {Map.class}, lastViewByPair);
		Object resumesOfTheEmail = call("getResumesOfTheEmail", new Class<?>[] {List.class, CcpJsonRepresentation.class, Map.class, Map.class},
				resumes, rankings, resumeDates, viewsByResume);

		CcpJsonRepresentation recruiterEmail = CcpOtherConstants.EMPTY_JSON.put(VisEntityRecruiter.Fields.email, email);
		CcpJsonRepresentation withProfessional = VisJsonTransformerRecruiterProfessional.INSTANCE.execute(recruiterEmail);
		CcpJsonRepresentation recruiter = VisJsonTransformerRecruiterDomain.INSTANCE.execute(withProfessional);
		Object emailHash = call("getEmailHash", new Class<?>[] {String.class}, email);
		// os pares de vis_inactive_viewed_resume (desde 2026-11-12); um arquivo lido antes disso nao os tem
		List<String> inactivePairsList = productionData.getOrDefault(new CcpFieldName("inactivePairs"), () -> List.of());
		Set<String> inactivePairs = new HashSet<>(inactivePairsList);
		List<?> rows = (List<?>) call("getRowsOfTheRecruiter", new Class<?>[] {CcpJsonRepresentation.class, String.class, List.class, Map.class, Map.class, Set.class},
				recruiter, emailHash, resumesOfTheEmail, lastViewByPair, aliasByPair, inactivePairs);
		if(rows.isEmpty()) {
			System.out.println("Todos os curriculos proibem a empresa deste recrutador: nada a enviar.");
			System.exit(2);
		}

		String templateId = VisMessages.VisNotifyRecruiterAboutResumes.class.getName();
		CcpJsonRepresentation sentMark = CcpOtherConstants.EMPTY_JSON
				.put(JnEntityEmailMessageSent.Fields.subjectType, templateId)
				.put(JnEntityEmailMessageSent.Fields.email, email);
		boolean sentToday = JnEntityEmailMessageSent.ENTITY.exists(sentMark);
		if(sentToday) {
			JnEntityEmailMessageSent.ENTITY.delete(sentMark);
		}

		call("sendTheEmail", new Class<?>[] {String.class, List.class, String.class, String.class}, email, rows, frontendUrl, visApiUrl);

		// o envio registra a falha como aviso em vez de lancar: a marca de "ja enviado" so existe quando o provedor aceitou
		boolean accepted = JnEntityEmailMessageSent.ENTITY.exists(sentMark);
		int shown = Math.min(VisBusinessSendResumesToRecruiters.RESUMES_IN_THE_EMAIL, rows.size());
		System.out.println((accepted ? "OK " : "FALHOU ") + (send ? "enviar" : "simular") + " curriculosEmProducao=" + resumes.size()
				+ " linhasDoRecrutador=" + rows.size() + " noEmail=" + shown);
		if(false == accepted) {
			System.out.println("O e-mail nao foi aceito: veja o ultimo registro de jn_jobsnow_warning no Elasticsearch local.");
			System.exit(3);
		}
		// a lista inteira da tela "ver todos", gravada pelo envio no ES local, vai para um arquivo: o .ps1 a grava em
		// producao (modo gravar-lista), onde a tela a le pelo e-mail do recrutador logado
		boolean exportTheList = send && args.length > 5;
		if(exportTheList) {
			CcpJsonRepresentation key = CcpOtherConstants.EMPTY_JSON.put(VisEntityRecruiterResumes.Fields.email, email);
			CcpJsonRepresentation savedList = VisEntityRecruiterResumes.ENTITY.getOneById(key);
			List<CcpJsonRepresentation> listRows = savedList.getAsJsonList(VisEntityRecruiterResumes.Fields.resumes);
			CcpJsonRepresentation list = CcpOtherConstants.EMPTY_JSON.put(VisEntityRecruiterResumes.Fields.resumes, listRows);
			Files.writeString(Path.of(args[5]), list.asUgglyJson(), StandardCharsets.UTF_8);
			System.out.println("listaDaTelaVerTodos=" + listRows.size());
		}
		System.exit(0);
	}

	/**
	 * Modo gravar-lista: grava em {@code vis_recruiter_resumes} a lista da tela "ver todos" exportada pelo envio. Roda com
	 * a {@code application_properties} apontando o Elasticsearch para producao (pelo tunel), e grava pela propria entidade,
	 * com os seus decorators (o descartavel diario inclusive), como o processo diario grava. Confere a gravacao relendo.
	 */
	private static void saveTheListOfTheScreenSeeAll(String[] args) throws Exception {
		if(args.length < 3) {
			System.out.println("Uso: gravar-lista <e-mail do recrutador> <arquivo da lista>");
			System.exit(1);
		}
		loadDependencies(CcpLocalInstances.email);
		String email = args[1].trim().toLowerCase();
		String listText = Files.readString(Path.of(args[2]), StandardCharsets.UTF_8);
		CcpJsonRepresentation list = new CcpJsonRepresentation(listText);
		List<CcpJsonRepresentation> rows = list.getAsJsonList(VisEntityRecruiterResumes.Fields.resumes);
		CcpJsonRepresentation recruiterResumes = CcpOtherConstants.EMPTY_JSON
				.put(VisEntityRecruiterResumes.Fields.email, email)
				.put(VisEntityRecruiterResumes.Fields.resumes, rows);
		VisEntityRecruiterResumes.ENTITY.save(recruiterResumes);
		CcpJsonRepresentation key = CcpOtherConstants.EMPTY_JSON.put(VisEntityRecruiterResumes.Fields.email, email);
		CcpJsonRepresentation saved = VisEntityRecruiterResumes.ENTITY.getOneById(key);
		int savedRows = saved.getAsJsonList(VisEntityRecruiterResumes.Fields.resumes).size();
		boolean complete = savedRows == rows.size();
		System.out.println((complete ? "OK " : "FALHOU ") + "gravar-lista linhas=" + rows.size() + " relidas=" + savedRows);
		System.exit(complete ? 0 : 4);
	}

	private static void loadDependencies(CcpInstanceProvider<?> emailProvider) {
		CcpDependencyInjection.loadAllDependencies(
				CcpGsonJsonHandler.INSTANCE,
				emailProvider,
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

	/** Chama um método estático, de pacote, do processo diário. */
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

	private static Map<String, long[]> getResumeDates(CcpJsonRepresentation dates) {
		Map<String, long[]> resumeDates = new HashMap<>();
		for (String emailHash : dates.fieldSet()) {
			List<Object> oldestAndNewest = dates.getAsObjectList(new CcpFieldName(emailHash));
			long oldest = ((Number) oldestAndNewest.get(0)).longValue();
			long newest = ((Number) oldestAndNewest.get(1)).longValue();
			resumeDates.put(emailHash, new long[] {oldest, newest});
		}
		return resumeDates;
	}

	private static Map<String, Long> getLastViewByPair(CcpJsonRepresentation views) {
		Map<String, Long> lastViewByPair = new HashMap<>();
		for (String pair : views.fieldSet()) {
			Double lastView = views.getAsDoubleNumber(new CcpFieldName(pair));
			lastViewByPair.put(pair, lastView.longValue());
		}
		return lastViewByPair;
	}

	private static Map<String, String> getAliasByPair(CcpJsonRepresentation aliases) {
		Map<String, String> aliasByPair = new HashMap<>();
		for (String pair : aliases.fieldSet()) {
			String alias = aliases.getAsString(new CcpFieldName(pair));
			aliasByPair.put(pair, alias);
		}
		return aliasByPair;
	}
}
