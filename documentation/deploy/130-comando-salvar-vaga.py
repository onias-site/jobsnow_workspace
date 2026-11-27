# Comando /saveJobPosting do bot de suporte (/salvarVaga, 2026-11-26): o operador digita o texto de uma vaga (100 a
# 5000 caracteres), que e salvo na entidade assincrona e descartavel diaria vis_job_posting (PK postId, o SHA-1 do texto
# sem espacos nas pontas e em maiusculas). Antes do save, no consumidor da fila da entidade, rodam as skills do texto
# (skills/fromText), o cruzamento dos grupos de habilidade dos curriculos (vis_virtual_skill_grouper, script 129) e a
# busca de curriculos da tela curriculos/buscar com essas skills obrigatorias, com o texto compartilhado sob
# curriculos@onias.site; o registro guarda a contagem, as medias e o link. Cada vaga e child (texto + id) do grupo de
# vis_virtual_job_posting_hour do dia da gravacao e de uma das horas que ainda vem nele, da proxima ate 23, pelo
# milissegundo: hora + 1 + milissegundo % (23 - hora) (gravada as 19h, de 20 a 23; as 23h, 23).
#
# O que faz:
#   1. cria o indice vis_job_posting com o mapeamento do local
#      (ccp_rest-api-tests_jobsnow/documentation/vis/.../create/vis_job_posting) e confere que ficou igual;
#   2. grava as sementes de 130-sementes-comando-salvar-vaga.jsonl (mesmo id do local, regra "igual"), semeadas por
#      VisEntityJobPosting: o comando, os 2 passos, o nome em portugues, as explicacoes, as mensagens de fim e os textos
#      (jn_system_message), inclusive os da publicacao de hora em hora (VisJobPostingPublishingTexts, job
#      jobsnow-vagas-do-bot-por-hora do script 32, que publica as vagas do grupo da hora nos grupos de tecnologia do bot
#      user).
#
# Filas novas em topicos.tsv: com.vis.entities.VisEntityJobPosting e JbBusinessRunBotCommand~support~saveJobPosting (esta
# com o CcpGcpPubSubMensageriaSender, para que o save va para a fila da entidade em vez de rodar na thread do comando).
#
# Ordem: depois do script 129 (os grupos de habilidade dos curriculos ja gravados); 03-criar-filas.ps1, este script e o
# deploy dos consumidores (o bot le os comandos quando inicia; o cache das entidades do bot dura 1 h) e o /ccp-deploy cron
# (o job novo de hora em hora). Idempotente.
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python 130-comando-salvar-vaga.py [destino]
#      ou: & .\com-tunel-de-producao.ps1 -Script .\130-comando-salvar-vaga.py
#      (sem destino: o tunel de producao, http://127.0.0.1:9210; para o ES local, http://127.0.0.1:9200)
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

arguments = [argument for argument in sys.argv[1:] if not argument.startswith("--")]
target_url = arguments[0].rstrip("/") if arguments else "http://127.0.0.1:9210"
auth = os.environ.get("ES_DESTINO_AUTH", "")
here = os.path.dirname(os.path.abspath(__file__))
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

INDEX = "vis_job_posting"
MAPPING_FILE = os.path.join(here, "..", "..", "ccp_rest-api-tests_jobsnow", "documentation", "vis", "database",
                            "elasticsearch", "scripts", "entities", "create", INDEX)
SEEDS_FILE = os.path.join(here, "130-sementes-comando-salvar-vaga.jsonl")


def call(method, path, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(target_url + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if auth:
        request.add_header("Authorization", auth)
    try:
        with opener.open(request, timeout=60) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"{}")


status, cluster = call("GET", "/")
print("cluster:", cluster.get("cluster_name"))
failures = 0

# 1. o indice
with open(MAPPING_FILE, encoding="utf-8") as mapping_file:
    creation = json.load(mapping_file)
status, _ = call("HEAD", "/" + INDEX)
if status == 404:
    status, answer = call("PUT", "/" + INDEX, creation)
    print("indice", INDEX, "criado" if status == 200 else "FALHOU %s %s" % (status, answer))
else:
    print("indice", INDEX, "ja existia")
status, mapping = call("GET", "/" + INDEX + "/_mapping")
stored = mapping.get(INDEX, {}).get("mappings", {})
same_mapping = stored == creation["mappings"]
failures += 0 if same_mapping else 1
print("mapeamento", "igual ao local" if same_mapping else "DIFERENTE: %s" % json.dumps(stored))

# 2. as sementes do comando
with open(SEEDS_FILE, encoding="utf-8") as seeds_file:
    seeds = [json.loads(line) for line in seeds_file if line.strip()]
for seed in seeds:
    index = seed["index"]
    path = "/%s/_doc/%s" % (index, urllib.parse.quote(seed["id"], safe=""))
    source = seed["source"]
    call("PUT", path + "?refresh=true", source)
    status, written = call("GET", path)
    ok = status == 200 and written.get("_source") == source
    failures += 0 if ok else 1
    print("%-34s %s %s" % (index, seed["id"][:42], "ok" if ok else "FALHOU"))
print("sementes: %d" % len(seeds))
print("OK" if failures == 0 else "FALHAS: %d" % failures)
sys.exit(1 if failures else 0)
