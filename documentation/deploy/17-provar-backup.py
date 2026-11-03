# Backup do ES no bucket jobsnow-backup: registra o repositorio gcs, grava um snapshot real dos centros de custo e restaura
# um indice com outro nome para provar que o backup le de volta. O indice temporario e apagado no fim; o snapshot fica.
# O bucket nasce antes, por: gcloud storage buckets create gs://jobsnow-backup --project=jobsnow-prd
#   --location=southamerica-east1 --uniform-bucket-level-access --public-access-prevention
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python 17-provar-backup.py [url]
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.request

url = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:9210"
auth = os.environ.get("ES_DESTINO_AUTH", "")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
bucket = "jobsnow-backup"
probe_index = "jn_bot_command"
restored_index = "temporario_prova_de_backup"


def call(method, path, body=None, timeout=60):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if auth:
        request.add_header("Authorization", auth)
    try:
        with opener.open(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise SystemExit("%s %s: HTTP %d %s" % (method, path, error.code, error.read().decode("utf-8")[:700]))


if call("GET", "/")["cluster_name"] != "jobsnow-prd":
    raise SystemExit("o destino nao e jobsnow-prd")

print("registro:", call("PUT", "/_snapshot/" + bucket, {"type": "gcs", "settings": {"bucket": bucket}}))
print("verificacao:", list(call("POST", "/_snapshot/%s/_verify" % bucket)["nodes"].values()))

name = "backup-" + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S-prova")
started = time.time()
snapshot = call("PUT", "/_snapshot/%s/%s?wait_for_completion=true" % (bucket, name), {"indices": "jn_*,js_*,vis_*,jb_*", "ignore_unavailable": True, "include_global_state": False}, timeout=900)["snapshot"]
print("snapshot %s: %s, %d indices, shards %s, %d s" % (name, snapshot["state"], len(snapshot["indices"]), snapshot["shards"], time.time() - started))
if snapshot["state"] != "SUCCESS":
    raise SystemExit("snapshot sem sucesso")

expected = call("GET", "/%s/_count" % probe_index)["count"]
call("POST", "/_snapshot/%s/%s/_restore?wait_for_completion=true" % (bucket, name), {"indices": probe_index, "include_global_state": False, "rename_pattern": ".+", "rename_replacement": restored_index, "index_settings": {"index.number_of_replicas": 0}}, timeout=300)
call("POST", "/%s/_refresh" % restored_index)
restored = call("GET", "/%s/_count" % restored_index)["count"]
call("DELETE", "/" + restored_index)
print("restauracao de %s: %d registros no original, %d no restaurado" % (probe_index, expected, restored))
if expected != restored:
    raise SystemExit("contagens diferentes")
print("snapshots no repositorio:", len(call("GET", "/_snapshot/%s/_all" % bucket)["snapshots"]))
