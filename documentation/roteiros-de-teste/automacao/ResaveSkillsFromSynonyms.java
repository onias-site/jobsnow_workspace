import java.util.List;

import com.ccp.constants.CcpOtherConstants;
import com.ccp.decorators.CcpJsonRepresentation;
import com.ccp.dependency.injection.CcpDependencyInjection;
import com.ccp.especifications.db.bulk.CcpBulkItem;
import com.ccp.implementations.db.bulk.elasticsearch.CcpElasticSerchDbBulk;
import com.ccp.implementations.db.crud.elasticsearch.CcpElasticSearchCrud;
import com.ccp.implementations.db.query.elasticsearch.CcpElasticSearchQueryExecutor;
import com.ccp.implementations.db.utils.elasticsearch.CcpElasticSearchDbRequest;
import com.ccp.implementations.http.apache.mime.CcpApacheMimeHttp;
import com.ccp.implementations.json.gson.CcpGsonJsonHandler;
import com.ccp.implementations.password.mindrot.CcpMindrotPasswordHandler;
import com.ccp.local.testings.implementations.CcpLocalInstances;
import com.ccp.local.testings.implementations.cache.CcpLocalCacheInstances;
import com.vis.entities.VisEntitySkill;
import com.vis.json.fields.validation.VisJsonCommonsFields;

/**
 * Leva o synonyms.json ao vis_skill de um banco ja populado, sem recriar indices (secao 18 da revisao de 2026-11-02):
 * regrava, uma a uma, pelo VisEntitySkill.ENTITY.save, as skills que a semente monta, para o decorator do grouper
 * atualizar os grupos de iniciais no jn_grouper, e apaga pelo ENTITY.delete as skills fundidas passadas como argumento.
 * O ranking e o childOcurrences voltam com os valores da semente ate a proxima carga do Telegram, que os recalcula.
 * Rode de dentro de ccp_rest-api-tests_jobsnow (a semente le ../ccp_rest-api-tests_jobsnow/documentation/...).
 * Uso: java @args ResaveSkillsFromSynonyms.java "SKILL FUNDIDA 1" "SKILL FUNDIDA 2" ...
 */
public class ResaveSkillsFromSynonyms {

	public static void main(String[] args) {
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
		String skillEntityName = VisEntitySkill.ENTITY.getEntityMetaData().entityName;
		List<CcpBulkItem> seed = VisEntitySkill.INSTANCE.getFirstRecordsToInsert();
		int saved = 0;
		long start = System.currentTimeMillis();
		for (CcpBulkItem item : seed) {
			String itemEntityName = item.entity.getEntityMetaData().entityName;
			if (false == skillEntityName.equals(itemEntityName)) {
				continue;
			}
			VisEntitySkill.ENTITY.save(item.json);
			saved++;
			if (saved % 100 == 0) {
				System.out.println("Regravadas: " + saved);
			}
		}
		int deleted = 0;
		for (String skill : args) {
			CcpJsonRepresentation key = CcpOtherConstants.EMPTY_JSON.put(VisJsonCommonsFields.skill, skill);
			boolean wasDeleted = VisEntitySkill.ENTITY.delete(key);
			System.out.println("Apagada " + skill + ": " + wasDeleted);
			deleted += wasDeleted ? 1 : 0;
		}
		long seconds = (System.currentTimeMillis() - start) / 1000;
		System.out.println("Skills regravadas.......: " + saved);
		System.out.println("Skills apagadas.........: " + deleted + " de " + args.length);
		System.out.println("Segundos................: " + seconds);
		System.exit(0);
	}
}
