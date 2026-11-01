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
import com.vis.business.telegram.VisBusinessLoadTelegramFolder;
import com.vis.business.telegram.VisTelegramLoadFields;

/**
 * A carga dos anúncios do Telegram, sem IA em nenhuma etapa ({@code VisBusinessLoadTelegramFolder}): grava as vagas,
 * carrega os recrutadores, recalcula as estatísticas e o ranking e, por fim, exclui os arquivos confirmados no índice.
 * Lê os {@code .html}/{@code .htm} do Telegram e os {@code .txt} do WhatsApp, cujas vagas entram todas como home office.
 *
 * <p>Uso (rodar pelo {@code executaCargaTelegram.bat}, na raiz do workspace, que monta o classpath):
 * <pre>java -Xmx6g @target/create-entities-args.txt ../documentation/roteiros-de-teste/automacao/LoadTelegramPositions.java C:\z 8 [manter]</pre>
 * O terceiro argumento, {@code manter}, deixa os arquivos na pasta.
 */
public class LoadTelegramPositions {

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

		String folderPath = args[0];
		int threads = Integer.parseInt(args[1]);
		boolean keepFiles = args.length > 2 && "manter".equals(args[2]);

		CcpJsonRepresentation input = CcpOtherConstants.EMPTY_JSON
				.put(VisTelegramLoadFields.folderPath, folderPath)
				.put(VisTelegramLoadFields.threads, threads)
				.put(VisTelegramLoadFields.keepFiles, keepFiles);

		long start = System.currentTimeMillis();
		CcpJsonRepresentation result = VisBusinessLoadTelegramFolder.INSTANCE.execute(input);
		long minutes = (System.currentTimeMillis() - start) / 60_000;
		CcpJsonRepresentation positions = result.getInnerJson(VisTelegramLoadFields.positions);

		System.out.println("Pasta...................: " + folderPath);
		System.out.println("Arquivos lidos..........: " + positions.getAsString(VisTelegramLoadFields.filesRead));
		System.out.println("Mensagens com texto.....: " + positions.getAsString(VisTelegramLoadFields.messagesRead));
		System.out.println("Repetidas no arquivo....: " + positions.getAsString(VisTelegramLoadFields.repeatedMessages));
		System.out.println("Sem contato (descartada): " + positions.getAsString(VisTelegramLoadFields.noContact));
		System.out.println("Sem skill (descartada)..: " + positions.getAsString(VisTelegramLoadFields.noSkill));
		System.out.println("Vagas gravadas..........: " + positions.getAsString(VisTelegramLoadFields.positionsWritten));
		System.out.println("Vagas nao confirmadas...: " + positions.getAsString(VisTelegramLoadFields.notConfirmed));
		System.out.println("Arquivos com falha......: " + positions.getAsStringList(VisTelegramLoadFields.failedFiles));
		System.out.println("Recrutadores............: " + result.getInnerJson(VisTelegramLoadFields.recruiters).asUgglyJson());
		System.out.println("Estatisticas............: " + result.getInnerJson(VisTelegramLoadFields.statistics).asUgglyJson());
		System.out.println("Ranking.................: " + result.getInnerJson(VisTelegramLoadFields.ranking).asUgglyJson());
		System.out.println("Arquivos excluidos......: " + result.getAsString(VisTelegramLoadFields.filesDeleted));
		System.out.println("Minutos.................: " + minutes);
		System.exit(0);
	}
}
