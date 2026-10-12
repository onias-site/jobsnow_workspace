import com.ccp.business.CcpBusiness;
import com.ccp.decorators.CcpJsonRepresentation;
import com.ccp.decorators.CcpStringDecorator;
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
import com.jb.business.bots.engine.JbBotType;

/**
 * Faz o papel do operador do suporte sem o Telegram: entrega ao bot de suporte um comando, do jeito que o leitor
 * do Telegram entregaria, e roda o bot neste processo. As respostas do bot vão para
 * {@code c:\logs\telegram\support-751717896.txt} (o "Telegram" local) e os e-mails para {@code c:\logs\email}.
 *
 * <p>As dependências são as do leitor do bot ({@code JbInstantMessengerDependencyChooser}), trocando o Telegram pelo
 * arquivo local. O cache é o mock, como no leitor: nunca lê dado velho e, ao apagar, grava a marca de exclusão que
 * faz as APIs locais descartarem o que tinham guardado.
 *
 * <p>Uso (pasta de trabalho em {@code ccp_rest-api-tests_jobsnow}, depois de um {@code executaCcpCreateEntities.bat},
 * que gera o arquivo de argumentos com o classpath):
 * <pre>java @target/create-entities-args.txt ../documentation/roteiros-de-teste/automacao/SupportBotCommand.java "/solveLoginTokenTicket unlockToken x@teste.com"</pre>
 */
public class SupportBotCommand {

	public static void main(String[] args) {
		String command = String.join(" ", args);

		CcpDependencyInjection.loadAllDependencies(
				new CcpGsonJsonHandler(),
				CcpLocalInstances.email,
				CcpLocalInstances.instantMessenger,
				CcpLocalInstances.syncMensageriaListener,
				CcpLocalCacheInstances.mock,
				new CcpMindrotPasswordHandler(),
				new CcpElasticSerchDbBulk(),
				new CcpApacheMimeHttp(),
				new CcpElasticSearchDbRequest(),
				new CcpElasticSearchCrud(),
				new CcpElasticSearchQueryExecutor()
		);

		long now = System.currentTimeMillis();
		String escapedCommand = command.replace("\\", "\\\\").replace("\"", "\\\"");
		String message = "{"
				+ "\"botName\": \"support\","
				+ "\"chatId\": 751717896,"
				+ "\"message_id\": " + (now % 1000000) + ","
				+ "\"sentAt\": " + (now / 1000) + ","
				+ "\"updateId\": " + now + ","
				+ "\"userName\": \"OniasJr\","
				+ "\"message\": \"" + escapedCommand + "\""
				+ "}";

		CcpJsonRepresentation json = new CcpStringDecorator(message).json();
		CcpBusiness supportBot = JbBotType.support.getBot();
		supportBot.execute(json);
		System.out.println("OK " + command);
		System.exit(0);
	}
}
