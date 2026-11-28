import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

import com.ccp.decorators.CcpJsonRepresentation;
import com.ccp.dependency.injection.CcpDependencyInjection;
import com.ccp.especifications.db.bulk.CcpBulkItem;
import com.ccp.implementations.json.gson.CcpGsonJsonHandler;
import com.vis.entities.VisEntityRecruiterResumes;

/**
 * Grava em jsonl (um registro por linha: index, id e source) as sementes do e-mail dos curriculos de uma vaga
 * (2026-11-27): os templates de VisNotifyRecruiterAboutResumesOfTheJobPosting e de VisNotifyRecruiterAboutResumes (banner
 * novo), os parametros de envio do e-mail da vaga e os 4 textos do assunto (jobPostingSubject*), lidos do
 * getFirstRecordsToInsert de VisEntityRecruiterResumes, com o id que o codigo calcula.
 * Le o ES local so para o historico versionavel das sementes (que fica de fora: so os 3 indices de configuracao).
 * Uso: {@code <arquivo de saida>}
 */
public class DumpJobPostingEmailSeeds {

	public static void main(String[] args) throws Exception {
		CcpDependencyInjection.loadAllDependencies(CcpGsonJsonHandler.INSTANCE,
				com.ccp.implementations.http.apache.mime.CcpApacheMimeHttp.INSTANCE,
				com.ccp.implementations.db.utils.elasticsearch.CcpElasticSearchDbRequest.INSTANCE,
				com.ccp.implementations.db.crud.elasticsearch.CcpElasticSearchCrud.INSTANCE,
				com.ccp.local.testings.implementations.cache.CcpLocalCacheInstances.mock);
		List<String> lines = new ArrayList<>();
		for (CcpBulkItem seed : VisEntityRecruiterResumes.INSTANCE.getFirstRecordsToInsert()) {
			String entityName = seed.entity.getEntityMetaData().entityName;
			String text = seed.json.asUgglyJson();
			boolean configuration = List.of("jn_email_template_message", "jn_email_parameters_to_send", "jn_system_message").contains(entityName);
			if(false == configuration) {
				continue;
			}
			boolean wanted = text.contains("VisNotifyRecruiterAboutResumesOfTheJobPosting")
					|| text.contains("\"com.vis.messages.VisMessages$VisNotifyRecruiterAboutResumes\"") && entityName.equals("jn_email_template_message")
					|| text.contains("VisRecruiterResumesTexts.jobPostingSubject");
			if(false == wanted) {
				continue;
			}
			String line = "{\"index\": \"" + entityName + "\", \"id\": \"" + seed.id + "\", \"source\": " + text + "}";
			lines.add(line);
		}
		Files.write(Path.of(args[0]), lines, StandardCharsets.UTF_8);
		System.out.println("sementes: " + lines.size());
	}
}
