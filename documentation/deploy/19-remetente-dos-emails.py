# Remetente dos e-mails: troca devs.jobsnow@gmail.com por curriculos@onias.site nos parametros de envio ja gravados
# (jn_email_parameters_to_send), porque o SendGrid autentica o dominio onias.site e um remetente @gmail.com reprova no
# DMARC. O sender nao faz parte da chave, entao o id do registro nao muda. Rodar de novo nao altera nada.
# O cache das entidades (1 hora) segura o valor antigo ate expirar ou ate as APIs e os consumidores reiniciarem.
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python 19-remetente-dos-emails.py [url]
import json
import os
import sys
import urllib.request

url = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:9210"
auth = os.environ.get("ES_DESTINO_AUTH", "")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
index = "jn_email_parameters_to_send"
old_sender = "devs.jobsnow@gmail.com"
new_sender = "curriculos@onias.site"


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
    if source.get("sender") != old_sender:
        continue
    call("POST", "/%s/_update/%s?refresh=true" % (index, hit["_id"]), {"doc": {"sender": new_sender}})
    changed += 1
    print("remetente trocado:", source.get("templateId", hit["_id"]))
remaining = [hit for hit in call("POST", "/%s/_search" % index, {"size": 500, "query": {"match_all": {}}})["hits"]["hits"] if hit["_source"].get("sender") == old_sender]
print("parametros alterados: %d; ainda com o remetente antigo: %d" % (changed, len(remaining)))
