# E-mail do curriculo excluido no padrao dos outros avisos do curriculo e textos no singular da tabela (2026-11-10):
# (1) o template de VisMessages$VisNotifyUserAboutDeletedResume ganhou a saudacao do Onias e o rodape com o link da
#     politica de privacidade (defeito R04-1: saia com 124 bytes, so uma frase); copia do ES local (9200) para o
#     destino, com o mesmo id, o template (jn_email_template_message, portugues e ingles), regra "igual", e os
#     parametros de envio (jn_email_parameters_to_send), regra "adaptar": o moreParameters (frontendUrl e
#     oniasLinkedin) vem do registro de producao do e-mail aos recrutadores (VisNotifyRecruiterAboutResumes), como no 45;
# (2) os textos novos de jn_system_message disponibilityInOneDay ("em 1 dia") e temporaryJobMinimumOneMonth ("1 mes"),
#     usados pela tabela do e-mail aos recrutadores, do curriculo salvo e do convite (defeito R11-1: "em 1 dias").
# A origem e o ES local depois de gravar as sementes de VisEntityResume.getFirstRecordsToInsert e de
# VisRecruiterResumesTexts.getSeeds.
# Rodar ANTES do deploy da vis e dos consumidores com o VisBusinessBuildResumeRow novo: sem os textos em producao,
# a tabela de um curriculo com disponibilidade de 1 dia falha. O template novo vale tambem com o codigo antigo.
# Grava por cima (idempotente). O cache das entidades (1 hora) segura o valor antigo ate expirar ou ate as APIs e os
# consumidores reiniciarem.
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python 46-email-do-curriculo-excluido-e-singulares.py [destino] [origem]
import json
import os
import sys
import urllib.parse
import urllib.request

target_url = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:9210"
source_url = sys.argv[2].rstrip("/") if len(sys.argv) > 2 else "http://127.0.0.1:9200"
auth = os.environ.get("ES_DESTINO_AUTH", "")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
deleted_template = "com.vis.messages.VisMessages$VisNotifyUserAboutDeletedResume"
recruiters_template = "com.vis.messages.VisMessages$VisNotifyRecruiterAboutResumes"
environment_fields = ("frontendUrl", "oniasLinkedin")
languages = ["english", "portuguese"]
system_messages = [
    "com.vis.business.recruiter.resumes.VisRecruiterResumesTexts.disponibilityInOneDay",
    "com.vis.business.recruiter.resumes.VisRecruiterResumesTexts.temporaryJobMinimumOneMonth",
]


def call(url, method, path, body=None, authorization=""):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if authorization:
        request.add_header("Authorization", authorization)
    with opener.open(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def search(url, index, field, value, authorization=""):
    query = {"size": 10, "query": {"term": {field: value}}}
    return call(url, "POST", "/%s/_search" % index, query, authorization)["hits"]["hits"]


def write(index, hit, source, label):
    doc_path = "/%s/_doc/%s" % (index, urllib.parse.quote(hit["_id"], safe=""))
    result = call(target_url, "PUT", doc_path + "?refresh=true", source, auth)
    written = call(target_url, "GET", doc_path, authorization=auth)["_source"]
    same = "confere" if written == source else "DIFERENTE"
    print("%s %s %s: %s, %s" % (index, label, source.get("language", "parametros"), result["result"], same))


print("origem:", call(source_url, "GET", "/")["cluster_name"])
print("destino:", call(target_url, "GET", "/", authorization=auth)["cluster_name"])

# confere tudo na origem e no destino antes de gravar qualquer coisa
templates = search(source_url, "jn_email_template_message", "templateId", deleted_template)
found = sorted(hit["_source"].get("language") for hit in templates)
if found != languages:
    raise SystemExit("esperava os dois idiomas do template na origem, achei %s" % found)
if any("{oniasLinkedin}" not in hit["_source"]["message"] for hit in templates):
    raise SystemExit("o template da origem nao tem {oniasLinkedin}: grave antes as sementes novas no local")
parameters = search(source_url, "jn_email_parameters_to_send", "templateId", deleted_template)
if len(parameters) != 1:
    raise SystemExit("esperava 1 registro de parametros na origem, achei %d" % len(parameters))
target_recruiters = search(target_url, "jn_email_parameters_to_send", "templateId", recruiters_template, auth)
if len(target_recruiters) != 1:
    raise SystemExit("esperava 1 registro de parametros do e-mail aos recrutadores no destino, achei %d" % len(target_recruiters))
target_more = target_recruiters[0]["_source"].get("moreParameters", {})
missing = [field for field in environment_fields if field not in target_more]
if missing:
    raise SystemExit("o destino nao tem %s no moreParameters do e-mail aos recrutadores" % missing)
texts = {}
for name in system_messages:
    hits = search(source_url, "jn_system_message", "systemMessageName", name)
    found = sorted(hit["_source"].get("language") for hit in hits)
    if found != languages:
        raise SystemExit("%s: esperava %s na origem, achei %s; grave antes as sementes no local" % (name, languages, found))
    texts[name] = hits

for name, hits in texts.items():
    for hit in hits:
        write("jn_system_message", hit, hit["_source"], name.rsplit(".", 1)[-1])
for hit in templates:
    write("jn_email_template_message", hit, hit["_source"], "VisNotifyUserAboutDeletedResume")
adapted = dict(parameters[0]["_source"])
adapted["moreParameters"] = {field: target_more[field] for field in environment_fields}
write("jn_email_parameters_to_send", parameters[0], adapted, "VisNotifyUserAboutDeletedResume")
print("moreParameters gravado:", adapted["moreParameters"])
