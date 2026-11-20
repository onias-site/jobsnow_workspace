import java.util.List;

import com.ccp.constants.CcpOtherConstants;
import com.ccp.decorators.CcpJsonRepresentation;
import com.ccp.dependency.injection.CcpDependencyInjection;
import com.ccp.implementations.db.bulk.elasticsearch.CcpElasticSerchDbBulk;
import com.ccp.implementations.db.crud.elasticsearch.CcpElasticSearchCrud;
import com.ccp.implementations.db.query.elasticsearch.CcpElasticSearchQueryExecutor;
import com.ccp.implementations.db.utils.elasticsearch.CcpElasticSearchDbRequest;
import com.ccp.implementations.http.apache.mime.CcpApacheMimeHttp;
import com.ccp.implementations.json.gson.CcpGsonJsonHandler;
import com.ccp.implementations.password.mindrot.CcpMindrotPasswordHandler;
import com.ccp.local.testings.implementations.CcpLocalInstances;
import com.ccp.local.testings.implementations.cache.CcpLocalCacheInstances;
import com.vis.entities.VisEntityViewedResume;

/**
 * Apaga, pela entidade ({@code deleteAnyWhere}: principal e gêmea, com os decorators que corrigem os grupos e os
 * contadores do {@code jn_grouper}), as visualizações de um currículo feitas pelos recrutadores informados. Roda contra
 * o Elasticsearch da {@code application_properties} do processo (o .ps1 troca pelo de produção, pelo túnel). O histórico
 * de cada visualização (um grupo do {@code jn_grouper} desde 2026-11-20) sai com ela.
 *
 * <p>Uso: {@code <endereço do LinkedIn do currículo> <e-mail do recrutador> [<e-mail do recrutador>...]}
 */
public class DeleteViewsOfAResume {

	public static void main(String[] args) {
		if(args.length < 2) {
			System.out.println("Uso: <endereco do LinkedIn> <e-mail do recrutador> [...]");
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
		String linkedin = args[0];
		List<String> recruiters = List.of(args).subList(1, args.length);
		int failures = 0;
		for (String recruiter : recruiters) {
			CcpJsonRepresentation key = CcpOtherConstants.EMPTY_JSON
					.put(VisEntityViewedResume.Fields.linkedin, linkedin)
					.put(VisEntityViewedResume.Fields.email, recruiter);
			boolean deleted = VisEntityViewedResume.ENTITY.deleteAnyWhere(key);
			boolean inTheMain = VisEntityViewedResume.ENTITY.exists(key);
			boolean inTheTwin = VisEntityViewedResume.ENTITY.getTwinEntity().exists(key);
			boolean gone = false == inTheMain && false == inTheTwin;
			failures += gone ? 0 : 1;
			System.out.println("recrutador " + (recruiters.indexOf(recruiter) + 1) + ": apagada=" + deleted + " ainda existe=" + (gone ? "nao" : "SIM"));
		}
		System.exit(failures == 0 ? 0 : 2);
	}
}
