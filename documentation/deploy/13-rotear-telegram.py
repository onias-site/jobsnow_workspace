# Leva para um Elasticsearch ja populado o roteamento das mensagens do bot de suporte para os grupos com topicos,
# sem recriar indices: inclui o campo origin em jn_jobsnow_error e atualiza 3 registros de
# jn_instant_messenger_parameters_to_send. Os valores sao os dos seeds de JnEntityInstantMessengerParametersToSend e
# JsEntityContactUs. Pode rodar de novo. A escrita e direta: nao gera versao em jn_versionable.
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python 13-rotear-telegram.py <url>
import json
import os
import sys
import urllib.request

url = sys.argv[1].rstrip("/")
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


index = "jn_instant_messenger_parameters_to_send"
stack_traces = -1004489667665
contact_us = -1004428777693
routes = {
    "com.jn.business.messages.JnMessages$JnNotifySupportAboutAnError": (stack_traces, {"messageThreadIds": {"vis": 4, "js": 5}}),
    "com.jn.business.messages.JnMessages$JnNotifySupportAboutWaring": (stack_traces, {"messageThreadIds": {"vis": 4, "js": 5}}),
    "com.js.messages.JsNotifySupportAndUserAboutContactUs": (contact_us, {
        "operatorChatId": 751717896,
        "messageThreadIds": {"reportBug": 5, "clarifyDoubts": 6, "makeCriticism": 7, "makeSuggestion": 8, "makeCompliment": 9, "makeComment": 10},
    }),
}

call("PUT", "/jn_jobsnow_error/_mapping", {"properties": {"origin": {"type": "keyword"}}})
print("jn_jobsnow_error: campo origin presente")

for template, (chat, extras) in routes.items():
    query = {"size": 10, "query": {"term": {"templateId": template}}}
    hits = call("POST", "/" + index + "/_search", query)["hits"]["hits"]
    if len(hits) != 1:
        raise SystemExit("esperava 1 registro de %s, achei %d" % (template, len(hits)))
    hit = hits[0]
    more = dict(hit["_source"].get("moreParameters", {}))
    more.update(extras)
    call("POST", "/" + index + "/_update/" + hit["_id"] + "?refresh=true", {"doc": {"chatId": chat, "moreParameters": more}})
    saved = call("GET", "/" + index + "/_doc/" + hit["_id"])["_source"]
    if saved["chatId"] != chat or saved["moreParameters"].get("messageThreadIds") != extras["messageThreadIds"]:
        raise SystemExit("registro nao ficou como esperado: " + template)
    print("%s: chat %s, %d topicos" % (template.split(".")[-1], saved["chatId"], len(extras["messageThreadIds"])))
