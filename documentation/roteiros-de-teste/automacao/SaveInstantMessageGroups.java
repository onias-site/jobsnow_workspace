import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
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
import com.vis.entities.VisEntityInstantMessageGroup;

/**
 * Grava em {@code vis_instant_message_group} o nome e o link de cada grupo de mensagem instantânea das vagas (2026-11-23),
 * pelo {@code save} da entidade, sobrescrevendo: rodar de novo não muda nada. Sem {@code --gravar}, só mostra as linhas.
 * <p>
 * Arquivo TSV sem cabeçalho, em UTF-8: {@code chatId, title, link}.
 * <p>
 * Uso: {@code <arquivo.tsv> [--gravar]}
 */
public class SaveInstantMessageGroups {

	public static void main(String[] args) throws Exception {
		if (args.length < 1) {
			System.out.println("Uso: <arquivo.tsv> [--gravar]");
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
		boolean write = List.of(args).contains("--gravar");
		List<String> lines = Files.readAllLines(Path.of(args[0]), StandardCharsets.UTF_8).stream().filter(line -> false == line.isBlank()).toList();
		for (String line : lines) {
			String[] columns = line.split("\t");
			CcpJsonRepresentation group = CcpOtherConstants.EMPTY_JSON
					.put(VisEntityInstantMessageGroup.Fields.chatId, Long.valueOf(columns[0].trim()))
					.put(VisEntityInstantMessageGroup.Fields.title, columns[1].trim())
					.put(VisEntityInstantMessageGroup.Fields.link, columns[2].trim());
			System.out.println(columns[0].trim() + " | " + columns[1].trim() + (write ? " | gravado" : " | a gravar"));
			if (false == write) {
				continue;
			}
			VisEntityInstantMessageGroup.ENTITY.save(group);
		}
		System.out.println("total: " + lines.size() + (write ? " gravados" : " a gravar (rode com --gravar)"));
	}
}
