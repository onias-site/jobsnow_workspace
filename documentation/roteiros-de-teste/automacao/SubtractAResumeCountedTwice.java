import java.util.List;
import java.util.Map;
import java.util.function.Function;

import com.ccp.constants.CcpOtherConstants;
import com.ccp.decorators.CcpFieldName;
import com.ccp.decorators.CcpJsonRepresentation;
import com.ccp.decorators.CcpReflectionConstructorDecorator;
import com.ccp.dependency.injection.CcpDependencyInjection;
import com.ccp.especifications.db.crud.CcpCrud;
import com.ccp.especifications.db.utils.entity.CcpEntity;
import com.ccp.especifications.db.utils.entity.decorators.annotations.CcpEntityGrouperChildCounter;
import com.ccp.implementations.db.bulk.elasticsearch.CcpElasticSerchDbBulk;
import com.ccp.implementations.db.crud.elasticsearch.CcpElasticSearchCrud;
import com.ccp.implementations.db.query.elasticsearch.CcpElasticSearchQueryExecutor;
import com.ccp.implementations.db.utils.elasticsearch.CcpElasticSearchDbRequest;
import com.ccp.implementations.http.apache.mime.CcpApacheMimeHttp;
import com.ccp.implementations.json.gson.CcpGsonJsonHandler;
import com.ccp.implementations.password.mindrot.CcpMindrotPasswordHandler;
import com.ccp.local.testings.implementations.CcpLocalInstances;
import com.ccp.local.testings.implementations.cache.CcpLocalCacheInstances;
import com.jn.entities.JnEntityVirtualRecordsTotal;
import com.jn.entities.decorators.engine.JnEntityGrouperParents;
import com.jn.utils.JnGroupers;
import com.vis.entities.VisEntityResume;

/**
 * Desconta 1 vez um currículo contado duas vezes nos contadores do {@code jn_grouper}: em 2026-11-15 às 23:47 o mesmo
 * currículo foi salvo duas vezes em 70 ms, e as duas gravações, em threads diferentes da fila, contaram-no como
 * inserção (corrida corrigida em 2026-11-16 pelo {@code CcpMensageriaRecordLocks}). Para cada
 * {@code @CcpEntityGrouperChildCounter} de {@code VisEntityResume} (empresas proibidas, habilidade excluída,
 * habilidades evitadas, tipo, mês, dia e ddd de inserção), calcula os pais e as chaves do registro gravado com as mesmas
 * peças do {@code JnGrouperChildCurrentCounterEntityBeforeWrite} e soma -1 a cada chave; desconta 1 também do total de
 * registros ({@code jn_virtual_records_total}, lado principal).
 * <p>
 * Sem {@code --gravar}, só mostra os contadores e o que mudaria. Com {@code --gravar}, só grava se o total atual do
 * {@code vis_resume} for o informado (o que impede descontar duas vezes ao rodar de novo).
 * <p>
 * Uso: {@code <_id do currículo em vis_resume> <total atual esperado> [--gravar]}
 */
public class SubtractAResumeCountedTwice {

	public static void main(String[] args) {
		if(args.length < 2) {
			System.out.println("Uso: <_id do curriculo> <total atual esperado> [--gravar]");
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
		String resumeId = args[0];
		long expectedTotal = Long.parseLong(args[1]);
		boolean write = List.of(args).contains("--gravar");
		String entityName = VisEntityResume.ENTITY.getEntityMetaData().entityName;
		CcpCrud crud = CcpDependencyInjection.getDependency(CcpCrud.class);
		CcpJsonRepresentation stored = crud.getOneById(entityName, resumeId);
		if(stored.isEmpty()) {
			System.out.println("curriculo nao encontrado em " + entityName);
			System.exit(2);
		}

		String totalParentName = JnEntityVirtualRecordsTotal.ENTITY.getEntityMetaData().entityName;
		String totalParentId = JnEntityVirtualRecordsTotal.getParentId(entityName);
		CcpJsonRepresentation totals = JnGroupers.getCounters(totalParentName, entityName, totalParentId);
		long currentTotal = totals.getAsLongNumber(JnEntityVirtualRecordsTotal.Counters.total);
		System.out.println("total atual de " + entityName + ": " + currentTotal + " (esperado " + expectedTotal + ")");
		if(write && currentTotal != expectedTotal) {
			System.out.println("o total nao e o esperado: nada foi gravado (ja corrigido?)");
			System.exit(3);
		}

		CcpEntity grouper = JnGroupers.getGrouper(false);
		CcpEntityGrouperChildCounter[] countings = VisEntityResume.class.getAnnotationsByType(CcpEntityGrouperChildCounter.class);
		for (CcpEntityGrouperChildCounter counting : countings) {
			CcpReflectionConstructorDecorator counterKeyConstructor = new CcpReflectionConstructorDecorator(counting.counterKeyClass());
			Function<CcpJsonRepresentation, List<String>> counterKeysProducer = counterKeyConstructor.newInstance();
			List<String> keys = counterKeysProducer.apply(stored);
			List<JnEntityGrouperParents> allParents = JnEntityGrouperParents.getAll(counting.value(), VisEntityResume.class);
			for (JnEntityGrouperParents parents : allParents) {
				String parentName = parents.getParentName();
				Map<String, CcpJsonRepresentation> recordParents = parents.getParents(stored);
				for (String parentId : recordParents.keySet()) {
					CcpJsonRepresentation counters = JnGroupers.getCounters(parentName, entityName, parentId);
					CcpJsonRepresentation deltas = CcpOtherConstants.EMPTY_JSON;
					for (String key : keys) {
						deltas = deltas.put(new CcpFieldName(key), -1);
					}
					System.out.println(parentName + " " + recordParents.get(parentId) + " antes " + counters + " desconta " + deltas);
					if(deltas.isEmpty() || false == write) {
						continue;
					}
					JnGroupers.addToCounters(grouper, parentName, entityName, Map.of(parentId, deltas), Map.of(parentId, recordParents.get(parentId)));
					System.out.println("   depois " + JnGroupers.getCounters(parentName, entityName, parentId));
				}
			}
		}

		CcpJsonRepresentation totalDelta = CcpOtherConstants.EMPTY_JSON.put(JnEntityVirtualRecordsTotal.Counters.total, -1);
		CcpJsonRepresentation totalParentJson = JnEntityVirtualRecordsTotal.getParentJson(entityName);
		System.out.println(totalParentName + " " + totalParentJson + " antes " + totals + " desconta " + totalDelta);
		if(false == write) {
			System.out.println("simulacao: nada foi gravado (use --gravar)");
			System.exit(0);
		}
		JnGroupers.addToCounters(grouper, totalParentName, entityName, Map.of(totalParentId, totalDelta), Map.of(totalParentId, totalParentJson));
		System.out.println("   depois " + JnGroupers.getCounters(totalParentName, entityName, totalParentId));
		System.exit(0);
	}
}
