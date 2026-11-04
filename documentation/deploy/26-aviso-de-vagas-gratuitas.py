# Aviso destacado na terceira linha do e-mail de curriculos aos recrutadores (VisNotifyRecruiterAboutResumes): insere,
# logo depois do paragrafo "Seguem os curriculos ... (N no total).", a caixa de VisEntityRecruiterResumes.Notice. O texto
# abaixo e copia do de VisEntityRecruiterResumes.java; mudou la, muda aqui. Template que ja tem o aviso fica como esta.
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python -X utf8 26-aviso-de-vagas-gratuitas.py [url]
#      sem url, usa o tunel de producao (http://127.0.0.1:9210); para o local, passe http://localhost:9200
import json
import os
import sys
import urllib.parse
import urllib.request

url = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:9210"
auth = os.environ.get("ES_DESTINO_AUTH", "")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
index = "jn_email_template_message"
template_id = "com.vis.messages.VisMessages$VisNotifyRecruiterAboutResumes"
box = ("<p style=\"background-color: #FFF4CC; border-left: 6px solid #F5A623; padding: 12px 16px; "
       "font-size: 17px; font-weight: bold; color: #333333;\">&#128226; ")
notices = {
    "portuguese": (" no total).</p>", box + "Ainda este ano você poderá, <span style=\"color: #D35400;\">gratuitamente</span>, "
                   "cadastrar vagas e receber apenas currículos consistentes!</p>"),
    "english": (" in total).</p>", box + "Later this year you will be able, <span style=\"color: #D35400;\">for free</span>, "
                "to post positions and receive only consistent resumes!</p>"),
}


def call(method, path, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if auth:
        request.add_header("Authorization", auth)
    with opener.open(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


print("cluster:", call("GET", "/")["cluster_name"])
hits = call("POST", "/%s/_search" % index, {"size": 1000, "query": {"match_all": {}}})["hits"]["hits"]
changed = 0
for hit in hits:
    source = hit["_source"]
    if source.get("templateId") != template_id:
        continue
    language = source.get("language", "")
    message = source.get("message", "")
    if language not in notices:
        print("idioma desconhecido, ficou como esta:", language)
        continue
    anchor, notice = notices[language]
    if "#FFF4CC" in message:
        print("ja tem o aviso:", language)
        continue
    position = message.find(anchor)
    if position < 0:
        print("sem o paragrafo do total, ficou como esta:", language)
        continue
    position += len(anchor)
    new_message = message[:position] + notice + message[position:]
    document_id = urllib.parse.quote(hit["_id"], safe="")
    call("POST", "/%s/_update/%s?refresh=true" % (index, document_id), {"doc": {"message": new_message}})
    changed += 1
    print("aviso inserido:", language)
print("templates alterados:", changed)
