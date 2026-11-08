# E-mail do curriculo reativado (after delete da gemea vis_inactive_resume, 2026-11-08) igual ao do curriculo salvo:
# mesma tabela de como o recrutador vera o curriculo, com a abertura "Voce reativou seus dados". Copia do ES local
# (9200) para o destino, com o mesmo id, (1) o template (jn_email_template_message, templateId
# VisMessages$VisNotifyUserAboutReactivatedResume, portugues e ingles), regra "igual", e (2) os parametros de envio
# (jn_email_parameters_to_send), regra "adaptar": o moreParameters (frontendUrl e oniasLinkedin) vem do registro de
# producao do e-mail aos recrutadores (VisNotifyRecruiterAboutResumes). Mesma logica do 39, so muda o templateId.
# A origem e o ES local depois de gravar as sementes de VisEntityResume.getFirstRecordsToInsert.
# Rodar LOGO DEPOIS do deploy da vis e dos consumidores com o VisNotifyUserAboutReactivatedResume novo (vis_resume e
# async: quem manda o e-mail e o consumidor): antes dele, o e-mail sairia com o {resumesTable} cru. Idempotente.
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python 44-email-do-curriculo-reativado.py [destino] [origem]
import json
import os
import sys
import urllib.parse
import urllib.request

target_url = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:9210"
source_url = sys.argv[2].rstrip("/") if len(sys.argv) > 2 else "http://127.0.0.1:9200"
auth = os.environ.get("ES_DESTINO_AUTH", "")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
saved_template = "com.vis.messages.VisMessages$VisNotifyUserAboutReactivatedResume"
recruiters_template = "com.vis.messages.VisMessages$VisNotifyRecruiterAboutResumes"
environment_fields = ("frontendUrl", "oniasLinkedin")


def call(url, method, path, body=None, authorization=""):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if authorization:
        request.add_header("Authorization", authorization)
    with opener.open(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def search(url, index, template_id, authorization=""):
    query = {"size": 10, "query": {"term": {"templateId": template_id}}}
    return call(url, "POST", "/%s/_search" % index, query, authorization)["hits"]["hits"]


def write(index, hit, source):
    doc_path = "/%s/_doc/%s" % (index, urllib.parse.quote(hit["_id"], safe=""))
    result = call(target_url, "PUT", doc_path + "?refresh=true", source, auth)
    written = call(target_url, "GET", doc_path, authorization=auth)["_source"]
    same = "confere" if written == source else "DIFERENTE"
    print("%s %s: %s, %s" % (index, source.get("language", "parametros"), result["result"], same))


print("origem:", call(source_url, "GET", "/")["cluster_name"])
print("destino:", call(target_url, "GET", "/", authorization=auth)["cluster_name"])

templates = search(source_url, "jn_email_template_message", saved_template)
languages = sorted(hit["_source"].get("language") for hit in templates)
if languages != ["english", "portuguese"]:
    raise SystemExit("esperava os dois idiomas do template na origem, achei %s" % languages)
if any("{resumesTable}" not in hit["_source"]["message"] for hit in templates):
    raise SystemExit("o template da origem nao tem {resumesTable}: grave antes as sementes novas no local")

parameters = search(source_url, "jn_email_parameters_to_send", saved_template)
if len(parameters) != 1:
    raise SystemExit("esperava 1 registro de parametros na origem, achei %d" % len(parameters))
target_recruiters = search(target_url, "jn_email_parameters_to_send", recruiters_template, auth)
if len(target_recruiters) != 1:
    raise SystemExit("esperava 1 registro de parametros do e-mail aos recrutadores no destino, achei %d" % len(target_recruiters))
target_more = target_recruiters[0]["_source"].get("moreParameters", {})
missing = [field for field in environment_fields if field not in target_more]
if missing:
    raise SystemExit("o destino nao tem %s no moreParameters do e-mail aos recrutadores" % missing)

for hit in templates:
    write("jn_email_template_message", hit, hit["_source"])
adapted = dict(parameters[0]["_source"])
adapted["moreParameters"] = {field: target_more[field] for field in environment_fields}
write("jn_email_parameters_to_send", parameters[0], adapted)
print("moreParameters gravado:", adapted["moreParameters"])
