import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

import com.ccp.constants.CcpOtherConstants;
import com.ccp.decorators.CcpJsonRepresentation;
import com.ccp.dependency.injection.CcpDependencyInjection;
import com.ccp.especifications.db.query.CcpQueryOptions;
import com.ccp.implementations.db.bulk.elasticsearch.CcpElasticSerchDbBulk;
import com.ccp.implementations.db.crud.elasticsearch.CcpElasticSearchCrud;
import com.ccp.implementations.db.query.elasticsearch.CcpElasticSearchQueryExecutor;
import com.ccp.implementations.db.utils.elasticsearch.CcpElasticSearchDbRequest;
import com.ccp.implementations.http.apache.mime.CcpApacheMimeHttp;
import com.ccp.implementations.json.gson.CcpGsonJsonHandler;
import com.ccp.implementations.password.mindrot.CcpMindrotPasswordHandler;
import com.ccp.local.testings.implementations.CcpLocalInstances;
import com.ccp.local.testings.implementations.cache.CcpLocalCacheInstances;
import com.vis.business.skill.VisBusinessSkillFixHierarchyItem;
import com.vis.business.skill.VisBusinessSkillSuggestionApply;
import com.vis.entities.VisEntitySkill;
import com.vis.entities.VisEntitySkillApproved;
import com.vis.entities.VisEntitySkillFixHierarchyItemApproved;

/**
 * Executor do script 103 (2026-11-20): aplica no vis_skill, pelos mesmos businesses do bot de suporte (save da
 * entidade, que atualiza os agrupamentos de iniciais do jn_grouper e o dicionario), toda decisao aprovada que ainda nao
 * esta la: cada item de hierarquia aprovado (o parent entra na associacao, sai na desassociacao) e cada sugestao de
 * habilidade aprovada (a skill existe com os sinonimos sugeridos). Sem --gravar so mostra o que falta.
 */
public class ApplyApprovedSkillDecisions {

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
		int failures = 0;

		List<CcpJsonRepresentation> items = new ArrayList<>();
		CcpQueryOptions.INSTANCE.matchAll().selectFrom(VisEntitySkillFixHierarchyItemApproved.ENTITY).consumeQueryResult("1m", 500, items::add);
		for (CcpJsonRepresentation item : items) {
			String label = "item " + item.getAsString(VisEntitySkillFixHierarchyItemApproved.Fields.type) + " "
					+ item.getAsString(VisEntitySkillFixHierarchyItemApproved.Fields.parent) + " / "
					+ item.getAsString(VisEntitySkillFixHierarchyItemApproved.Fields.skill);
			Boolean applied = isItemApplied(item);
			if(applied == null) {
				System.out.println(label + ": skill sem registro em vis_skill (nada a aplicar)");
				continue;
			}
			if(applied) {
				System.out.println(label + ": ja aplicado");
				continue;
			}
			if(false == write) {
				System.out.println(label + ": FALTA aplicar");
				continue;
			}
			VisBusinessSkillFixHierarchyItem.INSTANCE.execute(item);
			boolean nowApplied = Boolean.TRUE.equals(isItemApplied(item));
			System.out.println(label + ": " + (nowApplied ? "aplicado agora" : "FALHOU"));
			failures += nowApplied ? 0 : 1;
		}

		List<CcpJsonRepresentation> suggestions = new ArrayList<>();
		CcpQueryOptions.INSTANCE.matchAll().selectFrom(VisEntitySkillApproved.ENTITY).consumeQueryResult("1m", 500, suggestions::add);
		for (CcpJsonRepresentation suggestion : suggestions) {
			String label = "sugestao " + suggestion.getAsString(VisEntitySkillApproved.Fields.skill);
			boolean applied = isSuggestionApplied(suggestion);
			if(applied) {
				System.out.println(label + ": ja aplicada");
				continue;
			}
			if(false == write) {
				System.out.println(label + ": FALTA aplicar");
				continue;
			}
			VisBusinessSkillSuggestionApply.INSTANCE.execute(suggestion);
			boolean nowApplied = isSuggestionApplied(suggestion);
			System.out.println(label + ": " + (nowApplied ? "aplicada agora" : "FALHOU"));
			failures += nowApplied ? 0 : 1;
		}
		System.out.println(write ? "falhas: " + failures : "(simulacao: use --gravar)");
		System.exit(failures == 0 ? 0 : 2);
	}

	private static CcpJsonRepresentation storedSkill(String skill) {
		CcpJsonRepresentation key = CcpOtherConstants.EMPTY_JSON.put(VisEntitySkill.Fields.skill, skill);
		return VisEntitySkill.ENTITY.getEntityMetaData().getOneByIdOrHandleItIfThisIdWasNotFound(key, notFound -> CcpOtherConstants.EMPTY_JSON);
	}

	/** null = a skill nao tem registro. */
	private static Boolean isItemApplied(CcpJsonRepresentation item) {
		CcpJsonRepresentation stored = storedSkill(item.getAsString(VisEntitySkillFixHierarchyItemApproved.Fields.skill));
		if(stored.isEmpty()) {
			return null;
		}
		List<String> parents = stored.getAsStringList(VisEntitySkill.Fields.parent);
		String parent = item.getAsString(VisEntitySkillFixHierarchyItemApproved.Fields.parent);
		boolean association = "add".equals(item.getAsString(VisEntitySkillFixHierarchyItemApproved.Fields.type));
		return parents.contains(parent) == association;
	}

	private static boolean isSuggestionApplied(CcpJsonRepresentation suggestion) {
		CcpJsonRepresentation stored = storedSkill(suggestion.getAsString(VisEntitySkillApproved.Fields.skill));
		if(stored.isEmpty()) {
			return false;
		}
		Set<String> synonyms = new LinkedHashSet<>(stored.getAsStringList(VisEntitySkill.Fields.synonym));
		List<String> suggested = suggestion.getAsStringList(VisEntitySkillApproved.Fields.synonym);
		return synonyms.containsAll(suggested);
	}
}
