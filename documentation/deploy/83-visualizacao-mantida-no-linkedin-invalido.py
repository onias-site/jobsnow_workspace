# Visualizacao mantida no LinkedIn invalido (2026-11-15): quando o operador confirma ("Sim" no /verifyLinkedinAddress)
# que o LinkedIn reportado e invalido, a visualizacao do recrutador nao e mais apagada (deleteAnyWhere): continua na
# gemea vis_inactive_viewed_resume, onde o reporte a pos (aba "Indesejados"). Pedido do usuario, que desfez o pedido
# anterior. O comportamento esta no codigo; este script leva so o texto da resposta ao operador
# (VisSupportVerifyLinkedinMessages.confirmedInvalid, pt e en, em jn_system_message, regra "igual"), que dizia "a
# visualizacao do recrutador foi apagada". Sementes em 83-sementes-visualizacao-mantida-no-linkedin-invalido.jsonl,
# mesmo _id do local.
# Roda junto com o deploy da API vis e dos consumidores (antes ou depois: so muda o texto). Idempotente.
# Cache das entidades: 1 h; publique nova revisao e reinicie os consumidores (pm2 restart all), ou espere a hora passar.
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python 83-visualizacao-mantida-no-linkedin-invalido.py [destino]
#      ou: powershell -File com-tunel-de-producao.ps1 -Script 83-visualizacao-mantida-no-linkedin-invalido.py
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

arguments = [argument for argument in sys.argv[1:] if not argument.startswith("--")]
target_url = arguments[0].rstrip("/") if arguments else "http://127.0.0.1:9210"
auth = os.environ.get("ES_DESTINO_AUTH", "")
here = os.path.dirname(os.path.abspath(__file__))
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def call(method, path, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(target_url + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if auth:
        request.add_header("Authorization", auth)
    try:
        with opener.open(request, timeout=60) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"{}")


status, cluster = call("GET", "/")
print("cluster:", cluster.get("cluster_name"))
failures = 0
with open(os.path.join(here, "83-sementes-visualizacao-mantida-no-linkedin-invalido.jsonl"), encoding="utf-8") as seeds_file:
    seeds = [json.loads(line) for line in seeds_file if line.strip()]
for seed in seeds:
    index = seed["index"]
    path = "/%s/_doc/%s" % (index, urllib.parse.quote(seed["id"], safe=""))
    source = seed["source"]
    call("PUT", path + "?refresh=true", source)
    status, written = call("GET", path)
    ok = status == 200 and written.get("_source") == source
    failures += 0 if ok else 1
    print("%-20s %s %s" % (index, seed["id"][:42], "ok" if ok else "FALHOU"))
print("sementes: %d" % len(seeds))
sys.exit(1 if failures else 0)
