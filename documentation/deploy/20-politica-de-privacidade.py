# Politica de privacidade: copia do ES local (9200) para o destino os registros de jn_system_message com o texto da
# politica (com.js.business.privacy.JsPrivacyPolicyMessages.privacyPolicy, portugues e ingles), com o mesmo id. A origem
# e o ES local depois de o PrivacyPolicyTest regravar as sementes de JsPrivacyPolicyMessages.getSeeds(). Grava por cima:
# rodar de novo depois de mudar o texto atualiza o destino. O cache das entidades (1 hora) segura o texto antigo ate
# expirar ou ate a API js reiniciar. No tunel de producao, invalida tambem o CDN da rota (o navegador guarda 5 minutos).
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python 20-politica-de-privacidade.py [url do destino] [url da origem]
import json
import subprocess
import os
import sys
import urllib.parse
import urllib.request

target_url = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:9210"
source_url = sys.argv[2].rstrip("/") if len(sys.argv) > 2 else "http://127.0.0.1:9200"
auth = os.environ.get("ES_DESTINO_AUTH", "")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
index = "jn_system_message"
system_message_name = "com.js.business.privacy.JsPrivacyPolicyMessages.privacyPolicy"
languages = ("portuguese", "english")


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
hits = call(source_url, "POST", "/%s/_search" % index, {"size": 500, "query": {"match_all": {}}})["hits"]["hits"]
policies = [hit for hit in hits if hit["_source"].get("systemMessageName") == system_message_name]
found = sorted(hit["_source"].get("language") for hit in policies)
if found != sorted(languages):
    raise SystemExit("esperava os idiomas %s na origem, achei %s: rode antes o PrivacyPolicyTest" % (list(languages), found))

for hit in policies:
    path = "/%s/_doc/%s?refresh=true" % (index, urllib.parse.quote(hit["_id"], safe=""))
    result = call(target_url, "PUT", path, hit["_source"], auth)
    print("%s: %s (%d caracteres)" % (hit["_source"]["language"], result["result"], len(hit["_source"]["message"][0])))

# o CDN da rota /privacy-policy (09-criar-balanceador.ps1) guarda o texto por 1 ano: so a producao (o tunel) o invalida
if target_url.endswith(":9210"):
    gcloud = os.path.join(os.environ["LOCALAPPDATA"], "Google", "Cloud SDK", "google-cloud-sdk", "bin", "gcloud.cmd")
    command = [gcloud, "compute", "url-maps", "invalidate-cdn-cache", "jobsnow-lb", "--global", "--host", "login.onias.site",
               "--path", "/privacy-policy", "--async", "--project", "jobsnow-prd"]
    if subprocess.call(command) != 0:
        raise SystemExit("falhou a invalidacao do CDN da politica de privacidade")
    print("CDN da politica: invalidacao pedida")
