import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

import com.ccp.constants.CcpOtherConstants;
import com.ccp.decorators.CcpJsonRepresentation;
import com.ccp.dependency.injection.CcpDependencyInjection;
import com.ccp.especifications.email.CcpEmailSuppressionList;
import com.ccp.implementations.db.bulk.elasticsearch.CcpElasticSerchDbBulk;
import com.ccp.implementations.db.crud.elasticsearch.CcpElasticSearchCrud;
import com.ccp.implementations.db.query.elasticsearch.CcpElasticSearchQueryExecutor;
import com.ccp.implementations.db.utils.elasticsearch.CcpElasticSearchDbRequest;
import com.ccp.implementations.http.apache.mime.CcpApacheMimeHttp;
import com.ccp.implementations.json.gson.CcpGsonJsonHandler;
import com.ccp.implementations.password.mindrot.CcpMindrotPasswordHandler;
import com.ccp.local.testings.implementations.CcpLocalInstances;
import com.ccp.local.testings.implementations.cache.CcpLocalCacheInstances;
import com.jn.entities.JnEntityEmailSuppressed;
import com.vis.business.recruiter.VisBusinessPrepareRecruiter;
import com.vis.entities.VisEntityRecruiter;

/**
 * Grava em {@code jn_email_suppressed} os endereços que recusaram de vez o e-mail de currículos, mas cuja recusa só chegou
 * à caixa {@code curriculos@onias.site} (o servidor de destino aceitou do SendGrid e devolveu depois, ou o SendGrid a pôs em
 * blocks), de modo que a carga diária das supressões nunca os trouxe (2026-11-19). Grava pelo {@code save} da entidade, com os
 * decorators: a primeira gravação publica o evento e a vis inativa o recrutador
 * ({@code VisBusinessInactivateSuppressedRecruiter}), como na carga diária. Os e-mails nunca são impressos: cada linha sai
 * pelo número.
 * <p>
 * Arquivo TSV sem cabeçalho: {@code email, created (segundos Unix), status (pode ficar vazio), reason}.
 * Sem {@code --gravar}, só mostra a situação de cada linha. Rodar de novo não muda nada (o evento só sai na inserção).
 * <p>
 * Uso: {@code <arquivo.tsv> [--gravar]}
 */
public class SaveEmailSuppressions {

	public static void main(String[] args) throws Exception {
		if(args.length < 1) {
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
		List<String> lines = Files.readAllLines(Path.of(args[0])).stream().filter(line -> false == line.isBlank()).toList();
		String listName = CcpEmailSuppressionList.bounces.name();
		String loginSource = VisEntityRecruiter.Sources.login.getValue();
		int alreadySuppressed = 0, saved = 0, failures = 0;
		for (int index = 0; index < lines.size(); index++) {
			String[] columns = lines.get(index).split("\t", -1);
			String email = columns[0].trim().toLowerCase();
			long created = Long.parseLong(columns[1].trim());
			String status = columns.length > 2 ? columns[2].trim() : "";
			String reason = columns.length > 3 ? columns[3].trim() : "";
			CcpJsonRepresentation suppression = CcpOtherConstants.EMPTY_JSON
					.put(JnEntityEmailSuppressed.Fields.email, email)
					.put(JnEntityEmailSuppressed.Fields.created, created)
					.put(JnEntityEmailSuppressed.Fields.suppressionList, listName);
			suppression = status.isEmpty() ? suppression : suppression.put(JnEntityEmailSuppressed.Fields.status, status);
			suppression = reason.isEmpty() ? suppression : suppression.put(JnEntityEmailSuppressed.Fields.reason, reason);

			CcpJsonRepresentation recruiterInput = CcpOtherConstants.EMPTY_JSON
					.put(VisEntityRecruiter.Fields.email, email)
					.put(VisEntityRecruiter.Fields.source, loginSource);
			CcpJsonRepresentation recruiter = VisBusinessPrepareRecruiter.INSTANCE.execute(recruiterInput);
			String recruiterBefore = recruiterState(recruiter);
			boolean suppressedBefore = JnEntityEmailSuppressed.ENTITY.exists(suppression);
			alreadySuppressed += suppressedBefore ? 1 : 0;
			if(false == write || suppressedBefore) {
				System.out.println((index + 1) + ": suprimido=" + suppressedBefore + ", recrutador " + recruiterBefore);
				continue;
			}
			JnEntityEmailSuppressed.ENTITY.save(suppression);
			boolean suppressedAfter = JnEntityEmailSuppressed.ENTITY.exists(suppression);
			String recruiterAfter = recruiterState(recruiter);
			boolean ok = suppressedAfter && false == "ativo".equals(recruiterAfter);
			saved += suppressedAfter ? 1 : 0;
			failures += ok ? 0 : 1;
			System.out.println((index + 1) + ": gravado=" + suppressedAfter + ", recrutador " + recruiterBefore + " -> " + recruiterAfter + (ok ? "" : " FALHOU"));
		}
		System.out.println("linhas: " + lines.size() + ", ja suprimidos: " + alreadySuppressed + (write ? ", gravados: " + saved + ", falhas: " + failures : " (simulacao: use --gravar)"));
		System.exit(failures == 0 ? 0 : 2);
	}

	private static String recruiterState(CcpJsonRepresentation recruiter) {
		boolean inTheMain = VisEntityRecruiter.ENTITY.exists(recruiter);
		boolean inTheTwin = VisEntityRecruiter.ENTITY.getTwinEntity().exists(recruiter);
		return inTheMain ? "ativo" : inTheTwin ? "inativo" : "ausente";
	}
}
