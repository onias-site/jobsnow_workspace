# Apoio do 100-visualizacoes-e-login-de-um-recrutador.ps1 (2026-11-20, pedido de apagar em producao as visualizacoes de
# curriculo e o login de curriculos@onias.site, recrutador de teste do proprio usuario). O e-mail chega pela variavel
# RECRUTADOR_EMAIL, nunca por argumento, e nem ele nem os LinkedIns sao impressos.
#   listar <arquivo>: grava no arquivo o LinkedIn legivel de cada visualizacao do recrutador, tirado dos filhos do grupo
#       vis_viewed_resumes_of_the_recruiter do jn_grouper (vis_viewed_resume guarda o LinkedIn como SHA-1); confere que
#       cada SHA-1 bate com uma visualizacao gravada. O executor Java apaga pela entidade com essas chaves.
#   limpar [--gravar]: depois do Java, apaga os
#       grupos jn_login_email das sessoes ja expurgadas (js_login_session_validation, principal e inativo), que nao tem
#       mais registro para a entidade apagar. Mostra o que sobrou do recrutador em cada indice. O historico dos registros
#       apagados (desde 2026-11-20 um grupo jn_virtual_versionable_history do jn_grouper por registro; antes, linhas do
#       jn_versionable) sai junto com cada registro, pelo @CcpEntityVersionablePurge do deleteAnyWhere do Java.
# Uso: RECRUTADOR_EMAIL=<e-mail> ES_DESTINO_AUTH=<Authorization> python 100-...py listar <arquivo> | limpar [--gravar]
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request

target_url = "http://127.0.0.1:9210"
auth = os.environ.get("ES_DESTINO_AUTH", "")
email = os.environ["RECRUTADOR_EMAIL"]
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
RECRUITER_INDICES = ["vis_viewed_resume", "vis_inactive_viewed_resume", "js_login_token", "js_login_token_locked",
                     "js_login_password", "js_login_password_locked", "js_login_answers", "jn_login_email"]


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


email_hash = sha1(email)


def groups(parent_names):
    found = []
    for index in ["jn_grouper", "jn_inactive_grouper"]:
        query = {"size": 10000, "query": {"terms": {"parentName": parent_names}}}
        _, answer = call("POST", "/" + index + "/_search", query)
        for hit in answer.get("hits", {}).get("hits", []):
            parent = hit["_source"].get("parentJson") or {}
            if parent.get("email") == email_hash:
                found.append((index, hit))
    return found


def list_linkedins(output):
    readable = {}
    for _, hit in groups(["vis_viewed_resumes_of_the_recruiter"]):
        for child in hit["_source"].get("child") or []:
            linkedin = json.loads(child)["linkedin"]
            readable[sha1(linkedin)] = linkedin
    query = {"size": 10000, "query": {"term": {"email": email_hash}}, "_source": ["linkedin"]}
    _, answer = call("POST", "/vis_viewed_resume,vis_inactive_viewed_resume/_search", query)
    stored = {hit["_source"]["linkedin"] for hit in answer["hits"]["hits"]}
    matched = sorted(readable[key] for key in stored if key in readable)
    print("visualizacoes gravadas:", len(stored), "| LinkedIns legiveis no grupo:", len(readable), "| sem par:", len(stored) - len(matched))
    with open(output, "w", encoding="utf-8") as target:
        target.write("\n".join(matched))
    return 0 if len(matched) == len(stored) else 2


def clean(write):
    session_groups = [(index, hit) for index, hit in groups(["jn_login_email"])
                      if hit["_source"].get("childName") == "js_login_session_validation"]
    print("grupos de sessao:", [(index, hit["_source"].get("childCount")) for index, hit in session_groups])
    if write:
        for index, hit in session_groups:
            status, _ = call("DELETE", "/" + index + "/_doc/" + hit["_id"] + "?refresh=true")
            print("grupo de sessao apagado em", index, status)
    leftovers = {}
    for index in RECRUITER_INDICES:
        _, answer = call("POST", "/" + index + "/_count", {"query": {"term": {"email": email_hash}}})
        leftovers[index] = answer.get("count")
    print("sobrou do recrutador:", leftovers)
    print("grupos que ainda citam o recrutador:",
          [(index, hit["_source"]["parentName"], hit["_source"].get("childName"), hit["_source"].get("childCount"))
           for index, hit in groups(["vis_viewed_resumes_of_the_recruiter", "jn_login_email"])])
    return 0


mode = sys.argv[1]
if mode == "listar":
    sys.exit(list_linkedins(sys.argv[2]))
sys.exit(clean("--gravar" in sys.argv))
