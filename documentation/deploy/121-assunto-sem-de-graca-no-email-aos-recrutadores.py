# Tira do assunto do e-mail de curriculos aos recrutadores (VisNotifyRecruiterAboutResumes, jn_email_template_message,
# regra "igual") o prefixo "[DE GRACA!!!] " ("[FOR FREE!!!] " no ingles), posto pelo script 98 (pedido de 2026-11-25: a
# abertura dos e-mails caiu de 47% para 13% em tres semanas, e caixa alta com "!!!" e "gratis" no assunto e gatilho classico
# dos filtros de spam). Mesmo texto da semente de VisEntityRecruiterResumes.java, com o mesmo _id; so o subject muda.
# Idempotente: o template que ja nao comeca com o prefixo fica como esta. Confere o que gravou.
# Depois: o job jobsnow-curriculos-aos-recrutadores le o template a cada execucao (10:00); nao exige deploy.
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python -X utf8 121-assunto-sem-de-graca-no-email-aos-recrutadores.py [destino]
#      destino padrao: tunel de producao (http://127.0.0.1:9210)
import json
import os
import sys
import urllib.parse
import urllib.request

destination = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:9210"
auth = os.environ.get("ES_DESTINO_AUTH", "")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
index = "jn_email_template_message"
template_id = "com.vis.messages.VisMessages$VisNotifyRecruiterAboutResumes"
prefixes = {"portuguese": "[DE GRAÇA!!!] ", "english": "[FOR FREE!!!] "}
expected_starts = {"portuguese": "{totalOfResumes} currículos de ", "english": "{totalOfResumes} resumes of "}


def call(method, path, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(destination + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if auth:
        request.add_header("Authorization", auth)
    with opener.open(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def templates():
    query = {"size": 100, "query": {"term": {"templateId": template_id}}}
    hits = call("POST", "/%s/_search" % index, query)["hits"]["hits"]
    return {h["_id"]: h["_source"] for h in hits if h["_source"].get("templateId") == template_id}


print("destino:", call("GET", "/")["cluster_name"])
current = templates()
if len(current) != 2:
    sys.exit("o destino deveria ter 2 templates (portugues e ingles), tem %d" % len(current))
changed = 0
for document_id, source in current.items():
    language = source.get("language", "")
    prefix = prefixes.get(language)
    if prefix is None:
        sys.exit("idioma inesperado no template %s: %s" % (document_id, language))
    subject = source.get("subject", "")
    if not subject.startswith(prefix):
        print("ja esta sem o prefixo:", language)
        continue
    new_subject = subject[len(prefix):]
    quoted_id = urllib.parse.quote(document_id, safe="")
    call("POST", "/%s/_update/%s?refresh=true" % (index, quoted_id), {"doc": {"subject": new_subject}})
    changed += 1
    print("assunto atualizado:", language)

check = templates()
failed = False
for document_id, source in check.items():
    language = source["language"]
    subject = source.get("subject", "")
    ok = not subject.startswith(prefixes[language]) and subject.startswith(expected_starts[language])
    failed = failed or not ok
    print("conferido %s: %s | %s" % (language, "OK" if ok else "DIFERENTE", subject))
print("templates alterados:", changed)
sys.exit(1 if failed else 0)
