# E-mail do token de acesso so com os dois primeiros paragrafos (2026-11-11, pedido do usuario): a saudacao do Onias e
# o paragrafo do token. Saem o convite para receber vagas e curriculos pelo Telegram e os passos A a D do bot.
# O template de JnMessages$JnNotifyUserAboutLoginToken (jn_email_template_message, portugues e ingles, regra "igual")
# e lido da origem; se ainda tiver os paragrafos do Telegram (origem antiga), eles sao cortados aqui com a mesma regra
# das sementes de JnEntityEmailTemplateMessage. Grava no destino com o mesmo id e confere. Os parametros de envio nao
# mudam: telegramGroupLink e botAddress ficam no moreParameters sem uso.
# Rodar com origem e destino locais atualiza o ES local; depois, com destino de producao (tunel).
# Vale com o codigo antigo e com o novo: pode rodar antes ou depois do deploy.
# Grava por cima (idempotente). O cache das entidades (1 hora) segura o texto antigo ate expirar ou ate as APIs e os
# consumidores reiniciarem.
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python 52-email-do-token-so-com-a-saudacao.py [destino] [origem]
import json
import os
import re
import sys
import urllib.parse
import urllib.request

target_url = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:9210"
source_url = sys.argv[2].rstrip("/") if len(sys.argv) > 2 else "http://127.0.0.1:9200"
auth = os.environ.get("ES_DESTINO_AUTH", "")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
token_template = "com.jn.business.messages.JnMessages$JnNotifyUserAboutLoginToken"
index = "jn_email_template_message"
languages = ["english", "portuguese"]
telegram_paragraphs = {
    "portuguese": re.compile(r"</p><p>Você pode receber vagas .*?informe o token \{token\} </p></div>", re.S),
    "english": re.compile(r"</p><p>You can receive job openings .*?give it the token \{token\} </p></div>", re.S),
}


def call(url, method, path, body=None, authorization=""):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if authorization:
        request.add_header("Authorization", authorization)
    with opener.open(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


source_auth = auth if source_url == target_url else ""
print("origem:", call(source_url, "GET", "/", authorization=source_auth)["cluster_name"])
print("destino:", call(target_url, "GET", "/", authorization=auth)["cluster_name"])

query = {"size": 10, "query": {"term": {"templateId": token_template}}}
hits = call(source_url, "POST", "/%s/_search" % index, query, source_auth)["hits"]["hits"]
found = sorted(hit["_source"].get("language") for hit in hits)
if found != languages:
    raise SystemExit("esperava os dois idiomas do template na origem, achei %s" % found)

for hit in hits:
    source = hit["_source"]
    language = source["language"]
    message = source["message"]
    trimmed = telegram_paragraphs[language].sub("</p></div>", message)
    if "{token}" not in trimmed or "{accessLink}" not in trimmed:
        raise SystemExit("o template %s perdeu o paragrafo do token" % language)
    if "elegram" in trimmed:
        raise SystemExit("o template %s ainda fala do Telegram: o corte nao achou o trecho" % language)
    document = dict(source, message=trimmed)
    doc_path = "/%s/_doc/%s" % (index, urllib.parse.quote(hit["_id"], safe=""))
    result = call(target_url, "PUT", doc_path + "?refresh=true", document, auth)
    written = call(target_url, "GET", doc_path, authorization=auth)["_source"]
    same = "confere" if written == document else "DIFERENTE"
    print("%s %s: %s, %s (%d -> %d caracteres)" % (index, language, result["result"], same, len(message), len(trimmed)))
