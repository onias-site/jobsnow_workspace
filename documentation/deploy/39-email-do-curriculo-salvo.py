# E-mail do curriculo salvo (after save do vis_resume) igual ao convite aos candidatos legados, sem a chamada para
# cadastrar e sem o aviso de convite unico: copia do ES local (9200) para o destino, com o mesmo id,
# (1) o template (jn_email_template_message, templateId VisMessages$VisNotifyUserAboutSavedResume, portugues e ingles),
# regra "igual", e (2) os parametros de envio (jn_email_parameters_to_send), regra "adaptar": o moreParameters
# (frontendUrl e oniasLinkedin, que a tabela e a saudacao usam) vem do registro de producao do e-mail aos recrutadores
# (VisNotifyRecruiterAboutResumes), que ja tem os enderecos de producao.
# A origem e o ES local depois de gravar as sementes de VisEntityResume.getFirstRecordsToInsert.
# Rodar LOGO DEPOIS do deploy do vis com o VisBusinessBuildSavedResumeTable: antes dele, a API antiga nao preenche o
# {resumesTable} e o e-mail sairia com o marcador cru. Idempotente. O cache das entidades (1 hora) segura o valor antigo
# ate expirar ou ate as APIs e os consumidores reiniciarem.
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python 39-email-do-curriculo-salvo.py [destino] [origem]
import json
import os
import sys
import urllib.parse
import urllib.request

target_url = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:9210"
source_url = sys.argv[2].rstrip("/") if len(sys.argv) > 2 else "http://127.0.0.1:9200"
auth = os.environ.get("ES_DESTINO_AUTH", "")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
saved_template = "com.vis.messages.VisMessages$VisNotifyUserAboutSavedResume"
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
