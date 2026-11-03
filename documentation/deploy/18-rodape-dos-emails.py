# Rodape dos e-mails (endereco fisico e link da politica de privacidade, exigidos pelo SendGrid): acrescenta o rodape de
# JnEmailFooter, antes do ultimo </body>, nos templates ja gravados do token de login, do e-mail de curriculos aos
# recrutadores e do convite aos candidatos legados. Template que ja tem o link da politica fica como esta: rodar de novo
# nao duplica. O texto abaixo e copia do de JnEmailFooter.java; mudou la, muda aqui.
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python 18-rodape-dos-emails.py [url]
import json
import os
import sys
import urllib.parse
import urllib.request

url = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:9210"
auth = os.environ.get("ES_DESTINO_AUTH", "")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
index = "jn_email_template_message"
privacy_link = "https://onias.site/privacidade"
address = "JobsNow · Avenida Alda, 858, cj. 193, Torre 1, Centro, Diadema, SP, 09910-170, "
footers = {
    "portuguese": "<hr/><p style='font-size: 12px; color: #777777;'>" + address + "Brasil · <a href='" + privacy_link + "' target='_blank'>Política de privacidade</a></p>",
    "english": "<hr/><p style='font-size: 12px; color: #777777;'>" + address + "Brazil · <a href='" + privacy_link + "' target='_blank'>Privacy policy</a></p>",
}
templates = (
    "com.jn.business.messages.JnMessages$JnNotifyUserAboutLoginToken",
    "com.vis.messages.VisMessages$VisNotifyRecruiterAboutResumes",
    "com.vis.messages.VisMessages$VisInviteLegacyCandidate",
)


def call(method, path, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if auth:
        request.add_header("Authorization", auth)
    with opener.open(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


print("cluster:", call("GET", "/")["cluster_name"])
hits = call("POST", "/%s/_search" % index, {"size": 500, "query": {"match_all": {}}})["hits"]["hits"]
changed = 0
for hit in hits:
    source = hit["_source"]
    template_id = source.get("templateId", "")
    if template_id not in templates:
        continue
    language = source.get("language", "")
    message = source.get("message", "")
    name = "%s (%s)" % (template_id.rsplit("$", 1)[-1], language)
    if privacy_link in message:
        print("ja tem rodape:", name)
        continue
    position = message.rfind("</body>")
    if position < 0 or language not in footers:
        print("sem </body> ou idioma desconhecido, ficou como esta:", name)
        continue
    new_message = message[:position] + footers[language] + message[position:]
    document_id = urllib.parse.quote(hit["_id"], safe="")
    call("POST", "/%s/_update/%s?refresh=true" % (index, document_id), {"doc": {"message": new_message}})
    changed += 1
    print("rodape acrescentado:", name)
print("templates alterados:", changed)
