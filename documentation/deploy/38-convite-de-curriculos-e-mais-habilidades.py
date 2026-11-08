# Convite aos candidatos legados e tabela de curriculos: copia do ES local (9200) para o destino, com o mesmo id,
# (1) o template do e-mail do convite (jn_email_template_message, templateId VisMessages$VisInviteLegacyCandidate,
# portugues e ingles: assunto "Envie seu curriculo para 2.000 recrutadores gratuitamente" e o paragrafo das empresas
# bloqueadas) e (2) o texto moreSkills de jn_system_message ("ver as outras {count} habilidades", que dobra as
# habilidades depois da 15a na tabela do convite e do e-mail aos recrutadores).
# A origem e o ES local depois de o InviteLegacyCandidates (ou o CcpCreateEntities do vis) gravar as sementes.
# Rodar ANTES do deploy do vis com o moreSkills: sem o texto em producao, a tabela dos recrutadores falha.
# Grava por cima (idempotente). O cache das entidades (1 hora) segura o valor antigo ate expirar ou ate as APIs e os
# consumidores reiniciarem.
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python 38-convite-de-curriculos-e-mais-habilidades.py [destino] [origem]
import json
import os
import sys
import urllib.parse
import urllib.request

target_url = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:9210"
source_url = sys.argv[2].rstrip("/") if len(sys.argv) > 2 else "http://127.0.0.1:9200"
auth = os.environ.get("ES_DESTINO_AUTH", "")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
languages = ["english", "portuguese"]
copies = [
    ("jn_email_template_message", "templateId", "com.vis.messages.VisMessages$VisInviteLegacyCandidate"),
    ("jn_system_message", "systemMessageName", "com.vis.business.recruiter.resumes.VisRecruiterResumesTexts.moreSkills"),
]


def call(url, method, path, body=None, authorization=""):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if authorization:
        request.add_header("Authorization", authorization)
    with opener.open(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


print("origem:", call(source_url, "GET", "/")["cluster_name"])
print("destino:", call(target_url, "GET", "/", authorization=auth)["cluster_name"])
for index, field, value in copies:
    query = {"size": 10, "query": {"term": {field: value}}}
    hits = call(source_url, "POST", "/%s/_search" % index, query)["hits"]["hits"]
    found = sorted(hit["_source"].get("language") for hit in hits)
    if found != languages:
        raise SystemExit("%s: esperava %s na origem, achei %s; grave antes as sementes no local" % (value, languages, found))
    for hit in hits:
        doc_path = "/%s/_doc/%s" % (index, urllib.parse.quote(hit["_id"], safe=""))
        result = call(target_url, "PUT", doc_path + "?refresh=true", hit["_source"], auth)
        written = call(target_url, "GET", doc_path, authorization=auth)["_source"]
        same = "confere" if written == hit["_source"] else "DIFERENTE"
        print("%s %s %s: %s, %s" % (index, value.rsplit(".", 1)[-1], hit["_source"]["language"], result["result"], same))
