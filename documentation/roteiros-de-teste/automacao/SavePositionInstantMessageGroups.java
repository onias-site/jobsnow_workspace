import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

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
import com.ccp.json.validations.fields.annotations.type.CcpJsonFieldTypeNumberUnsigned;
import com.ccp.local.testings.implementations.CcpLocalInstances;
import com.ccp.local.testings.implementations.cache.CcpLocalCacheInstances;
import com.vis.entities.VisEntityPositionInstantMessageGroup;
import com.vis.json.fields.validation.VisJsonCommonsFields;
import com.vis.json.transformers.VisSeniorityType;

/**
 * Grava em {@code vis_position_instant_message_group} os grupos de mensagem instantânea das vagas (2026-11-23): cada grupo
 * cobre uma área ({@code resumeType}), então o chat dele entra no registro de toda senioridade ({@code VisSeniorityType}) e
 * de todo ddd aceito pela vaga ({@code VisJsonCommonsFields.ddd}, inclusive o 10, home office) daquela área. Dois grupos da
 * mesma área ficam juntos na lista {@code chatId}. O bot é o padrão da entidade ({@code user}).
 * <p>
 * Grava pelo {@code save} da entidade, sobrescrevendo: rodar de novo com os mesmos grupos não muda nada. Sem
 * {@code --gravar}, só mostra quantos registros cada área teria.
 * <p>
 * Uso: {@code <resumeType>=<chatId> [<resumeType>=<chatId> ...] [--gravar]}, por exemplo {@code 1=-1001234567890}
 */
public class SavePositionInstantMessageGroups {

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
		boolean write = List.of(args).contains("--gravar");
		Map<Integer, List<Long>> chatsByResumeType = new LinkedHashMap<>();
		for (String arg : args) {
			if (false == arg.contains("=")) {
				continue;
			}
			String[] pair = arg.split("=");
			Integer resumeType = Integer.valueOf(pair[0].trim());
			Long chatId = Long.valueOf(pair[1].trim());
			chatsByResumeType.computeIfAbsent(resumeType, key -> new ArrayList<>()).add(chatId);
		}
		if (chatsByResumeType.isEmpty()) {
			System.out.println("Uso: <resumeType>=<chatId> [<resumeType>=<chatId> ...] [--gravar]");
			System.exit(1);
		}
		long[] ddds = VisJsonCommonsFields.class.getField(VisJsonCommonsFields.ddd.name()).getAnnotation(CcpJsonFieldTypeNumberUnsigned.class).allowedValues();
		VisSeniorityType[] seniorities = VisSeniorityType.values();
		int total = 0;
		for (Map.Entry<Integer, List<Long>> entry : chatsByResumeType.entrySet()) {
			int saved = 0;
			for (VisSeniorityType seniority : seniorities) {
				for (long ddd : ddds) {
					CcpJsonRepresentation group = CcpOtherConstants.EMPTY_JSON
							.put(VisEntityPositionInstantMessageGroup.Fields.seniority, seniority.name())
							.put(VisEntityPositionInstantMessageGroup.Fields.resumeType, entry.getKey())
							.put(VisEntityPositionInstantMessageGroup.Fields.ddd, ddd)
							.put(VisEntityPositionInstantMessageGroup.Fields.chatId, entry.getValue());
					saved++;
					if (false == write) {
						continue;
					}
					VisEntityPositionInstantMessageGroup.ENTITY.save(group);
				}
			}
			total += saved;
			System.out.println("resumeType " + entry.getKey() + ": " + entry.getValue().size() + " chat(s), " + saved + " registros (" + seniorities.length + " senioridades x " + ddds.length + " ddds)" + (write ? " gravados" : " a gravar"));
		}
		System.out.println("total: " + total + (write ? " gravados" : " a gravar (rode com --gravar)"));
	}
}
