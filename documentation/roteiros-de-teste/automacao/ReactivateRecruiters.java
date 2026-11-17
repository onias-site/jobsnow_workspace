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
import com.vis.business.recruiter.VisBusinessPrepareRecruiter;
import com.vis.business.recruiter.VisBusinessReactivateRecruiterWhoViewed;
import com.vis.entities.VisEntityRecruiter;

/**
 * Reativa os recrutadores de uma lista de e-mails (pedido de 2026-11-17): cada um que estiver em
 * {@code vis_inactive_recruiter} volta para {@code vis_recruiter} pelo mesmo caminho da visualização de um currículo
 * ({@link VisBusinessReactivateRecruiterWhoViewed}: o delete da gêmea transfere o registro gravado de volta, com os
 * decorators). Feito para os 5 recrutadores que visualizaram durante o envio de 2026-11-17 e foram inativados por engano.
 * Roda contra o Elasticsearch da {@code application_properties} do processo (o .ps1 troca pelo de produção, pelo túnel).
 * Os e-mails nunca são impressos: cada linha sai pelo número.
 * <p>
 * Sem {@code --gravar}, só mostra onde cada e-mail está. Rodar de novo não muda nada (o ativo fica como está).
 * <p>
 * Uso: {@code <arquivo com um e-mail por linha> [--gravar]}
 */
public class ReactivateRecruiters {

	public static void main(String[] args) throws Exception {
		if(args.length < 1) {
			System.out.println("Uso: <arquivo com um e-mail por linha> [--gravar]");
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
		List<String> lines = Files.readAllLines(Path.of(args[0]));
		List<String> emails = lines.stream().map(String::trim).filter(line -> false == line.isEmpty()).toList();
		String loginSource = VisEntityRecruiter.Sources.login.getValue();
		int active = 0, inactive = 0, absent = 0, failures = 0;
		for (int index = 0; index < emails.size(); index++) {
			String email = emails.get(index);
			CcpJsonRepresentation recruiterInput = CcpOtherConstants.EMPTY_JSON
					.put(VisEntityRecruiter.Fields.email, email)
					.put(VisEntityRecruiter.Fields.source, loginSource);
			CcpJsonRepresentation recruiter = VisBusinessPrepareRecruiter.INSTANCE.execute(recruiterInput);
			boolean inTheMain = VisEntityRecruiter.ENTITY.exists(recruiter);
			boolean inTheTwin = VisEntityRecruiter.ENTITY.getTwinEntity().exists(recruiter);
			String before = inTheMain ? "ativo" : inTheTwin ? "inativo" : "ausente";
			active += inTheMain ? 1 : 0;
			inactive += inTheMain ? 0 : inTheTwin ? 1 : 0;
			absent += inTheMain || inTheTwin ? 0 : 1;
			if(false == write || false == inTheTwin) {
				System.out.println((index + 1) + ": " + before);
				continue;
			}
			CcpJsonRepresentation recruiterEmail = CcpOtherConstants.EMPTY_JSON.put(VisEntityRecruiter.Fields.email, email);
			VisBusinessReactivateRecruiterWhoViewed.INSTANCE.execute(recruiterEmail);
			boolean stillActive = VisEntityRecruiter.ENTITY.exists(recruiter);
			boolean nowInactive = VisEntityRecruiter.ENTITY.getTwinEntity().exists(recruiter);
			boolean moved = stillActive && false == nowInactive;
			failures += moved ? 0 : 1;
			System.out.println((index + 1) + ": " + before + " -> " + (moved ? "ativo" : "FALHOU (principal=" + stillActive + ", gemea=" + nowInactive + ")"));
		}
		System.out.println("e-mails: " + emails.size() + ", ativos antes: " + active + ", inativos antes: " + inactive + ", ausentes: " + absent + (write ? ", falhas: " + failures : " (simulacao: use --gravar)"));
		System.exit(failures == 0 ? 0 : 2);
	}
}
