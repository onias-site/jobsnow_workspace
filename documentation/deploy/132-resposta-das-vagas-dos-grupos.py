# Resposta do bot support as vagas escritas nos grupos do Telegram (2026-11-27): a entidade sincrona e descartavel diaria
# vis_instant_message_position_reply (PK linkToShowResumes, escrito pelo 4o passo antes do save; groupChatId, o grupo;
# replyTo, a mensagem da vaga)
# roda antes do save os mesmos 6 businesses da vis_job_posting (recrutadores do texto, skills, cruzamento dos grupos de
# habilidade, busca de curriculos, descritivo dos filtros, e-mail aos recrutadores), com as mesmas recusas, que so logam e
# cancelam o save. Depois do save, o bot support responde no grupo a mensagem da vaga com a quantidade de curriculos, as
# medias e o link (VisJobPostingReplyTexts.resumesFound, html); sem curriculo, nao responde.
#
# O que faz:
#   1. cria o indice vis_instant_message_position_reply com o mapeamento do local
#      (ccp_rest-api-tests_jobsnow/documentation/vis/.../create/vis_instant_message_position_reply) e confere que ficou igual;
#   2. grava, com o mesmo id do local (regra "igual"), os 2 textos da resposta em jn_system_message (portugues e ingles),
#      semeados por VisEntityInstantMessagePositionReply (132-sementes-resposta-das-vagas-dos-grupos.jsonl).
#
# Sem fila nova em topicos.tsv: a entidade e sincrona. Nada chama a entidade ainda: as mensagens dos grupos so passam a
# ser gravadas nela quando o roteamento das mensagens de grupo do bot support for feito; ate la este script so prepara o
# indice e os textos. Ordem: antes do deploy dos consumidores que trouxer esse roteamento. Idempotente.
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python 132-resposta-das-vagas-dos-grupos.py [destino]
#      ou: & .\com-tunel-de-producao.ps1 -Script .\132-resposta-das-vagas-dos-grupos.py
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

INDEX = "vis_instant_message_position_reply"
MAPPING_FILE = os.path.join(here, "..", "..", "ccp_rest-api-tests_jobsnow", "documentation", "vis", "database",
                            "elasticsearch", "scripts", "entities", "create", INDEX)
SEEDS_FILE = os.path.join(here, "132-sementes-resposta-das-vagas-dos-grupos.jsonl")


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

# 2. os textos da resposta
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
