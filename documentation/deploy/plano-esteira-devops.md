# Plano da esteira DevOps (GitHub Actions → Cloud Run, VM e Elasticsearch)

Situação em 2026-11-05: plano, nada implementado. Hoje o deploy roda da máquina do usuário (`/ccp-deploy`, `07-publicar-na-vm.ps1`, `08-publicar-cloud-run.ps1`, scripts numerados pelo túnel, `C:\segredos\producao.json`). A esteira faz os mesmos passos no GitHub Actions.

## Três particularidades do projeto

1. **29 repositórios e nenhum repositório Maven**: os jars só existem no `~/.m2` local, então nenhum repositório de módulo compila sozinho no GitHub.
2. **O ES de produção só é acessível dentro da VPC**: do runner do GitHub só se chega a ele por IAP ou por algo rodando dentro da VPC.
3. **Os 29 repositórios são públicos**: a autenticação no GCP precisa de cuidado.

## 1. Onde mora a esteira

No `jobsnow_workspace`, que já tem o `pom.xml` agregador e o `documentation/deploy`.

- Cada repositório de módulo ganha um workflow mínimo: um push na `main` dispara um `repository_dispatch` para o `jobsnow_workspace`.
- O workflow central clona os 29 repositórios na `main` e roda `mvn clean install` da raiz, igual ao local.
- Ele grava um **manifesto da release** (`release.json`, com o SHA de cada repositório) e marca as imagens com esse id. Isso dá rastreabilidade e rollback.
- A CI só compila o que foi commitado: acaba o `git stash` para montar o jar de produção com trabalho em andamento.

Alternativa descartada por ora: publicar cada módulo no Artifact Registry (Maven) ou no GitHub Packages. Exige versionar e publicar 29 artefatos.

## 2. Autenticação no GCP

- **Workload Identity Federation**, sem chave JSON. A condição do provedor restringe a `repository_owner == 'onias-site'`, à branch `main` e ao environment `producao`.
- Conta `github-deployer@jobsnow-prd` com estes papéis: `run.developer`, `artifactregistry.writer`, `iam.serviceAccountUser` sobre a `jobsnow-vm@`, `iap.tunnelResourceAccessor`, `compute.osAdminLogin` e `cloudbuild.builds.editor`. As concessões ficam com o usuário, num script `01d` no padrão do `01b`.
- O environment `producao` do GitHub tem o usuário como aprovador obrigatório. Pull request de fork nunca recebe credencial.
- O `producao.json` vai para o **Secret Manager**. O Cloud Run já o lê de lá (`-SoSegredo`); a VM passa a buscá-lo também, em vez de receber por `scp`.

## 3. Etapas

| # | Etapa | Como | Bloqueia se |
|---|---|---|---|
| 1 | Build | checkout dos 29 → `mvn install` → manifesto | não compila |
| 2 | Testes | compilação e testes que não dependem de nada externo; depois, ES 9.5.5 como *service container* + `CcpCreateEntities` | falha |
| 3 | Imagens | `api.Dockerfile` (vis, js), front com os `--build-arg`, `processo-diario.Dockerfile` → Artifact Registry, tag = id da release | — |
| 4 | **Aprovação** | environment `producao` | o usuário não aprova |
| 5 | Snapshot do ES | snapshot nomeado com a release no `gs://jobsnow-backup` | snapshot falha |
| 6 | Migrações *pré* | ver a seção 4 | migração falha |
| 7 | `checar-producao.py` | os passos 1 a 4 contra produção | sai com 1 |
| 8 | Filas | `03-criar-filas` (idempotente) a partir do `topicos.tsv` | — |
| 9 | Cloud Run | `gcloud run deploy --no-traffic --tag cand` → teste rápido na URL `cand---` → migra 100% do tráfego; mantém o mínimo de 1 instância na js | teste rápido falha |
| 10 | VM | jar dos consumidores no GCS → SSH por IAP → script no estilo do `07-publicar-na-vm.sh`, que baixa do GCS e roda `pm2 reload` | o PM2 não sobe |
| 11 | Processo diário | `gcloud run jobs update --image` (o agendamento continua pausado) | — |
| 12 | Migrações *pós* | apagar índices que saíram do código | — |
| 13 | Cache | invalidar no Valkey as chaves das entidades migradas, para não esperar a 1 hora | — |

**Rollback:** no Cloud Run é voltar o tráfego para a revisão anterior. Na VM é reaplicar o manifesto anterior (o jar fica no GCS por release). No ES é o snapshot da etapa 5, só em último caso: produção escreve o tempo todo.

## 4. Mudança de índice no ES

Automatiza as regras da skill `ccp-transporte-para-producao`.

**a) Os scripts numerados viram migrações registradas.**
- Cada script declara no cabeçalho a sua fase (`pre` ou `pos`).
- Uma tabela de controle (por exemplo, o índice `jn_deploy_migration`, id = nome do script) registra o que já rodou. A esteira roda só os pendentes, em ordem.
- Os scripts já são idempotentes; o registro só evita rodá-los à toa.

**b) Onde rodam:** num **Cloud Run Job** `jobsnow-migracoes` ligado à VPC, como o processo diário: imagem Python com `documentation/deploy`, direto em `10.20.0.2:9200`. Sem túnel nem SSH, com log no Cloud Logging.

**c) Ajuste nos scripts que hoje copiam do ES local:** os de regra `igual` e `adaptar` usam o local como origem, e na CI não há ES local com esses dados. Passam a ler os dados de arquivos versionados, como o `16-sementes-solve-stack-trace.jsonl`. Os campos de ambiente do `adaptar` vêm do Secret Manager. As cargas (`10`, `11`, `21`) ficam fora da esteira, como workflow manual (`workflow_dispatch`).

**d) Cada tipo de mudança:**

| Mudança | Fase | Como |
|---|---|---|
| Entidade ou gêmea nova | pré | `PUT /<indice>` com o mapeamento do `scripts/entities/create` + sementes |
| Campo novo | pré | `PUT /<indice>/_mapping`; obrigatório, porque os índices são `dynamic: strict` |
| Registro de configuração novo ou alterado | pré | carga com o mesmo `_id` |
| Classe renomeada que está gravada em registro | **junto** | regrava os registros e recalcula o `_id` (AEI); roda logo antes de mudar o tráfego |
| Tipo de campo mudado | pré | reindexação: cria `<indice>_v2`, bloqueia escrita no antigo (`index.blocks.write`), `_reindex`, apaga o antigo e cria o **alias** `<indice>` → `<indice>_v2` na mesma chamada `_aliases`. O código continua usando o nome; a escrita fica parada alguns segundos nos índices pequenos |
| Campo retirado | — | não precisa mexer: fica no mapeamento sem uso; sai de vez só numa reindexação |
| Entidade eliminada | pós | confere o snapshot do dia e depois `DELETE` |

O `checar-producao.py` na etapa 7 garante que nenhuma divergência passe sem script.

## 5. Custo e ordem de implementação

- O GitHub Actions é gratuito para repositório público; o build Maven dos 29 repositórios cabe nos limites.
- Ordem:
  1. Workload Identity Federation (`01d`) e o build com manifesto, só CI.
  2. Cloud Run com revisão candidata.
  3. VM via GCS e IAP.
  4. Job de migrações com a tabela de controle.
  5. ES em container nos testes.
- O `/ccp-deploy` vira `gh workflow run deploy.yml -f alvos=vis,js`.
