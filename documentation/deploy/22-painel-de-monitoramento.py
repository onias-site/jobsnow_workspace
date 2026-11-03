# Painel do Cloud Monitoring "JobsNow - APIs, cache e banco": latencia, requisicoes, instancias e tempo cobrado das
# APIs do Cloud Run, uso e acertos do cache (Memorystore for Valkey), acumulo e idade das mensagens das filas (Pub/Sub)
# e CPU da VM do Elasticsearch.
# Gera o JSON do painel e o cria (ou substitui, pelo mesmo nome) com o gcloud. Pode rodar de novo.
# Uso: python 22-painel-de-monitoramento.py
import json
import os
import subprocess
import tempfile

PROJECT = "jobsnow-prd"
TITLE = "JobsNow - APIs, cache e banco"
GCLOUD = os.path.join(os.environ["LOCALAPPDATA"], "Google", "Cloud SDK", "google-cloud-sdk", "bin", "gcloud.cmd")
RUN = 'resource.type="cloud_run_revision"'
CACHE = 'resource.type="memorystore.googleapis.com/Instance"'
VM = 'resource.type="gce_instance"'
SUBSCRIPTION = 'resource.type="pubsub_subscription"'
TOPIC = 'resource.type="pubsub_topic"'
by_subscription = ["resource.label.subscription_id"]


def series(metric, resource, aligner, reducer, group_by, extra=""):
    return {
        "timeSeriesFilter": {
            "filter": 'metric.type="%s" %s%s' % (metric, resource, extra),
            "aggregation": {"alignmentPeriod": "60s", "perSeriesAligner": aligner, "crossSeriesReducer": reducer, "groupByFields": group_by},
        }
    }


def chart(title, label, *queries):
    data_sets = [{"timeSeriesQuery": query, "plotType": "LINE", "legendTemplate": legend} for query, legend in queries]
    return {"title": title, "xyChart": {"dataSets": data_sets, "yAxis": {"label": label, "scale": "LINEAR"}}}


def section(title):
    return {"title": title, "sectionHeader": {"subtitle": "", "dividerBelow": True}}


by_service = ["resource.label.service_name"]
widgets = [
    (section("APIs (Cloud Run: jobsnow-vis, jobsnow-js, jobsnow-front)"), 2),
    (chart("Latência p95 por serviço", "ms",
           (series("run.googleapis.com/request_latencies", RUN, "ALIGN_DELTA", "REDUCE_PERCENTILE_95", by_service), "")), 4),
    (chart("Latência p50 por serviço", "ms",
           (series("run.googleapis.com/request_latencies", RUN, "ALIGN_DELTA", "REDUCE_PERCENTILE_50", by_service), "")), 4),
    (chart("Requisições por segundo, por classe de resposta", "req/s",
           (series("run.googleapis.com/request_count", RUN, "ALIGN_RATE", "REDUCE_SUM", ["metric.label.response_code_class"]), "")), 4),
    (chart("Erros 5xx por serviço", "req/s",
           (series("run.googleapis.com/request_count", RUN, "ALIGN_RATE", "REDUCE_SUM", by_service, ' metric.label.response_code_class="5xx"'), "")), 4),
    (chart("Instâncias ativas por serviço", "instâncias",
           (series("run.googleapis.com/container/instance_count", RUN, "ALIGN_MAX", "REDUCE_SUM", by_service), "")), 4),
    (chart("Tempo cobrado por serviço (vira custo)", "s/s",
           (series("run.googleapis.com/container/billable_instance_time", RUN, "ALIGN_RATE", "REDUCE_SUM", by_service), "")), 4),
    (chart("CPU p95 por serviço", "uso",
           (series("run.googleapis.com/container/cpu/utilizations", RUN, "ALIGN_DELTA", "REDUCE_PERCENTILE_95", by_service), "")), 4),
    (chart("Memória p95 por serviço", "uso",
           (series("run.googleapis.com/container/memory/utilizations", RUN, "ALIGN_DELTA", "REDUCE_PERCENTILE_95", by_service), "")), 4),
    (section("Cache (Memorystore for Valkey: jobsnow-cache)"), 2),
    (chart("Acertos e falhas de leitura do cache", "leituras/s",
           (series("memorystore.googleapis.com/instance/stats/total_keyspace_hits_count", CACHE, "ALIGN_RATE", "REDUCE_SUM", []), "acertos (hits)"),
           (series("memorystore.googleapis.com/instance/stats/total_keyspace_misses_count", CACHE, "ALIGN_RATE", "REDUCE_SUM", []), "falhas (misses)")), 4),
    (chart("Comandos por segundo", "comandos/s",
           (series("memorystore.googleapis.com/instance/commandstats/total_calls_count", CACHE, "ALIGN_RATE", "REDUCE_SUM", []), "")), 4),
    (chart("Memória usada do cache", "uso",
           (series("memorystore.googleapis.com/instance/memory/average_utilization", CACHE, "ALIGN_MEAN", "REDUCE_MEAN", []), "")), 4),
    (chart("Chaves no cache", "chaves",
           (series("memorystore.googleapis.com/instance/keyspace/total_keys", CACHE, "ALIGN_MEAN", "REDUCE_SUM", []), "")), 4),
    (chart("Chaves expiradas e removidas por falta de memória", "chaves/s",
           (series("memorystore.googleapis.com/instance/stats/total_expired_keys_count", CACHE, "ALIGN_RATE", "REDUCE_SUM", []), "expiradas"),
           (series("memorystore.googleapis.com/instance/stats/total_evicted_keys_count", CACHE, "ALIGN_RATE", "REDUCE_SUM", []), "removidas (eviction)")), 4),
    (chart("Clientes conectados ao cache", "clientes",
           (series("memorystore.googleapis.com/instance/clients/total_connected_clients", CACHE, "ALIGN_MEAN", "REDUCE_SUM", []), "")), 4),
    (section("Filas (Pub/Sub: um tópico e uma assinatura por classe, consumidos pelo PM2 na VM)"), 2),
    (chart("Mensagens acumuladas por assinatura (fila crescendo = consumidor atrasado ou parado)", "mensagens",
           (series("pubsub.googleapis.com/subscription/num_undelivered_messages", SUBSCRIPTION, "ALIGN_MAX", "REDUCE_SUM", by_subscription), "")), 6),
    (chart("Idade da mensagem mais antiga sem confirmação, por assinatura", "s",
           (series("pubsub.googleapis.com/subscription/oldest_unacked_message_age", SUBSCRIPTION, "ALIGN_MAX", "REDUCE_MAX", by_subscription), "")), 6),
    (chart("Latência de confirmação p95, por assinatura (tempo de processamento)", "ms",
           (series("pubsub.googleapis.com/subscription/ack_latencies", SUBSCRIPTION, "ALIGN_DELTA", "REDUCE_PERCENTILE_95", by_subscription), "")), 4),
    (chart("Mensagens publicadas por tópico", "msg/s",
           (series("pubsub.googleapis.com/topic/send_message_operation_count", TOPIC, "ALIGN_RATE", "REDUCE_SUM", ["resource.label.topic_id"]), "")), 4),
    (chart("Mensagens entregues por assinatura", "msg/s",
           (series("pubsub.googleapis.com/subscription/sent_message_count", SUBSCRIPTION, "ALIGN_RATE", "REDUCE_SUM", by_subscription), "")), 4),
    (section("Banco (VM jobsnow-vm, Elasticsearch)"), 2),
    (chart("CPU da VM", "uso",
           (series("compute.googleapis.com/instance/cpu/utilization", VM, "ALIGN_MEAN", "REDUCE_MEAN", ["metric.label.instance_name"]), "")), 6),
    (chart("Rede da VM (bytes recebidos)", "bytes/s",
           (series("compute.googleapis.com/instance/network/received_bytes_count", VM, "ALIGN_RATE", "REDUCE_SUM", ["metric.label.instance_name"]), "")), 6),
]

tiles = []
x = y = 0
for widget, height in widgets:
    width = 12 if "sectionHeader" in widget else height + (2 if height == 4 else 0)
    if x + width > 12:
        x, y = 0, y + 4
    tile_height = 1 if "sectionHeader" in widget else 4
    tiles.append({"xPos": x, "yPos": y, "width": width, "height": tile_height, "widget": widget})
    x += width
    if "sectionHeader" in widget:
        x, y = 0, y + 1
dashboard = {"displayName": TITLE, "mosaicLayout": {"columns": 12, "tiles": tiles}}

listed = subprocess.run([GCLOUD, "monitoring", "dashboards", "list", "--project", PROJECT, "--format=json"], capture_output=True, text=True, check=True)
existing = [item for item in json.loads(listed.stdout) if item.get("displayName") == TITLE]
with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as config:
    json.dump(dashboard, config, ensure_ascii=False)
if existing:
    name = existing[0]["name"]
    dashboard["etag"] = existing[0]["etag"]
    with open(config.name, "w", encoding="utf-8") as file:
        json.dump(dashboard, file, ensure_ascii=False)
    command = [GCLOUD, "monitoring", "dashboards", "update", name, "--config-from-file", config.name, "--project", PROJECT, "--format=value(name)"]
else:
    command = [GCLOUD, "monitoring", "dashboards", "create", "--config-from-file", config.name, "--project", PROJECT, "--format=value(name)"]
result = subprocess.run(command, capture_output=True, text=True)
os.remove(config.name)
if result.returncode != 0:
    raise SystemExit(result.stderr[-1500:])
name = result.stdout.strip()
print("painel:", name)
print("https://console.cloud.google.com/monitoring/dashboards/builder/%s?project=%s" % (name.split("/")[-1], PROJECT))
