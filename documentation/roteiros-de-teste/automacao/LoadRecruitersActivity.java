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
import com.vis.business.recruiter.VisBusinessLoadRecruitersFromHtmlFolder;
import com.vis.business.recruiter.VisBusinessLoadRecruitersLegacyViews;

/**
 * As datas de atividade dos recrutadores, que ordenam o e-mail diário de currículos: lê os arquivos do Telegram e do
 * WhatsApp da pasta ({@code VisBusinessLoadRecruitersFromHtmlFolder}, que grava {@code lastTelegramAppearance} quando a
 * mensagem mais recente tem até 6 meses e cria o recrutador que ainda não existir) e as visualizações do JobsNow legado
 * ({@code VisBusinessLoadRecruitersLegacyViews}, {@code lastLegacyView}). Não exclui nenhum arquivo.
 *
 * <p>Uso (rodar pelo {@code scripts\executaAtividadeDosRecrutadores.bat}, que monta o classpath):
 * <pre>java @target/create-entities-args.txt ../documentation/roteiros-de-teste/automacao/LoadRecruitersActivity.java C:\z</pre>
 */
public class LoadRecruitersActivity {

	enum Fields implements com.ccp.decorators.CcpJsonFieldName { folderPath }

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
		CcpJsonRepresentation folderInput = CcpOtherConstants.EMPTY_JSON.put(Fields.folderPath, folderPath);

		long start = System.currentTimeMillis();
		CcpJsonRepresentation telegram = VisBusinessLoadRecruitersFromHtmlFolder.INSTANCE.execute(folderInput);
		CcpJsonRepresentation legacy = VisBusinessLoadRecruitersLegacyViews.INSTANCE.execute(CcpOtherConstants.EMPTY_JSON);
		long minutes = (System.currentTimeMillis() - start) / 60_000;

		System.out.println("Telegram/WhatsApp.......: " + telegram.asUgglyJson());
		System.out.println("Legado..................: " + legacy.asUgglyJson());
		System.out.println("Minutos.................: " + minutes);
		System.exit(0);
	}
}
