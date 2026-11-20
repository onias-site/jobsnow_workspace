import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

import com.ccp.constants.CcpOtherConstants;
import com.ccp.decorators.CcpJsonRepresentation;
import com.ccp.dependency.injection.CcpDependencyInjection;
import com.ccp.especifications.db.utils.entity.CcpEntity;
import com.ccp.implementations.db.bulk.elasticsearch.CcpElasticSerchDbBulk;
import com.ccp.implementations.db.crud.elasticsearch.CcpElasticSearchCrud;
import com.ccp.implementations.db.query.elasticsearch.CcpElasticSearchQueryExecutor;
import com.ccp.implementations.db.utils.elasticsearch.CcpElasticSearchDbRequest;
import com.ccp.implementations.http.apache.mime.CcpApacheMimeHttp;
import com.ccp.implementations.json.gson.CcpGsonJsonHandler;
import com.ccp.implementations.password.mindrot.CcpMindrotPasswordHandler;
import com.ccp.local.testings.implementations.CcpLocalInstances;
import com.ccp.local.testings.implementations.cache.CcpLocalCacheInstances;
import com.jn.entities.JnEntityLoginEmail;
import com.js.entities.JsEntityLoginAnswers;
import com.js.entities.JsEntityLoginPassword;
import com.js.entities.JsEntityLoginToken;
import com.vis.entities.VisEntityViewedResume;

/**
 * Apaga, pela entidade ({@code deleteAnyWhere}: principal e gêmea, com os decorators que corrigem os grupos e os
 * contadores do {@code jn_grouper}), as visualizações de currículo de um recrutador (uma por LinkedIn do arquivo) e o
 * login do mesmo e-mail: token, senha, respostas do cadastro e {@code jn_login_email}. O recrutador
 * ({@code vis_recruiter}) fica. Roda contra o Elasticsearch da {@code application_properties} do processo (o .ps1 troca
 * pelo de produção, pelo túnel). Nem o e-mail nem os LinkedIns são impressos. O histórico de cada registro (um grupo do
 * {@code jn_grouper} desde 2026-11-20) sai com o registro; os grupos de sessão já expurgada ficam com o script Python
 * que acompanha esta tarefa.
 * <p>
 * Sem {@code --gravar} só mostra onde cada registro está. Rodar de novo não muda nada.
 * <p>
 * Uso: {@code <e-mail do recrutador> <arquivo com um LinkedIn por linha> [--gravar]}
 */
public class DeleteViewsAndLoginOfARecruiter {

	public static void main(String[] args) throws Exception {
		if(args.length < 2) {
			System.out.println("Uso: <e-mail do recrutador> <arquivo com um LinkedIn por linha> [--gravar]");
			System.exit(1);
		}
		CcpDependencyInjection.loadAllDependencies(
				CcpGsonJsonHandler.INSTANCE,
				CcpLocalInstances.email,
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
		String email = args[0];
		boolean write = List.of(args).contains("--gravar");
		List<String> lines = Files.readAllLines(Path.of(args[1]));
		List<String> linkedins = lines.stream().map(String::trim).filter(line -> false == line.isEmpty()).toList();
		int failures = 0, found = 0;
		for (int index = 0; index < linkedins.size(); index++) {
			CcpJsonRepresentation key = CcpOtherConstants.EMPTY_JSON
					.put(VisEntityViewedResume.Fields.linkedin, linkedins.get(index))
					.put(VisEntityViewedResume.Fields.email, email);
			int result = deleteOne(VisEntityViewedResume.ENTITY, true, key, write, "visualizacao " + (index + 1));
			found += result >= 0 ? 1 : 0;
			failures += result == 1 ? 1 : 0;
		}
		System.out.println("visualizacoes: " + linkedins.size() + ", encontradas: " + found);
		CcpJsonRepresentation emailKey = CcpOtherConstants.EMPTY_JSON.put(JnEntityLoginEmail.Fields.email, email);
		CcpJsonRepresentation answersKey = emailKey
				.put(JsEntityLoginAnswers.Fields.channel, JsEntityLoginAnswers.VisChannelTypes.linkedin.name())
				.put(JsEntityLoginAnswers.Fields.goal, JsEntityLoginAnswers.VisGoalTypes.recruiting.name());
		failures += Math.max(0, deleteOne(JsEntityLoginToken.ENTITY, true, emailKey, write, "js_login_token"));
		failures += Math.max(0, deleteOne(JsEntityLoginPassword.ENTITY, true, emailKey, write, "js_login_password"));
		failures += Math.max(0, deleteOne(JsEntityLoginAnswers.ENTITY, false, answersKey, write, "js_login_answers"));
		failures += Math.max(0, deleteOne(JnEntityLoginEmail.ENTITY, false, emailKey, write, "jn_login_email"));
		System.out.println(write ? "falhas: " + failures : "(simulacao: use --gravar)");
		System.exit(failures == 0 ? 0 : 2);
	}

	/** -1 = ausente, 0 = presente (simulação) ou apagado, 1 = ainda existe depois do delete. */
	private static int deleteOne(CcpEntity entity, boolean hasTwin, CcpJsonRepresentation key, boolean write, String label) {
		boolean inTheMain = entity.exists(key);
		boolean inTheTwin = hasTwin && entity.getTwinEntity().exists(key);
		String before = inTheMain ? "principal" : inTheTwin ? "gemea" : "ausente";
		if(false == inTheMain && false == inTheTwin) {
			System.out.println(label + ": ausente");
			return -1;
		}
		if(false == write) {
			System.out.println(label + ": " + before);
			return 0;
		}
		entity.deleteAnyWhere(key);
		boolean stillInTheMain = entity.exists(key);
		boolean stillInTheTwin = hasTwin && entity.getTwinEntity().exists(key);
		boolean gone = false == stillInTheMain && false == stillInTheTwin;
		System.out.println(label + ": " + before + " -> " + (gone ? "apagado" : "FALHOU (principal=" + stillInTheMain + ", gemea=" + stillInTheTwin + ")"));
		return gone ? 0 : 1;
	}
}
