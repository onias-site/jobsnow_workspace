import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Stream;

import com.ccp.constants.CcpOtherConstants;
import com.ccp.decorators.CcpJsonFieldName;
import com.ccp.decorators.CcpJsonRepresentation;
import com.ccp.dependency.injection.CcpDependencyInjection;
import com.ccp.especifications.db.bulk.CcpBulkEntityOperationType;
import com.ccp.especifications.db.bulk.CcpBulkItem;
import com.ccp.especifications.db.bulk.CcpBulkScriptedUpdateFields;
import com.ccp.especifications.db.query.CcpQueryOptions;
import com.ccp.especifications.db.utils.entity.CcpEntity;
import com.ccp.especifications.db.utils.entity.decorators.annotations.CcpEntityTwin;
import com.ccp.especifications.db.utils.entity.decorators.engine.CcpEntityMetaData;
import com.ccp.implementations.db.bulk.elasticsearch.CcpElasticSerchDbBulk;
import com.ccp.implementations.db.crud.elasticsearch.CcpElasticSearchCrud;
import com.ccp.implementations.db.query.elasticsearch.CcpElasticSearchQueryExecutor;
import com.ccp.implementations.db.utils.elasticsearch.CcpElasticSearchDbRequest;
import com.ccp.implementations.http.apache.mime.CcpApacheMimeHttp;
import com.ccp.implementations.json.gson.CcpGsonJsonHandler;
import com.ccp.implementations.password.mindrot.CcpMindrotPasswordHandler;
import com.ccp.local.testings.implementations.CcpLocalInstances;
import com.ccp.local.testings.implementations.cache.CcpLocalCacheInstances;
import com.jn.db.bulk.JnExecuteBulkOperation;
import com.jn.entities.JnEntityGrouper;
import com.jn.json.fields.validation.JnJsonCommonsFields;
import com.jn.utils.JnDeleteKeysFromCache;
import com.jn.utils.JnGroupers;
import com.jn.utils.JnVersionableHistory;

/**
 * Leva o histórico das entidades versionáveis do índice {@code jn_versionable} (uma linha por gravação, até 2026-11-20)
 * para os grupos {@code jn_virtual_versionable_history} do {@code jn_grouper} (um grupo por registro, uma versão por
 * gravação, ver {@code JnVersionableHistory}). Roda contra o Elasticsearch da {@code application_properties} do processo
 * (o 104-historico-versionavel-no-grouper.ps1 troca pelo de produção, pelo túnel).
 * <p>
 * O id do registro é calculado pela própria entidade (as classes com {@code @CcpEntityVersionable} dos módulos de
 * negócio, e as gêmeas delas) a partir da chave primária do registro guardado em cada linha. As versões antigas entram
 * no começo do grupo, em ordem de {@code timestamp}, antes das que o código novo já gravou; uma versão que o grupo já
 * tem não entra de novo, então rodar de novo não muda nada.
 * <p>
 * Sem argumento só conta o que levaria. {@code --gravar} grava. {@code --conferir} lê cada grupo e confere que tem
 * todas as versões das linhas (sai com 1 se faltar alguma). Nenhum valor de registro é impresso.
 */
public class MoveVersionableHistoryToGrouper {

	enum Fields implements CcpJsonFieldName {
		olderVersions,
	}

	/** Junta as versões antigas, no começo, às que o grupo já tem, sem repetir. */
	static final String PREPEND_OLDER_VERSIONS = "def merged = new ArrayList(params.olderVersions); "
			+ "for (def c : ctx._source.child) { if (false == merged.contains(c)) { merged.add(c); } } "
			+ "ctx._source.child = merged; ctx._source.childCount = merged.size(); ctx._source.parentJson = params.parentJson;";

	static final int BULK_SIZE = 500;

	public static void main(String[] args) throws Exception {
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
		List<String> arguments = Arrays.asList(args);
		boolean write = arguments.contains("--gravar");
		boolean check = arguments.contains("--conferir");

		Map<String, CcpEntity> entitiesByName = versionableEntitiesByName();
		System.out.println("entidades versionaveis (com as gemeas): " + entitiesByName.size());

		// a leitura por query devolve em "entity" o nome do indice (e em "id" o _id): o nome da entidade de cada linha vem
		// do filtro de cada leitura
		List<CcpJsonRepresentation> everyRow = new ArrayList<>();
		CcpQueryOptions.INSTANCE.matchAll().selectFrom("jn_versionable").consumeQueryResult("2m", 1000, everyRow::add, "timestamp");
		Map<String, List<CcpJsonRepresentation>> rowsByEntity = new LinkedHashMap<>();
		int knownRows = 0;
		for (String entityName : entitiesByName.keySet()) {
			List<CcpJsonRepresentation> entityRows = new ArrayList<>();
			CcpQueryOptions query = CcpQueryOptions.INSTANCE
					.startQuery()
						.startBool()
							.startMust()
								.term(JnJsonCommonsFields.entity, entityName)
							.endMustAndBackToBool()
						.endBoolAndBackToQuery()
					.endQueryAndBackToRequest();
			query.selectFrom("jn_versionable").consumeQueryResult("2m", 1000, entityRows::add, "json", "operation", "date", "timestamp");
			rowsByEntity.put(entityName, entityRows);
			knownRows += entityRows.size();
		}
		System.out.println("linhas no jn_versionable: " + everyRow.size() + "; de entidades versionaveis do codigo: " + knownRows);

		Map<String, List<CcpJsonRepresentation>> rowsByRecord = new LinkedHashMap<>();
		Map<String, String[]> recordByKey = new LinkedHashMap<>();
		Map<String, CcpJsonRepresentation> primaryKeyByKey = new LinkedHashMap<>();
		int unknownRows = everyRow.size() - knownRows;
		int unreadable = 0;
		for (Map.Entry<String, List<CcpJsonRepresentation>> entityRows : rowsByEntity.entrySet())
		for (CcpJsonRepresentation row : entityRows.getValue()) {
			String entityName = entityRows.getKey();
			CcpEntity entity = entitiesByName.get(entityName);
			CcpJsonRepresentation record;
			try {
				String recordAsText = row.getAsString(JnJsonCommonsFields.json);
				record = new CcpJsonRepresentation(recordAsText);
			} catch (RuntimeException e) {
				unreadable++;
				continue;
			}
			CcpEntityMetaData entityDetails = entity.getEntityMetaData();
			CcpJsonRepresentation primaryKey = entityDetails.getPrimaryKeyValues(record.getJsonSupplier());
			String recordId = entity.calculateId(record);
			String key = entityName + "|" + recordId;
			rowsByRecord.computeIfAbsent(key, x -> new ArrayList<>()).add(row.put(JnJsonCommonsFields.json, record));
			recordByKey.put(key, new String[] { entityName, recordId });
			primaryKeyByKey.put(key, primaryKey);
		}
		System.out.println("registros (grupos): " + rowsByRecord.size() + "; linhas de entidade fora do codigo: " + unknownRows
				+ "; linhas com json ilegivel: " + unreadable);

		Map<String, List<String>> versionsByRecord = new LinkedHashMap<>();
		for (Map.Entry<String, List<CcpJsonRepresentation>> entry : rowsByRecord.entrySet()) {
			List<CcpJsonRepresentation> recordRows = entry.getValue();
			recordRows.sort(Comparator.comparingLong(row -> row.getAsLongNumber(JnJsonCommonsFields.timestamp)));
			List<String> versions = new ArrayList<>();
			for (CcpJsonRepresentation row : recordRows) {
				CcpJsonRepresentation version = CcpOtherConstants.EMPTY_JSON
						.put(JnJsonCommonsFields.operation, row.getAsString(JnJsonCommonsFields.operation))
						.put(JnJsonCommonsFields.date, row.getAsString(JnJsonCommonsFields.date))
						.put(JnJsonCommonsFields.timestamp, row.getAsLongNumber(JnJsonCommonsFields.timestamp))
						.put(JnJsonCommonsFields.json, row.getInnerJson(JnJsonCommonsFields.json));
				versions.add(version.asUgglyJson());
			}
			versionsByRecord.put(entry.getKey(), versions);
		}

		if(check) {
			int missingGroups = 0, missingVersions = 0, checked = 0;
			List<String> keys = new ArrayList<>(versionsByRecord.keySet());
			for (int start = 0; start < keys.size(); start += BULK_SIZE) {
				List<String> page = keys.subList(start, Math.min(start + BULK_SIZE, keys.size()));
				List<CcpJsonRepresentation> groupKeys = new ArrayList<>();
				for (String key : page) {
					String[] record = recordByKey.get(key);
					groupKeys.add(JnVersionableHistory.getGroupKey(record[0], record[1]));
				}
				List<List<String>> childrenOfEachGroup = JnGroupers.getChildrenOfEachGroup(groupKeys);
				for (int position = 0; position < page.size(); position++) {
					List<String> children = childrenOfEachGroup.get(position);
					List<String> versions = versionsByRecord.get(page.get(position));
					checked++;
					if(children.isEmpty()) {
						missingGroups++;
						continue;
					}
					for (String version : versions) {
						if(false == children.contains(version)) {
							missingVersions++;
						}
					}
				}
			}
			System.out.println("conferencia: grupos " + checked + ", grupos faltando " + missingGroups + ", versoes faltando " + missingVersions);
			System.exit(missingGroups + missingVersions == 0 ? 0 : 1);
		}

		int versionsCount = versionsByRecord.values().stream().mapToInt(List::size).sum();
		System.out.println("versoes a levar: " + versionsCount);
		if(false == write) {
			System.out.println("nada gravado (use --gravar)");
			return;
		}

		CcpEntity grouper = JnGroupers.getGrouper(false);
		String parentName = JnVersionableHistory.getParentName();
		List<CcpBulkItem> items = new ArrayList<>();
		int written = 0;
		for (Map.Entry<String, List<String>> entry : versionsByRecord.entrySet()) {
			String[] record = recordByKey.get(entry.getKey());
			CcpJsonRepresentation groupKey = JnVersionableHistory.getGroupKey(record[0], record[1]);
			CcpJsonRepresentation parentJson = CcpOtherConstants.EMPTY_JSON
					.put(JnJsonCommonsFields.entity, record[0])
					.put(JnJsonCommonsFields.id, record[1])
					.put(JnVersionableHistory.Fields.primaryKey, primaryKeyByKey.get(entry.getKey()));
			List<String> versions = entry.getValue();
			CcpJsonRepresentation params = CcpOtherConstants.EMPTY_JSON
					.put(Fields.olderVersions, versions)
					.put(JnEntityGrouper.Fields.parentJson, parentJson);
			CcpJsonRepresentation newGroup = groupKey
					.put(JnEntityGrouper.Fields.parentJson, parentJson)
					.put(JnEntityGrouper.Fields.child, versions)
					.put(JnEntityGrouper.Fields.childCount, versions.size());
			CcpJsonRepresentation item = CcpOtherConstants.EMPTY_JSON
					.put(CcpBulkScriptedUpdateFields.script, PREPEND_OLDER_VERSIONS)
					.put(CcpBulkScriptedUpdateFields.params, params)
					.put(CcpBulkScriptedUpdateFields.upsert, newGroup)
					.put(CcpBulkScriptedUpdateFields.scriptedUpsert, false);
			String groupId = grouper.calculateId(groupKey);
			items.add(new CcpBulkItem(item, CcpBulkEntityOperationType.scriptedUpdate, grouper, groupId));
			if(items.size() >= BULK_SIZE) {
				JnExecuteBulkOperation.INSTANCE.executeBulk(items, JnDeleteKeysFromCache.INSTANCE);
				written += items.size();
				items = new ArrayList<>();
				System.out.println("grupos gravados: " + written);
			}
		}
		if(false == items.isEmpty()) {
			JnExecuteBulkOperation.INSTANCE.executeBulk(items, JnDeleteKeysFromCache.INSTANCE);
			written += items.size();
		}
		System.out.println("grupos gravados: " + written + " (rode com --conferir)");
	}

	/** As entidades com {@code @CcpEntityVersionable} dos módulos de negócio, e as gêmeas delas, pelo nome. */
	static Map<String, CcpEntity> versionableEntitiesByName() throws IOException, ReflectiveOperationException {
		Map<String, CcpEntity> entitiesByName = new LinkedHashMap<>();
		List<Path> sources = new ArrayList<>();
		try (Stream<Path> modules = Files.list(Path.of(".."))) {
			for (Path module : modules.filter(m -> m.getFileName().toString().endsWith("_business_jobsnow")).toList()) {
				Path javaFolder = module.resolve("src/main/java");
				if(false == Files.isDirectory(javaFolder)) {
					continue;
				}
				try (Stream<Path> files = Files.walk(javaFolder)) {
					files.filter(f -> f.toString().endsWith(".java")).forEach(f -> sources.add(javaFolder.relativize(f)));
				}
				for (Path relative : new ArrayList<>(sources)) {
					Path file = javaFolder.resolve(relative);
					if(false == Files.exists(file)) {
						continue;
					}
					String text = Files.readString(file);
					if(false == text.contains("@CcpEntityVersionable(")) {
						continue;
					}
					String className = relative.toString().replace(".java", "").replace('\\', '.').replace('/', '.');
					CcpEntity entity = (CcpEntity) Class.forName(className).getField("ENTITY").get(null);
					CcpEntityMetaData entityDetails = entity.getEntityMetaData();
					entitiesByName.put(entityDetails.entityName, entity);
					boolean twin = entityDetails.configurationClass.isAnnotationPresent(CcpEntityTwin.class);
					if(twin) {
						CcpEntity twinEntity = entity.getTwinEntity();
						entitiesByName.put(twinEntity.getEntityMetaData().entityName, twinEntity);
					}
				}
				sources.clear();
			}
		}
		return entitiesByName;
	}
}
