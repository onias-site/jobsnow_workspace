# Mensagens dos grupos do bot support (2026-11-27): desde 2026-11-27 os bots nao executam comandos fora do chat privado
# (o motor respondia cada mensagem de grupo com a lista de comandos). Uma mensagem de texto de um grupo ou supergrupo vai,
# quando o bot tem um business para os seus grupos, a fila com.jb.business.bots.engine.JbBusinessHandleGroupMessage~<bot>
# (1 thread, sender sincrono, linha nova de topicos.tsv), que roda pelo nome da classe o business semeado na entidade nova
# jn_bot_group_message_handler (JnEntityBotGroupMessageHandler, PK botName, campo business). O vis semeia o do bot support,
# VisBusinessSaveTheJobPostingOfTheGroup, que grava a mensagem em vis_instant_message_position_reply (script 132): os 6
# passos da vis_job_posting e a resposta no grupo. O que nao e vaga (texto de menos de 100 caracteres, sem skills, filtros
# repetidos) e ignorado. O bot user nao tem business: as mensagens dos grupos dele so movem o offset.
#
# O que faz:
#   1. cria o indice jn_bot_group_message_handler com o mapeamento do local
#      (ccp_rest-api-tests_jobsnow/documentation/jn/.../create/jn_bot_group_message_handler) e confere que ficou igual;
#   2. grava, com o mesmo id do local (regra "igual"), o registro do bot support
#      (133-sementes-mensagens-dos-grupos-do-bot.jsonl).
#
# Ordem: antes do deploy dos consumidores (sem o registro, as mensagens dos grupos so movem o offset). Idempotente.
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python 133-mensagens-dos-grupos-do-bot.py [destino]
#      ou: & .\com-tunel-de-producao.ps1 -Script .\133-mensagens-dos-grupos-do-bot.py
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

INDEX = "jn_bot_group_message_handler"
MAPPING_FILE = os.path.join(here, "..", "..", "ccp_rest-api-tests_jobsnow", "documentation", "jn", "database",
                            "elasticsearch", "scripts", "entities", "create", INDEX)
SEEDS_FILE = os.path.join(here, "133-sementes-mensagens-dos-grupos-do-bot.jsonl")


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

# 2. o business dos grupos do bot support
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
    print("%-22s %s %s" % (index, seed["id"], "ok" if ok else "FALHOU"))
print("registros: %d" % len(seeds))
print("OK" if failures == 0 else "FALHAS: %d" % failures)
sys.exit(1 if failures else 0)
