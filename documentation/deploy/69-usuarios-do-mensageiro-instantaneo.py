# Chat do bot user por e-mail (2026-11-13): o chat de cada usuario deixa de ficar no curriculo (vis_resume.chatId) e
# passa a ficar em jn_instant_messenger_user (JnEntityInstantMessengerUser), um registro por e-mail (gravado como hash
# SHA-1) com o chatId. O /receiveMessages grava ali (e apaga o registro do e-mail anterior do mesmo chat), e os avisos
# ao dono do curriculo (visualizacao e LinkedIn invalido) buscam ali o chat pelo e-mail do curriculo.
# Este script leva a producao:
#   1. o indice novo jn_instant_messenger_user, com o mapeamento do arquivo de criacao do local;
#   2. as sementes de 69-sementes-usuarios-do-mensageiro-instantaneo.jsonl (mesmo id do local, regra "igual"): o passo
#      /receiveMessages com o desvio 409 (e-mail ja cadastrado com este chat) e o texto dele em portugues e ingles
#      (jn_system_message);
#   3. a copia dos chats ja gravados nos curriculos (vis_resume e vis_inactive_resume com chatId > 0) para o indice
#      novo, so criando (um registro que ja existe no indice novo nao e tocado). Um chat em mais de um e-mail e
#      copiado para todos e listado no fim.
# Roda ANTES do deploy da API vis e dos consumidores, e de novo LOGO DEPOIS deles, para copiar os chats gravados no
# curriculo pelo codigo antigo nesse intervalo. Idempotente.
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python 69-usuarios-do-mensageiro-instantaneo.py [destino] [--sem-sementes]
#      ou: powershell -File com-tunel-de-producao.ps1 -Script 69-usuarios-do-mensageiro-instantaneo.py
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

INDEX = "jn_instant_messenger_user"
RESUME_INDEXES = ("vis_resume", "vis_inactive_resume")
arguments = [argument for argument in sys.argv[1:] if not argument.startswith("--")]
target_url = arguments[0].rstrip("/") if arguments else "http://127.0.0.1:9210"
without_seeds = "--sem-sementes" in sys.argv
auth = os.environ.get("ES_DESTINO_AUTH", "")
here = os.path.dirname(os.path.abspath(__file__))
create_file = os.path.join(here, "..", "..", "ccp_rest-api-tests_jobsnow", "documentation", "jn", "database",
                           "elasticsearch", "scripts", "entities", "create", INDEX)
seeds_file = os.path.join(here, "69-sementes-usuarios-do-mensageiro-instantaneo.jsonl")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


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


def ccp_id(primary_key):
    # CcpEntity.calculateId: SHA-1 dos valores da chave em ordem de nome, BigInteger com sinal em hexadecimal
    text = ", ".join(str(primary_key[name]) for name in sorted(primary_key))
    digest = hashlib.sha1(text.encode("utf-8")).digest()
    return format(int.from_bytes(digest, "big", signed=True), "x")


def doc_path(index, doc_id):
    return "/%s/_doc/%s" % (index, urllib.parse.quote(doc_id, safe=""))


status, cluster = call("GET", "/")
print("cluster:", cluster.get("cluster_name"))
failures = 0

# 1. indice novo
with open(create_file, encoding="utf-8") as source:
    definition = json.load(source)
status, _ = call("HEAD", "/" + INDEX)
if status == 404:
    status, answer = call("PUT", "/" + INDEX, definition)
    print("criado %s: %s" % (INDEX, status))
    if status != 200:
        print(answer)
        sys.exit(1)
else:
    print("ja existia:", INDEX)
status, mapping = call("GET", "/%s/_mapping" % INDEX)
mappings = mapping[INDEX]["mappings"]
same = mappings.get("properties") == definition["mappings"]["properties"] and mappings.get("dynamic") == "strict"
print("mapeamento igual ao local:", same)
if not same:
    failures += 1

# 2. sementes
if without_seeds:
    print("sementes: puladas (--sem-sementes)")
else:
    with open(seeds_file, encoding="utf-8") as source:
        seeds = [json.loads(line) for line in source if line.strip()]
    for seed in seeds:
        path = doc_path(seed["index"], seed["id"])
        status, answer = call("PUT", path + "?refresh=true", seed["source"])
        status, stored = call("GET", path)
        equal = stored.get("found") and stored["_source"] == seed["source"]
        print("semente %s %s: %s" % (seed["index"], seed["id"], "ok" if equal else "DIFERENTE"))
        if not equal:
            failures += 1

# 3. chats dos curriculos
copied = 0
already = 0
chats = {}
for resume_index in RESUME_INDEXES:
    query = {"size": 1000, "_source": ["email", "chatId"], "query": {"range": {"chatId": {"gt": 0}}}}
    status, answer = call("POST", "/%s/_search" % resume_index, query)
    if status != 200:
        print("falha ao ler %s: %s" % (resume_index, status))
        failures += 1
        continue
    hits = answer["hits"]["hits"]
    print("%s com chat: %d" % (resume_index, len(hits)))
    for hit in hits:
        hashed_email = hit["_source"]["email"]
        chat_id = int(hit["_source"]["chatId"])
        chats.setdefault(chat_id, []).append(hashed_email)
        record = {"email": hashed_email, "chatId": chat_id}
        record_id = urllib.parse.quote(ccp_id({"email": hashed_email}), safe="")
        status, answer = call("PUT", "/%s/_create/%s" % (INDEX, record_id), record)
        if status in (200, 201):
            copied += 1
            continue
        if status == 409:
            already += 1
            continue
        print("falha ao copiar o chat de %s: %s %s" % (hashed_email, status, answer.get("error", {}).get("type")))
        failures += 1
call("POST", "/%s/_refresh" % INDEX)
status, count = call("GET", "/%s/_count" % INDEX)
print("chats copiados: %d, ja existiam: %d, registros no indice: %s" % (copied, already, count.get("count")))
shared = {chat_id: emails for chat_id, emails in chats.items() if len(emails) > 1}
for chat_id, emails in shared.items():
    print("chat %s em %d e-mails: %s" % (chat_id, len(emails), ", ".join(emails)))

print("OK" if failures == 0 else "FALHAS: %d" % failures)
sys.exit(0 if failures == 0 else 1)
