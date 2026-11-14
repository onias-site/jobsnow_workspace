# LinkedIn invalido (2026-11-12): o recrutador reporta, na pagina do curriculo do e-mail, que o LinkedIn nao abre; o
# ticket /verifyLinkedinAddress vai ao operador de suporte, que diz se o recrutador tem razao.
# Este script leva a producao:
#   1. os campos novos: invalidLinkedinAddress (boolean) e chatId (long) em vis_resume e vis_inactive_resume; comment
#      (keyword) em vis_viewed_resume e vis_inactive_viewed_resume (os indices sao dynamic strict);
#   2. o indice novo vis_resume_message (VisEntityResumeMessage), com o mapeamento do arquivo de criacao do local;
#   3. as sementes de 63-sementes-linkedin-invalido.jsonl (com o mesmo id do local): templates de Telegram e de e-mail,
#      parametros de envio, o comando do bot de suporte com passos, mensagens de fim e textos; inclui a mensagem ao dono
#      sobre cada nova visualizacao do curriculo (VisNewViewInYourResume e os textos de VisResumeViewMessages). Regra "igual"
#      sobrescreve; nos parametros ("adaptar") os campos de ambiente (chatId, sender, moreParameters) que ja existirem
#      no destino sao mantidos.
# Roda ANTES do deploy da API vis, dos consumidores e do processo diario (todos leem ou gravam os campos novos).
# Idempotente.
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python 63-linkedin-invalido.py [destino] [--sem-sementes]
#      ou: powershell -File com-tunel-de-producao.ps1 -Script 63-linkedin-invalido.py
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

arguments = [argument for argument in sys.argv[1:] if not argument.startswith("--")]
target_url = arguments[0].rstrip("/") if arguments else "http://127.0.0.1:9210"
without_seeds = "--sem-sementes" in sys.argv
auth = os.environ.get("ES_DESTINO_AUTH", "")
here = os.path.dirname(os.path.abspath(__file__))
create_dir = os.path.join(here, "..", "..", "ccp_rest-api-tests_jobsnow", "documentation", "vis", "database",
                          "elasticsearch", "scripts", "entities", "create")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

NEW_FIELDS = {
    "vis_resume": {"invalidLinkedinAddress": {"type": "boolean"}, "chatId": {"type": "long"}},
    "vis_inactive_resume": {"invalidLinkedinAddress": {"type": "boolean"}, "chatId": {"type": "long"}},
    "vis_viewed_resume": {"comment": {"type": "keyword"}},
    "vis_inactive_viewed_resume": {"comment": {"type": "keyword"}},
}
NEW_INDEX = "vis_resume_message"
# campos de ambiente das entidades de regra "adaptar"
ENVIRONMENT_FIELDS = {
    "jn_instant_messenger_parameters_to_send": ["chatId", "moreParameters"],
    "jn_email_parameters_to_send": ["sender", "moreParameters"],
}


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

# 1. campos novos
for index, fields in NEW_FIELDS.items():
    status, answer = call("PUT", "/%s/_mapping" % index, {"properties": fields})
    status, mapping = call("GET", "/%s/_mapping" % index)
    properties = mapping[index]["mappings"].get("properties", {})
    ok = all(properties.get(name) == definition for name, definition in fields.items())
    failures += 0 if ok else 1
    print("%-28s campos %s: %s" % (index, ",".join(fields), "ok" if ok else "FALHOU %s" % answer))

# 2. indice novo
with open(os.path.join(create_dir, NEW_INDEX), encoding="utf-8") as source:
    definition = json.load(source)
status, _ = call("HEAD", "/" + NEW_INDEX)
if status == 404:
    status, answer = call("PUT", "/" + NEW_INDEX, definition)
    print("criado %s: %s" % (NEW_INDEX, status))
status, mapping = call("GET", "/%s/_mapping" % NEW_INDEX)
mappings = mapping[NEW_INDEX]["mappings"]
same = mappings.get("properties") == definition["mappings"]["properties"] and mappings.get("dynamic") == "strict"
failures += 0 if same else 1
print("%-28s mapeamento igual ao local: %s" % (NEW_INDEX, same))

# 3. sementes
if without_seeds:
    sys.exit(1 if failures else 0)
with open(os.path.join(here, "63-sementes-linkedin-invalido.jsonl"), encoding="utf-8") as seeds_file:
    seeds = [json.loads(line) for line in seeds_file if line.strip()]
for seed in seeds:
    index = seed["index"]
    path = "/%s/_doc/%s" % (index, urllib.parse.quote(seed["id"], safe=""))
    source = dict(seed["source"])
    status, current = call("GET", path)
    kept = []
    for field in ENVIRONMENT_FIELDS.get(index, []):
        if status == 200 and field in current.get("_source", {}):
            source[field] = current["_source"][field]
            kept.append(field)
    status, answer = call("PUT", path + "?refresh=true", source)
    status, written = call("GET", path)
    ok = status == 200 and written.get("_source") == source
    failures += 0 if ok else 1
    print("%-42s %s %s%s" % (index, seed["id"][:40], "ok" if ok else "FALHOU", " (mantidos: %s)" % ",".join(kept) if kept else ""))
print("sementes: %d" % len(seeds))
sys.exit(1 if failures else 0)
