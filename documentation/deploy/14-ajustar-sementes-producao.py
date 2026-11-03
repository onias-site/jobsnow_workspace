# Fase 7 do plano de migracao: troca os enderecos locais das sementes de jn_email_parameters_to_send pelos de producao.
# Os seeds do codigo continuam com os enderecos locais, usados no ambiente de teste. Pode rodar de novo.
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python 14-ajustar-sementes-producao.py [url]
import json
import os
import sys
import urllib.request

url = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:9210"
auth = os.environ.get("ES_DESTINO_AUTH", "")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def call(method, path, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if auth:
        request.add_header("Authorization", auth)
    with opener.open(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


if call("GET", "/")["cluster_name"] != "jobsnow-prd":
    raise SystemExit("o destino nao e jobsnow-prd")

index = "jn_email_parameters_to_send"
changes = {
    "com.vis.messages.VisMessages$VisNotifyRecruiterAboutResumes": {"frontendUrl": "https://onias.site", "visApiUrl": "https://api.onias.site"},
    "com.jn.business.messages.JnMessages$JnNotifyUserAboutLoginToken": {"accessLink": "https://onias.site"},
}
hits = call("POST", "/" + index + "/_search", {"size": 500, "query": {"match_all": {}}})["hits"]["hits"]
for suffix, values in changes.items():
    name = suffix.split(".")[-1]
    found = [hit for hit in hits if hit["_source"].get("templateId", "").endswith(name)]
    if len(found) != 1:
        raise SystemExit("esperava 1 registro de %s, achei %d" % (name, len(found)))
    hit = found[0]
    more = dict(hit["_source"]["moreParameters"])
    more.update(values)
    call("POST", "/" + index + "/_update/" + hit["_id"] + "?refresh=true", {"doc": {"moreParameters": more}})
    saved = call("GET", "/" + index + "/_doc/" + hit["_id"])["_source"]["moreParameters"]
    if any(saved.get(key) != value for key, value in values.items()):
        raise SystemExit("registro nao ficou como esperado: " + name)
    print(name, json.dumps({key: saved[key] for key in values}))
