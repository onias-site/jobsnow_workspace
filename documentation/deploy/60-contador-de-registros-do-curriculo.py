# Contador de registros das entidades (2026-11-12): cria no destino o indice jn_records_count (entidade nova
# JnEntityRecordsCount, mapeamento do arquivo de criacao do local) e grava a contagem atual de vis_resume (ativos) e
# vis_inactive_resume (inativos). Depois do deploy da vis e dos consumidores, o decorator de @CcpEntityRecordsCounter
# (JnRecordsCounterEntity) reconta as duas pontas a cada inclusao, inativacao, reativacao e exclusao de curriculo.
# Roda ANTES do deploy da vis e dos consumidores: eles gravam no indice.
# Idempotente: se o indice ja existe, so confere o mapeamento; a contagem e sempre regravada.
# Uso: powershell -File com-tunel-de-producao.ps1 -Script 60-contador-de-registros-do-curriculo.py
#      ou: ES_DESTINO_AUTH=<valor> python 60-contador-de-registros-do-curriculo.py [destino]
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

INDEX = "jn_records_count"
MAIN = "vis_resume"
TWIN = "vis_inactive_resume"
target_url = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:9210"
auth = os.environ.get("ES_DESTINO_AUTH", "")
here = os.path.dirname(os.path.abspath(__file__))
create_file = os.path.join(here, "..", "..", "ccp_rest-api-tests_jobsnow", "documentation", "jn", "database",
                           "elasticsearch", "scripts", "entities", "create", INDEX)
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def call(method, path, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(target_url + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if auth:
        request.add_header("Authorization", auth)
    try:
        with opener.open(request) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"{}")


def ccp_id(primary_key):
    # CcpEntity.calculateId: SHA-1 dos valores da chave em ordem de nome, BigInteger com sinal em hexadecimal
    text = ", ".join(str(primary_key[name]) for name in sorted(primary_key))
    digest = hashlib.sha1(text.encode("utf-8")).digest()
    return format(int.from_bytes(digest, "big", signed=True), "x")


with open(create_file, encoding="utf-8") as file:
    definition = json.load(file)
expected = definition["mappings"]["properties"]

status, _ = call("GET", "/" + INDEX + "/_mapping")
if status == 404:
    status, answer = call("PUT", "/" + INDEX, definition)
    if status != 200:
        print("falha ao criar o indice:", status, answer)
        sys.exit(1)
    print("indice criado:", INDEX)
else:
    status, mapping = call("GET", "/" + INDEX + "/_mapping")
    properties = mapping[INDEX]["mappings"].get("properties", {})
    missing = [name for name in expected if name not in properties]
    if missing:
        print("mapeamento sem os campos:", missing)
        sys.exit(1)
    print("indice ja existia, mapeamento conferido:", INDEX)

counts = {}
for index in (MAIN, TWIN):
    call("POST", "/" + index + "/_refresh")
    status, answer = call("GET", "/" + index + "/_count")
    if status != 200:
        print("falha ao contar", index, status)
        sys.exit(1)
    counts[index] = answer["count"]

record = {"entityName": MAIN, "twinEntityName": TWIN, "mainRecords": counts[MAIN], "twinRecords": counts[TWIN]}
record_id = ccp_id({"entityName": MAIN})
status, answer = call("PUT", "/" + INDEX + "/_doc/" + urllib.parse.quote(record_id, safe="") + "?refresh=true", record)
if status not in (200, 201):
    print("falha ao gravar a contagem:", status, answer.get("error", {}).get("type"))
    sys.exit(1)

print("entidade\tativos\tinativos")
print(f"{MAIN}\t{counts[MAIN]}\t{counts[TWIN]}")
print("OK")
