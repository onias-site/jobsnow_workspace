# Restricao dos curriculos com dominios invalidos em notAllowedCompany (2026-11-12).
# O campo "Empresas / consultorias que nao podem receber o meu linkedin" (vis_resume.notAllowedCompany) so ganhou a
# validacao de dominio depois que parte dos curriculos ja estava gravada. Um item invalido faz o filtro das consultorias
# proibidas falhar em silencio, e o curriculo poderia chegar a quem o dono proibiu.
# Este script:
#   1. cria o indice vis_resume_restriction (VisEntityResumeRestriction) com o mapeamento do local, se faltar;
#   2. varre vis_resume e valida cada item de notAllowedCompany com a mesma regra da entidade (regex + 4 a 50 caracteres);
#   3. com --gravar, grava uma restricao por curriculo com itens invalidos: _id = _id do curriculo (os dois sao o hash do
#      hash do e-mail), email = hash gravado no curriculo, message = [texto que o formulario mostra em vermelho].
# Sem --gravar, so lista e nao escreve nada. Idempotente: regravar so sobrescreve a mesma restricao.
# Cuidado: uma restricao regravada depois que o dono ja corrigiu o curriculo volta a bloquea-lo; rode de novo so se
# quiser rever. A restricao e apagada pelo proprio sistema quando o dono atualiza o curriculo (afterUpdate).
# Ordem: roda ANTES ou JUNTO com o deploy da API vis e do processo diario (a API antiga nao conhece o indice, mas tambem
# nao o le). Depois de gravar: cache de 1 hora; publique nova revisao da vis ou espere a hora passar.
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python -X utf8 65-restricao-de-curriculo.py [destino] [--gravar]
#      ou: powershell -File com-tunel-de-producao.ps1 -Script 65-restricao-de-curriculo.py [-Argumentos --gravar]
# --inativos varre vis_inactive_resume (a gemea) em vez de vis_resume: o id da restricao e o mesmo nas duas pontas, e
# o update do curriculo inativo tambem a libera. Rodado em producao assim em 2026-11-13.
import json
import os
import re
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

INDEX = "vis_resume_restriction"
RESUME_INDEX = "vis_inactive_resume" if "--inativos" in sys.argv else "vis_resume"
FIELD = "notAllowedCompany"
DOMAIN = re.compile(r"^([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,63}$")
MESSAGE = ("No campo 'Empresas / consultorias que não podem receber o meu linkedin' você cadastrou os seguintes "
           "registros de forma incorreta {}, por favor, corrija este campo, pois não podemos enviar seu currículo para os "
           "recrutadores, pois, tememos enviar para quem não podemos enviar. O domínio deve ter o formato "
           "nomeDaConsultoria.com, nomeDaConsultoria.com.br ou .org, enfim, tem que ser um domínio válido. Pedimos "
           "desculpas, pois esta validação veio apenas depois que vocês inseriram os curriculos na base.")
MAX_MESSAGE = 2000

args = [arg for arg in sys.argv[1:] if not arg.startswith("--")]
write = "--gravar" in sys.argv
target_url = args[0].rstrip("/") if args else "http://127.0.0.1:9210"
auth = os.environ.get("ES_DESTINO_AUTH", "")
here = os.path.dirname(os.path.abspath(__file__))
create_file = os.path.join(here, "..", "..", "ccp_rest-api-tests_jobsnow", "documentation", "vis", "database",
                           "elasticsearch", "scripts", "entities", "create", INDEX)
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def call(method, path, body=None, ndjson=None):
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    if ndjson is not None:
        data = ndjson.encode("utf-8")
    request = urllib.request.Request(target_url + path, data=data, method=method)
    request.add_header("Content-Type", "application/x-ndjson" if ndjson is not None else "application/json")
    if auth:
        request.add_header("Authorization", auth)
    try:
        with opener.open(request) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"{}")


def is_valid(item):
    return isinstance(item, str) and 4 <= len(item) <= 50 and DOMAIN.fullmatch(item) is not None


# 2. varredura
restrictions = []
query = {"size": 1000, "_source": ["email", FIELD], "query": {"exists": {"field": FIELD}}}
status, page = call("POST", "/" + RESUME_INDEX + "/_search?scroll=2m", query)
if status != 200:
    print("falha na busca:", status, page)
    sys.exit(1)
scanned = 0
while page["hits"]["hits"]:
    for hit in page["hits"]["hits"]:
        scanned += 1
        source = hit["_source"]
        items = source.get(FIELD) or []
        if not isinstance(items, list):
            items = [items]
        only_wrong_domains = [str(item) for item in items if not is_valid(item)]
        if not only_wrong_domains:
            continue
        message = MESSAGE.format(", ".join(only_wrong_domains))
        restrictions.append({"_id": hit["_id"], "email": source["email"], "wrong": only_wrong_domains, "message": message})
    status, page = call("POST", "/_search/scroll", {"scroll": "2m", "scroll_id": page["_scroll_id"]})
call("DELETE", "/_search/scroll", {"scroll_id": page.get("_scroll_id", "")})

print(RESUME_INDEX, "com", FIELD + ":", scanned, "| com itens invalidos:", len(restrictions))
for number, restriction in enumerate(restrictions, 1):
    print("%4d  %s  %s" % (number, restriction["_id"], " | ".join(restriction["wrong"])))
too_long = [restriction["_id"] for restriction in restrictions if len(restriction["message"]) > MAX_MESSAGE]
if too_long:
    print("mensagens acima de", MAX_MESSAGE, "caracteres (a validacao recusaria):", too_long)
    sys.exit(1)

if not write:
    print("simulacao: nada gravado (use --gravar)")
    sys.exit(0)

# 1. indice (so com --gravar: a simulacao nao escreve nada)
with open(create_file, encoding="utf-8") as source:
    definition = json.load(source)
status, _ = call("HEAD", "/" + INDEX)
if status == 404:
    status, answer = call("PUT", "/" + INDEX, definition)
    print("indice criado:", status, answer.get("acknowledged"))
    if status != 200:
        print(answer)
        sys.exit(1)
else:
    print("indice ja existia:", INDEX)

# 3. gravacao
lines = []
for restriction in restrictions:
    lines.append(json.dumps({"index": {"_index": INDEX, "_id": restriction["_id"]}}))
    lines.append(json.dumps({"email": restriction["email"], "message": [restriction["message"]]}, ensure_ascii=False))
for start in range(0, len(lines), 1000):
    status, answer = call("POST", "/_bulk?refresh=true", ndjson="\n".join(lines[start:start + 1000]) + "\n")
    if status != 200 or answer.get("errors"):
        print("falha no bulk:", status, json.dumps(answer)[:2000])
        sys.exit(1)
status, count = call("GET", "/" + INDEX + "/_count")
print("gravadas:", len(restrictions), "| total no indice:", count.get("count"))
