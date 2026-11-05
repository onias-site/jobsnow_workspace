# Plano: fazer o portal dos painéis funcionar em outra máquina

Escrito em 2026-11-05 para o Claude Code ler e executar numa máquina Windows nova. Siga os passos em ordem: cada um
tem uma **checagem**, e o passo só termina quando ela passa. Se uma checagem falhar e a correção não estiver aqui,
pare e mostre ao usuário o erro exato.

## O que é o sistema

O portal `37-portal-dos-paineis.py` é um servidor Python local (porta 8773) com um menu. Ele carrega como módulos os
8 painéis abaixo e mostra cada um num iframe, sob `/p/<número>/`. Os painéis também funcionam sozinhos, cada um na sua
porta. Todos leem a produção (projeto GCP `jobsnow-prd`) **só para leitura**.

| Menu do portal | Script | Porta própria | Fonte dos dados | Precisa do `producao.json` |
|---|---|---|---|---|
| Monitoria › Cloud › GCP › Memorystore | `30-cache-do-memorystore.py` | 8768 | Cloud Monitoring | não |
| Monitoria › Cloud › GCP › Cloud Run | `27-requisicoes-do-cloud-run.py` | 8765 | Cloud Logging | não |
| Monitoria › Cloud › GCP › Mensagens das filas | `31-mensagens-das-filas.py` | 8769 | Cloud Logging | não |
| Monitoria › Cloud › GCP › Pub/Sub | `29-filas-do-pubsub.py` | 8767 | Cloud Monitoring e Logging | não |
| Monitoria › Cloud › GCP › Compute Engine | `28-maquina-do-compute-engine.py` | 8766 | Cloud Monitoring e Logging (Ops Agent) | não |
| Monitoria › Dados › Elasticsearch › APIs | `34-chamadas-ao-elasticsearch.py` | 8770 | Cloud Logging | não |
| Monitoria › Dados › Elasticsearch › Entidades | `35-gravacoes-das-entidades-das-telas.py` | 8771 | ES de produção por túnel IAP (porta local 9211) | sim (`elasticsearch.secret`) |
| Monitoria › Email › SendGrid | `36-indicadores-do-sendgrid.py` | 8772 | API do SendGrid | sim (`tokenEmailKey`) |
| Cadastros › system_message, instant_message, email, bot | (telas vazias, ainda a fazer) | – | – | – |

Arquivo auxiliar obrigatório: `medicao_elasticsearch.py`, importado pelos painéis 27, 29, 34 e 35.

## Restrições (valem em todos os passos)

- Nunca exibir, imprimir nem copiar para o chat o conteúdo de `C:\segredos\producao.json` nem o valor de qualquer
  segredo. Para checar se uma chave existe, imprima só `True`/`False`.
- Nunca levar o `producao.json` pelo git: só o usuário o copia, por pendrive ou cofre de senhas.
- A produção é só lida: nenhum painel faz escrita, e nada neste plano escreve na produção.
- Não instalar pacotes Python: os painéis usam só a biblioteca padrão.
- Commit e push são do usuário.

## Passo 1. Código

1. O workspace fica em `C:\eclipse-workspaces\ccp`, e os painéis em `documentation\deploy` do repositório
   `onias-site/jobsnow_workspace`. Se a pasta não existir, peça ao usuário para clonar esse repositório nesse caminho.
2. Confira que estes arquivos existem em `C:\eclipse-workspaces\ccp\documentation\deploy`:
   `27-requisicoes-do-cloud-run.py`, `28-maquina-do-compute-engine.py`, `29-filas-do-pubsub.py`,
   `30-cache-do-memorystore.py`, `31-mensagens-das-filas.py`, `34-chamadas-ao-elasticsearch.py`,
   `35-gravacoes-das-entidades-das-telas.py`, `36-indicadores-do-sendgrid.py`, `37-portal-dos-paineis.py`,
   `medicao_elasticsearch.py`.

**Checagem:** os 10 arquivos existem. Se faltar algum, o commit da máquina de origem não chegou: peça ao usuário para
commitar e enviar o `jobsnow_workspace` na outra máquina, ou copiar a pasta à mão. Não recrie os painéis do zero.

## Passo 2. Python

1. Procure um Python 3.10 ou mais novo: `py -3 --version`, `python --version`, e o `pythonw.exe` ao lado dele.
2. Se não houver, peça ao usuário para instalar pelo python.org (marcando "Add python.exe to PATH") ou com
   `winget install Python.Python.3.12`.

**Checagem:** `python -c "import http.server, concurrent.futures, importlib.util; print('ok')"` imprime `ok`, e o
caminho do `pythonw.exe` é conhecido (por exemplo, `python -c "import sys,os; print(os.path.join(os.path.dirname(sys.executable),'pythonw.exe'))"`).

## Passo 3. Google Cloud SDK

1. Os scripts procuram o `gcloud` num caminho fixo:
   `%LOCALAPPDATA%\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd` (constante `GCLOUD` no início de cada script).
2. Se o `gcloud` não estiver instalado, peça ao usuário para instalá-lo **só para o usuário atual** (instalador do
   Google Cloud SDK, opção "Single user"), que usa esse caminho.
3. Se ele estiver em outro lugar (por exemplo, `C:\Program Files (x86)\Google\Cloud SDK\...`), troque a constante
   `GCLOUD` nos 8 scripts por uma busca que use primeiro o PATH e só depois o caminho fixo:
   `GCLOUD = shutil.which("gcloud") or os.path.join(os.environ["LOCALAPPDATA"], "Google", "Cloud SDK", "google-cloud-sdk", "bin", "gcloud.cmd")`
   (com `import shutil`). Isso não muda o comportamento na máquina de origem.

**Checagem:** o `gcloud.cmd` do caminho que os scripts usam responde a `gcloud --version`.

## Passo 4. Login no GCP

1. Peça ao usuário para rodar `! gcloud auth login` (o login abre o navegador e é dele). Use a conta que administra o
   `jobsnow-prd`.
2. `gcloud config set project jobsnow-prd`.
3. Não use `GOOGLE_APPLICATION_CREDENTIALS` nem conta de serviço: os painéis pegam o token com
   `gcloud auth print-access-token`.

**Checagem**, cada comando tem de responder sem erro de permissão:

```
gcloud run services list --project jobsnow-prd --format="value(metadata.name)"
gcloud compute instances list --project jobsnow-prd --format="value(name)"
gcloud pubsub subscriptions list --project jobsnow-prd --format="value(name)" --limit 3
gcloud logging read "resource.type=cloud_run_revision" --project jobsnow-prd --limit 1 --format="value(timestamp)"
```

Esperado: os serviços `jobsnow-js`, `jobsnow-vis` (e o front) e a VM `jobsnow-vm`.

## Passo 5. Túnel IAP (só o painel de Entidades)

O painel 35 abre sozinho um túnel com
`gcloud compute ssh jobsnow-vm --zone southamerica-east1-a --tunnel-through-iap -- -N -L 9211:localhost:9200`.
Na primeira vez numa máquina nova, o `gcloud` gera a chave SSH e pode pedir confirmação.

1. Peça ao usuário para rodar uma vez, de forma interativa:
   `! gcloud compute ssh jobsnow-vm --zone southamerica-east1-a --project jobsnow-prd --tunnel-through-iap --command "echo ok"`
   (aceitando a criação da chave, com senha vazia ou não).
2. A porta local 9211 tem de estar livre.

**Checagem:** o comando acima imprime `ok`.

## Passo 6. Segredos

1. Peça ao usuário para copiar o `producao.json` da máquina de origem para `C:\segredos\producao.json`, pelo meio
   seguro dele. Só os painéis 35 e 36 precisam: sem ele, os outros 6 funcionam e esses dois mostram o erro.
2. Confira sem exibir valores:

```
python -c "import json; d=json.load(open(r'C:\segredos\producao.json',encoding='utf-8')); print('elasticsearch.secret' in d, 'tokenEmailKey' in d)"
```

**Checagem:** imprime `True True`. Se as chaves estiverem aninhadas e der `False`, confira como os scripts 35 e 36 leem o
arquivo (procure `PROPERTIES_FILE`) antes de concluir que falta algo. Nunca imprima o conteúdo.

## Passo 7. Testar o portal numa porta de teste

1. Rode o portal na porta 8790 em segundo plano: `python -X utf8 37-portal-dos-paineis.py 8790`, a partir de
   `documentation\deploy`. Ele abre uma aba no navegador: tudo bem.
2. Faça GET em cada endereço e confira o status 200:

| Endereço | Esperado |
|---|---|
| `/` | página do menu |
| `/p/27/`, `/p/28/`, `/p/29/`, `/p/30/`, `/p/31/`, `/p/34/`, `/p/35/`, `/p/36/` | página de cada painel, com `'/p/<número>'` injetado |
| `/p/27/api/services` | lista com `jobsnow-js` e `jobsnow-vis` |
| `/p/28/api/instances` | `jobsnow-vm` |
| `/p/29/api/subscriptions` | assinaturas do Pub/Sub |
| `/p/30/api/instances` | `jobsnow-cache` |
| `/p/31/api/queues` | tópicos com threads |
| `/p/35/api/indices` | texto no formato do `_cat/indices`, cerca de 90 linhas |
| `/p/36/api/stats?start=<ms de 7 dias atrás>&end=<ms de agora>&by=day` | JSON com `global` e `credits` (start e end em milissegundos desde 1970) |

3. Encerre o processo de teste. Ao encerrar, o portal fecha o túnel do 35.

**Checagem:** tudo 200. Se só o 35 ou o 36 falhar, volte ao passo 5 ou 6. Se uma página `/p/N/` responder 500 com
"nao carregou", o traceback mostra qual import faltou (quase sempre `medicao_elasticsearch.py`, passo 1).

## Passo 8. Atalho na área de trabalho

Crie a pasta `paineis` na área de trabalho e nela o atalho "Portal dos paineis" (PowerShell):

```powershell
$py = "<caminho do pythonw.exe do passo 2>"
$dir = "C:\eclipse-workspaces\ccp\documentation\deploy"
$pasta = Join-Path ([Environment]::GetFolderPath('Desktop')) 'paineis'
New-Item -ItemType Directory -Force $pasta | Out-Null
$s = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $pasta 'Portal dos paineis.lnk'))
$s.TargetPath = $py; $s.Arguments = "`"$dir\37-portal-dos-paineis.py`""; $s.WorkingDirectory = $dir
$s.IconLocation = "C:\Windows\System32\imageres.dll,104"; $s.Save()
```

Com `pythonw`, nenhuma janela de console fica aberta. Se o atalho for clicado com o portal já no ar, ele só abre a
página (a porta não é reaproveitada: `allow_reuse_address = False`).

**Checagem:** clicar no atalho (ou `Start-Process` com os mesmos argumentos) abre http://127.0.0.1:8773 e o menu
aparece. Se a extensão do Chrome estiver disponível, confira pela `javascript_tool` que `#es-entidades` desenha os
gráficos e a lista de índices, e que `#bot` mostra a tela vazia.

## Passo 9. Relatar

Responda ao usuário com uma tabela **Passo** | **Situação** (feito, já estava pronto, ou pendente com o motivo) e o
endereço http://127.0.0.1:8773. Se algum painel ficou sem funcionar, diga qual e por quê.

## Manutenção

- Depois de alterar qualquer painel, encerre o `pythonw.exe` do portal (o processo cuja linha de comando contém
  `37-portal-dos-paineis`) e abra de novo: o portal só carrega os módulos ao subir.
- A cota mensal do SendGrid é a constante `PLAN_MONTHLY_EMAILS` do script 36 (50.000, informada pelo usuário). A API
  devolve outro número, o limite técnico da conta.
- A cota do Cloud Monitoring é de 180 requisições por minuto por usuário. Os painéis reaproveitam respostas por 1 minuto
  e repetem as chamadas que tomarem 429.
- A pasta `__pycache__` gerada em `documentation\deploy` não deve ser versionada.
