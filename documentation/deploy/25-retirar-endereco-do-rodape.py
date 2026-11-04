# Retira o endereco fisico do rodape dos e-mails ja gravados em jn_email_template_message (o rodape do script 18 e de
# JnEmailFooter): o rodape fica so com "JobsNow ·" e o link da politica de privacidade. Varre todos os templates; o que
# nao tem o endereco fica como esta, e rodar de novo nao muda nada.
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python -X utf8 25-retirar-endereco-do-rodape.py [url]
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
addresses = (
    "Avenida Alda, 858, cj. 193, Torre 1, Centro, Diadema, SP, 09910-170, Brasil · ",
    "Avenida Alda, 858, cj. 193, Torre 1, Centro, Diadema, SP, 09910-170, Brazil · ",
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
hits = call("POST", "/%s/_search" % index, {"size": 1000, "query": {"match_all": {}}})["hits"]["hits"]
changed = 0
for hit in hits:
    source = hit["_source"]
    message = source.get("message", "")
    new_message = message
    for address in addresses:
        new_message = new_message.replace(address, "")
    if new_message == message:
        continue
    name = "%s (%s)" % (source.get("templateId", "").rsplit("$", 1)[-1], source.get("language", ""))
    document_id = urllib.parse.quote(hit["_id"], safe="")
    call("POST", "/%s/_update/%s?refresh=true" % (index, document_id), {"doc": {"message": new_message}})
    changed += 1
    print("endereco retirado:", name)
print("templates alterados:", changed)
