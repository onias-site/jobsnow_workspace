import java.util.List;

import com.ccp.constants.CcpOtherConstants;
import com.ccp.decorators.CcpJsonRepresentation;
import com.ccp.dependency.injection.CcpDependencyInjection;
import com.ccp.especifications.db.bulk.CcpBulkEntityOperationType;
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
import com.jn.entities.JnEntityEmailParametersToSend;
import com.jn.json.fields.validation.JnJsonCommonsFields;
import com.vis.business.position.VisBusinessActivePositionsOfTheFrequency;
import com.vis.business.recruiter.resumes.VisRecruiterResumesTexts;
import com.vis.entities.VisEntityPosition;
import com.vis.entities.VisEntityPositionResumes;
import com.vis.json.fields.validation.VisPositionFrequencyTypes;
import com.vis.messages.VisMessages;

/**
 * Script 116 (2026-11-24): what the sending of the resumes of the positions and the publishing of the positions in the
 * groups need in the Elasticsearch of the application_properties (the local one, or production through the tunnel):
 * <ol>
 * <li>the templates of the two e-mails of the positions (Portuguese and English), as the seeds of
 * {@code VisEntityPositionResumes};</li>
 * <li>their sending parameters, adapted: the sender and the {@code moreParameters} (frontendUrl, oniasLinkedin) copied from
 * the parameters of the daily e-mail to every recruiter of the same Elasticsearch;</li>
 * <li>the system messages of the message of the groups ({@code VisRecruiterResumesTexts.positionPublishing*});</li>
 * <li>with {@code --carga}: every active position saved again, so the decorator puts it in the groups of its days of
 * publishing ({@code vis_virtual_position_publishing_day}); a position that does not pass the validation is reported and
 * skipped.</li>
 * </ol>
 * Without {@code --gravar} it only counts. Idempotent. Prints no personal data.
 */
public class SavePositionSendingSetup {

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
		List<String> arguments = List.of(args);
		boolean write = arguments.contains("--gravar");
		boolean load = arguments.contains("--carga");

		CcpJsonRepresentation dailyKey = CcpOtherConstants.EMPTY_JSON.put(JnJsonCommonsFields.templateId, VisMessages.VisNotifyRecruiterAboutResumes.class.getName());
		CcpJsonRepresentation dailyParameters = JnEntityEmailParametersToSend.ENTITY.getOneById(dailyKey);
		CcpJsonRepresentation dailyMoreParameters = dailyParameters.getInnerJson(JnJsonCommonsFields.moreParameters);

		int templates = 0;
		int parameters = 0;
		List<CcpBulkItem> seeds = VisEntityPositionResumes.INSTANCE.getFirstRecordsToInsert();
		for (CcpBulkItem seed : seeds) {
			// the history of the versions comes with the seeds: the save writes it again
			boolean created = seed.operation == CcpBulkEntityOperationType.create;
			if (false == created) {
				continue;
			}
			boolean isParameters = seed.entity.getEntityMetaData().entityName.equals(JnEntityEmailParametersToSend.ENTITY.getEntityMetaData().entityName);
			if (false == isParameters) {
				templates++;
				if (write) {
					seed.entity.save(seed.json);
				}
				continue;
			}
			// the environment fields come from the parameters of the daily e-mail of the same Elasticsearch
			CcpJsonRepresentation adapted = seed.json
					.put(JnJsonCommonsFields.sender, dailyParameters.getAsString(JnJsonCommonsFields.sender))
					.put(JnJsonCommonsFields.moreParameters, dailyMoreParameters.getJsonPiece(() -> "frontendUrl", () -> "oniasLinkedin"));
			parameters++;
			if (write) {
				seed.entity.save(adapted);
			}
		}
		System.out.println("templates: " + templates + " | parametros: " + parameters + " (frontendUrl do destino: " + dailyMoreParameters.getAsString(() -> "frontendUrl") + ")");

		int texts = 0;
		for (CcpBulkItem seed : VisRecruiterResumesTexts.getSeeds()) {
			boolean ofThePublishing = seed.json.toString().contains("positionPublishing");
			boolean created = seed.operation == CcpBulkEntityOperationType.create;
			if (false == ofThePublishing || false == created) {
				continue;
			}
			texts++;
			if (write) {
				seed.entity.save(seed.json);
			}
		}
		System.out.println("mensagens do sistema: " + texts);

		if (false == load) {
			System.out.println(write ? "gravado (sem --carga, as vagas nao foram regravadas)" : "nada gravado (rode com --gravar)");
			return;
		}
		List<String> everyFrequency = List.of(VisPositionFrequencyTypes.values()).stream().map(Enum::name).toList();
		CcpJsonRepresentation positionsInput = CcpOtherConstants.EMPTY_JSON.put(VisBusinessActivePositionsOfTheFrequency.Fields.frequencyType, everyFrequency);
		List<CcpJsonRepresentation> positions = VisBusinessActivePositionsOfTheFrequency.INSTANCE.execute(positionsInput).getAsJsonList(VisBusinessActivePositionsOfTheFrequency.Fields.positions);
		int saved = 0;
		int refused = 0;
		for (CcpJsonRepresentation position : positions) {
			boolean publish = false == position.containsAllFields(VisEntityPosition.Fields.mustSendInGroups) || position.getAsBoolean(VisEntityPosition.Fields.mustSendInGroups);
			if (false == publish || false == write) {
				continue;
			}
			try {
				VisEntityPosition.ENTITY.save(position);
				saved++;
			} catch (RuntimeException failure) {
				refused++;
				System.out.println("vaga recusada: " + failure.getClass().getSimpleName());
			}
		}
		System.out.println("vagas ativas: " + positions.size() + " | regravadas: " + saved + " | recusadas: " + refused);
	}
}
