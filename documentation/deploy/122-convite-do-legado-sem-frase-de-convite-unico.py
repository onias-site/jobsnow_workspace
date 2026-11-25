# Tira do convite aos candidatos do legado (VisInviteLegacyCandidate, jn_email_template_message, regra "igual") o
# paragrafo que diz que o convite e unico (pedido de 2026-11-25: o convite e reenviado toda semana a quem nao se
# cadastrou). Mesmo texto da semente de VisEntityRecruiterResumes.getInvitationSeeds, com o mesmo _id; so o message muda.
# Idempotente: o template que ja nao tem o paragrafo fica como esta. Confere o que gravou.
# Depois: o reenvio le o template de producao a cada execucao; nao exige deploy.
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python -X utf8 122-convite-do-legado-sem-frase-de-convite-unico.py [destino]
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
template_id = "com.vis.messages.VisMessages$VisInviteLegacyCandidate"
paragraphs = {
    "portuguese": "<p>Este convite é único: se você não se cadastrar, não enviaremos outro e-mail sobre este assunto.</p>",
    "english": "<p>This invitation is a one-off: if you do not register, we will not send another e-mail about it.</p>",
}


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
    paragraph = paragraphs.get(language)
    if paragraph is None:
        sys.exit("idioma inesperado no template %s: %s" % (document_id, language))
    message = source.get("message", "")
    if paragraph not in message:
        print("ja esta sem o paragrafo:", language)
        continue
    new_message = message.replace(paragraph, "")
    quoted_id = urllib.parse.quote(document_id, safe="")
    call("POST", "/%s/_update/%s?refresh=true" % (index, quoted_id), {"doc": {"message": new_message}})
    changed += 1
    print("mensagem atualizada:", language)

check = templates()
failed = False
for document_id, source in check.items():
    language = source["language"]
    message = source.get("message", "")
    ok = paragraphs[language] not in message and "</body></html>" in message
    failed = failed or not ok
    print("conferido %s: %s" % (language, "OK" if ok else "DIFERENTE"))
print("templates alterados:", changed)
sys.exit(1 if failed else 0)
