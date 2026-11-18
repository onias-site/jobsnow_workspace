# Cria no destino o indice vis_recruiter_unsubscribed (2026-11-18): a entidade nova VisEntityRecruiterUnsubscribed, gravada
# pela API vis a cada clique no link de descadastro do e-mail de curriculos (UnsubscribeFromResumesEmail), mesmo quando o
# recrutador ja estava inativo. Antes so havia a mudanca para vis_inactive_recruiter, igual a inativacao do processo diario.
# O mapeamento vem do arquivo de criacao do local (ccp_rest-api-tests_jobsnow/documentation/vis/.../create/<indice>).
# Depois grava os 8 recrutadores que clicaram no link entre 2026-11-16 e 2026-11-18, achados nos logs de requisicao da API
# vis (POST /recruiter-email-link/unsubscribe com 200): os ids abaixo sao os _id de vis_recruiter = SHA-1 do e-mail, que
# e o campo email desta entidade; o _id do registro e o SHA-1 desse campo (a regra AEI, como em vis_recruiter_first_email).
# Confere que cada um existe em vis_inactive_recruiter. Nenhum e-mail em claro e lido ou impresso.
# Roda ANTES do deploy da API vis (a API grava no indice).
# Idempotente: indice existente so tem o mapeamento conferido; registro existente e regravado igual.
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python 95-recrutadores-descadastrados.py [destino]
#      ou: powershell -File com-tunel-de-producao.ps1 -Script 95-recrutadores-descadastrados.py
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request

INDEX = "vis_recruiter_unsubscribed"
ALREADY_UNSUBSCRIBED = [
    "76790e3603d8bd301b31448b953f8cf864ec5680",
    "7a37abf1bd64ccd4cf196f1b4a5f46425d1ca7c8",
    "3026f022564ad540bdbcc8037ca6be4e2ce50c0c",
    "bb5a50e8c7e5952373d90c4653b1339cc17b51e",
    "-7ea463b12a8e6fc58caf493bc2e8ba7580e6c1b6",
    "7bf1b4b533eed631514af7508ffcbd8f334b0691",
    "-3acbd02d171c6cc98a0a4229fdbb53e92d7c48c6",
    "58ac9c6af4b8497dcc021331740eef237d0b2bb3",
]
target_url = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:9210"
auth = os.environ.get("ES_DESTINO_AUTH", "")
here = os.path.dirname(os.path.abspath(__file__))
create_file = os.path.join(here, "..", "..", "ccp_rest-api-tests_jobsnow", "documentation", "vis", "database",
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


def sha1(text):
    # o formato do Java: BigInteger com sinal em base 16
    digest = hashlib.sha1(text.encode("utf-8")).digest()
    number = int.from_bytes(digest, "big", signed=True)
    return format(number, "x")


with open(create_file, encoding="utf-8") as source:
    definition = json.load(source)
expected = definition["mappings"]["properties"]

status, _ = call("HEAD", "/" + INDEX)
if status == 404:
    status, answer = call("PUT", "/" + INDEX, definition)
    print("criado:", status, answer.get("acknowledged"))
    if status != 200:
        print(answer)
        sys.exit(1)
else:
    print("ja existia:", INDEX)

status, mapping = call("GET", "/" + INDEX + "/_mapping")
properties = mapping[INDEX]["mappings"].get("properties", {})
dynamic = mapping[INDEX]["mappings"].get("dynamic")
same = properties == expected and dynamic == "strict"
print("mapeamento igual ao local:", same, properties, "dynamic:", dynamic)
if not same:
    sys.exit(1)

failures = 0
for email_hash in ALREADY_UNSUBSCRIBED:
    inactive_status, _ = call("HEAD", "/vis_inactive_recruiter/_doc/" + email_hash)
    record_id = sha1(email_hash)
    status, answer = call("PUT", "/" + INDEX + "/_doc/" + record_id + "?refresh=true", {"email": email_hash})
    read_status, read = call("GET", "/" + INDEX + "/_doc/" + record_id)
    stored = read.get("_source", {}).get("email") == email_hash
    ok = status in (200, 201) and read_status == 200 and stored
    failures += 0 if ok else 1
    print("%s... gravado=%s inativo=%s" % (email_hash[:10], ok, inactive_status == 200))

status, count = call("GET", "/" + INDEX + "/_count")
print("registros em", INDEX + ":", count.get("count"), "| falhas:", failures)
sys.exit(1 if failures else 0)
