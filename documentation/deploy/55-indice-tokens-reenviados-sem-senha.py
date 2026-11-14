# Cria no destino o indice js_login_token_resent_without_password (2026-11-11): a entidade nova
# JsEntityLoginTokenResentWithoutPassword, gravada pelo processo das 8h (JsBusinessSaveTokensResentWithoutPassword, logo
# depois do reenvio do token) com os e-mails de js_login_token_fulfilled_resend que nao tem senha (e-mail em SHA-1), e
# apagada pela insercao da senha em js_login_password. O mapeamento vem do arquivo de criacao do local
# (ccp_rest-api-tests_jobsnow/documentation/js/.../create/js_login_token_resent_without_password). Sem seeds.
# Roda ANTES do deploy da API js e do job jobsnow-reenvio-token-login: os dois gravam ou apagam no indice.
# Idempotente: se o indice ja existe, so confere o mapeamento.
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python 55-indice-tokens-reenviados-sem-senha.py [destino]
#      ou: powershell -File com-tunel-de-producao.ps1 -Script 55-indice-tokens-reenviados-sem-senha.py
import json
import os
import sys
import urllib.error
import urllib.request

INDEX = "js_login_token_resent_without_password"
target_url = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:9210"
auth = os.environ.get("ES_DESTINO_AUTH", "")
here = os.path.dirname(os.path.abspath(__file__))
create_file = os.path.join(here, "..", "..", "ccp_rest-api-tests_jobsnow", "documentation", "js", "database",
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
sys.exit(0 if same else 1)
