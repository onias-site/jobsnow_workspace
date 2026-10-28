import java.util.Arrays;
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
import com.vis.business.recruiter.resumes.VisBusinessSendResumesToRecruiters;
import com.vis.business.recruiter.resumes.VisRecruiterResumesFields;
import com.vis.entities.VisEntityRecruiter;

/**
 * Faz o papel do agendador do e-mail diário de currículos aos recrutadores ({@code VisBusinessSendResumesToRecruiters}),
 * restrito aos recrutadores passados nos argumentos: grava cada um em {@code vis_recruiter} (fonte "roteiro") e roda o
 * processo só para eles. Os e-mails vão para {@code c:\logs\email\<recrutador>}, com os links assinados de
 * "Ver currículo" e de descadastro.
 *
 * <p>Precisa de {@code recruiterLinksSecret} na variável de ambiente {@code application_properties} e do refresh dos
 * índices antes de rodar (o processo consulta o que acabou de ser gravado):
 * <pre>curl -XPOST "localhost:9200/jn_versionable,vis_resume,vis_recruiter,vis_viewed_resume/_refresh"</pre>
 *
 * <p>Uso (pasta de trabalho em {@code ccp_rest-api-tests_jobsnow}, como o {@code SupportBotCommand.java}):
 * <pre>java @target/create-entities-args.txt ../documentation/roteiros-de-teste/automacao/SendResumesToRecruiters.java a@empresa.com.br b@gmail.com</pre>
 */
public class SendResumesToRecruiters {

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

		List<String> recruiters = Arrays.asList(args);
		for (String email : recruiters) {
			// o validador roda antes dos transformadores: o domínio e o tipo do e-mail vão prontos
			String domain = email.substring(email.indexOf('@') + 1);
			CcpJsonRepresentation recruiter = CcpOtherConstants.EMPTY_JSON
					.put(VisEntityRecruiter.Fields.email, email)
					.put(VisEntityRecruiter.Fields.source, "roteiro")
					.put(VisEntityRecruiter.Fields.domain, domain)
					.put(VisEntityRecruiter.Fields.professional, false == domain.equals("gmail.com"));
			VisEntityRecruiter.ENTITY.save(recruiter);
		}

		CcpJsonRepresentation input = CcpOtherConstants.EMPTY_JSON.put(VisRecruiterResumesFields.recruiters, recruiters);
		CcpJsonRepresentation counters = VisBusinessSendResumesToRecruiters.INSTANCE.execute(input);
		System.out.println("OK " + counters);
		System.exit(0);
	}
}
