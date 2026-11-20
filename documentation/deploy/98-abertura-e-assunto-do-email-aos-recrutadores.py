# Leva a producao o novo texto do e-mail de curriculos aos recrutadores (VisNotifyRecruiterAboutResumes), regra "igual"
# de jn_email_template_message: o assunto passa a comecar com "[DE GRACA!!!] " ("[FOR FREE!!!] " no ingles); a abertura
# vira "Seguem os curriculos inseridos ou alterados no onias.site dos ultimos 7 dias N no total (ver todos).", com
# onias.site ligado a {frontendUrl} e "ver todos" a {seeAllUrl} (a tela Curriculos da semana); e a ultima frase antes da
# tabela pede ao recrutador que diga ao candidato que o encontrou aqui. Copia subject e message do ES local (semeado por
# VisEntityRecruiterResumes.java), com o mesmo _id; aborta se o local ainda nao tiver o texto novo.
# Exige o deploy do cron (jobsnow-curriculos-aos-recrutadores) com a vis que poe {seeAllUrl} na mensagem: sem ele, o link
# "ver todos" sai com a chave crua. Rode o script logo antes desse deploy (o envio e as 10:00).
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python -X utf8 98-abertura-e-assunto-do-email-aos-recrutadores.py [destino] [origem]
#      destino padrao: tunel de producao (http://127.0.0.1:9210); origem padrao: ES local (http://127.0.0.1:9200)
import json
import os
import sys
import urllib.parse
import urllib.request

destination = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:9210"
origin = sys.argv[2].rstrip("/") if len(sys.argv) > 2 else "http://127.0.0.1:9200"
auth = os.environ.get("ES_DESTINO_AUTH", "")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
index = "jn_email_template_message"
template_id = "com.vis.messages.VisMessages$VisNotifyRecruiterAboutResumes"
prefixes = {"portuguese": "[DE GRAÇA!!!] ", "english": "[FOR FREE!!!] "}
copied_fields = ("subject", "message")


def call(url, method, path, body=None, authorization=""):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if authorization:
        request.add_header("Authorization", authorization)
    with opener.open(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def templates(url, authorization):
    query = {"size": 100, "query": {"match_all": {}}}
    hits = call(url, "POST", "/%s/_search" % index, query, authorization)["hits"]["hits"]
    return {h["_id"]: h["_source"] for h in hits if h["_source"].get("templateId") == template_id}


print("destino:", call(destination, "GET", "/", authorization=auth)["cluster_name"])
local = templates(origin, "")
if len(local) != 2:
    sys.exit("a origem deveria ter 2 templates (portugues e ingles), tem %d" % len(local))
for document_id, source in local.items():
    language = source.get("language", "")
    if not source.get("subject", "").startswith(prefixes.get(language, "?")):
        sys.exit("a origem ainda tem o assunto antigo (%s): recrie as entidades locais com a vis nova" % language)
    if "seeAllUrl" not in source.get("message", ""):
        sys.exit("a origem ainda tem a abertura antiga (%s)" % language)

remote = templates(destination, auth)
changed = 0
for document_id, source in local.items():
    language = source["language"]
    current = remote.get(document_id)
    if current is None:
        sys.exit("o destino nao tem o template %s (%s): confira o _id antes de seguir" % (language, document_id))
    new_values = {field: source[field] for field in copied_fields}
    if all(current.get(field) == value for field, value in new_values.items()):
        print("ja esta atualizado:", language)
        continue
    quoted_id = urllib.parse.quote(document_id, safe="")
    call(destination, "POST", "/%s/_update/%s?refresh=true" % (index, quoted_id), {"doc": new_values}, auth)
    changed += 1
    print("template atualizado:", language)

check = templates(destination, auth)
for document_id, source in local.items():
    same = all(check[document_id].get(field) == source[field] for field in copied_fields)
    print("conferido %s: %s" % (source["language"], "OK" if same else "DIFERENTE"))
print("templates alterados:", changed)
