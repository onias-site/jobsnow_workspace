# Painel local das filas do Pub/Sub (jobsnow-prd): escolhe uma assinatura (ou todas) e o periodo; mostra mensagens
# publicadas, entregues e confirmadas, acumulo, idade da mais antiga sem confirmacao, latencia de confirmacao e de
# publicacao (p50/p95/p99), consumidores conectados (streaming pull) e codigos de resposta, em graficos de linha e
# pizzas, e uma tabela por fila com a configuracao (prazo de ack, fila de mensagens mortas, retencao).
# Metricas pela API do Cloud Monitoring, com o token do gcloud do usuario. O Pub/Sub manda as metricas com cerca
# de 1 a 3 minutos de atraso.
# Desde 2026-11-05 a tabela das filas e o quadro "Queries por fila" mostram as chamadas ao Elasticsearch de cada
# mensagem: as que o consumidor grava na linha da mensagem (log mensagens, CcpMessageReceiver) e, com o
# 33-slowlog-de-todas-as-queries.py ligado, o tempo de cada shard por dentro do Elasticsearch (medicao_elasticsearch.py).
# Uso: python 29-filas-do-pubsub.py [porta]   (abre http://127.0.0.1:8767; atalho na area de trabalho)
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import medicao_elasticsearch  # noqa: E402

PROJECT = "jobsnow-prd"
MESSAGES_LOG_NAME = "projects/%s/logs/mensagens" % PROJECT
GCLOUD = os.path.join(os.environ["LOCALAPPDATA"], "Google", "Cloud SDK", "google-cloud-sdk", "bin", "gcloud.cmd")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8767
POINTS = 240
SUBSCRIPTION = "pubsub_subscription"
TOPIC = "pubsub_topic"
BY_SUBSCRIPTION = ["resource.label.subscription_id"]
BY_TOPIC = ["resource.label.topic_id"]
token_lock = threading.Lock()
token_cache = {"value": "", "expires": 0.0}


def gcloud(*args):
    # sem janela de console piscando quando o painel roda pelo atalho (pythonw)
    no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    result = subprocess.run([GCLOUD, *args], capture_output=True, text=True, creationflags=no_window)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return result.stdout.strip()


def access_token():
    with token_lock:
        if time.time() < token_cache["expires"]:
            return token_cache["value"]
        token_cache["value"] = gcloud("auth", "print-access-token")
        token_cache["expires"] = time.time() + 45 * 60
        return token_cache["value"]


CACHE_SECONDS = 60
cache_lock = threading.Lock()
response_cache = {}


def call(url):
    # cota da API do Monitoring: 180 requisicoes por minuto por usuario. Resposta igual reaproveitada por 1 minuto
    # (atualizacao automatica, abas repetidas) e, no 429, espera e tenta de novo.
    with cache_lock:
        cached = response_cache.get(url)
        if cached and time.time() - cached[0] < CACHE_SECONDS:
            return cached[1]
    # token revogado antes dos 45 min (novo login do gcloud): descarta, pede outro e tenta de novo
    renewed = False
    for wait in (5, 15, 30, 0):
        request = urllib.request.Request(url)
        request.add_header("Authorization", "Bearer " + access_token())
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                content = json.load(response)
            break
        except urllib.error.HTTPError as error:
            if error.code == 401 and not renewed:
                renewed = True
                with token_lock:
                    token_cache["expires"] = 0.0
                continue
            if error.code != 429 or not wait:
                raise
            time.sleep(wait)
    with cache_lock:
        for key in [key for key, (moment, _) in response_cache.items() if time.time() - moment >= CACHE_SECONDS]:
            del response_cache[key]
        response_cache[url] = (time.time(), content)
    return content


def forget_token():
    with token_lock:
        token_cache["expires"] = 0.0


def cache_of(payload):
    # os comandos ao cache da mensagem; nada nas linhas anteriores a medicao do cache
    if "cacheCallsCount" not in payload:
        return None
    by_entity = [{"entity": name, "hits": int(counters.get("hits", 0)), "misses": int(counters.get("misses", 0))}
                 for name, counters in (payload.get("cacheByEntity") or {}).items()]
    return {"hits": int(payload.get("cacheHits", 0)), "misses": int(payload.get("cacheMisses", 0)), "writes": int(payload.get("cacheWrites", 0)),
            "clientMs": float(payload.get("cacheClientMs", 0)), "byEntity": by_entity}


def db_calls(subscription, start, end, maximum):
    # as mensagens que tocaram o Elasticsearch ou o cache (Memorystore), cada uma com as suas chamadas, o tempo por dentro
    # do ES e os comandos ao cache (estes desde a medicao do cache, 2026-11-05 a noite)
    filters = ['logName="%s"' % MESSAGES_LOG_NAME, 'timestamp>="%s"' % start, 'timestamp<"%s"' % end,
               "(jsonPayload.dbCallsCount>0 OR jsonPayload.cacheCallsCount>0)"]
    if subscription:
        filters.append('jsonPayload.topic="%s"' % subscription.replace('"', '\\"'))
    entries, truncated = medicao_elasticsearch.list_entries(access_token, forget_token, PROJECT, filters, maximum)
    payloads = [entry.get("jsonPayload", {}) for entry in entries]
    traces = [payload.get("traceId", "") for payload in payloads]
    slowlog = medicao_elasticsearch.read_slowlog(access_token, forget_token, PROJECT, start, end, traces)
    messages = []
    for entry, payload in zip(entries, payloads):
        messages.append({
            "timestamp": entry.get("timestamp", ""), "topic": payload.get("topic", ""), "result": payload.get("result", ""),
            "durationMs": float(payload.get("durationMs", 0) or 0), "db": medicao_elasticsearch.enrich(payload, slowlog),
            "cache": cache_of(payload),
        })
    return {"messages": messages, "truncated": truncated, "slowlogLines": slowlog["lines"], "slowlogTruncated": slowlog["truncated"]}


def subscriptions():
    listed = json.loads(gcloud("pubsub", "subscriptions", "list", "--project", PROJECT, "--format=json"))
    result = []
    for item in listed:
        dead_letter = item.get("deadLetterPolicy", {})
        result.append({
            "name": item["name"].rsplit("/", 1)[-1], "topic": item.get("topic", "").rsplit("/", 1)[-1],
            "ackDeadline": item.get("ackDeadlineSeconds", 10), "retention": item.get("messageRetentionDuration", ""),
            "deadLetter": dead_letter.get("deadLetterTopic", "").rsplit("/", 1)[-1],
            "maxAttempts": dead_letter.get("maxDeliveryAttempts", 0),
            "delivery": "push" if item.get("pushConfig", {}).get("pushEndpoint") else "pull",
        })
    result.sort(key=lambda item: item["name"])
    return result


def seconds_between(start, end):
    return (datetime.fromisoformat(end.replace("Z", "+00:00")) - datetime.fromisoformat(start.replace("Z", "+00:00"))).total_seconds()


def value_of(point):
    value = point["value"]
    if "distributionValue" in value:
        return value["distributionValue"]
    if "doubleValue" in value:
        return float(value["doubleValue"])
    if "boolValue" in value:
        return 1.0 if value["boolValue"] else 0.0
    return float(value.get("int64Value", 0))


def series(resource, metric, aligner, reducer, group_by, extra, start, end, period):
    params = [
        ("filter", 'metric.type="pubsub.googleapis.com/%s" resource.type="%s"%s' % (metric, resource, extra)),
        ("interval.startTime", start), ("interval.endTime", end),
        ("aggregation.alignmentPeriod", "%ds" % period), ("aggregation.perSeriesAligner", aligner),
        ("aggregation.crossSeriesReducer", reducer),
    ]
    params.extend(("aggregation.groupByFields", field) for field in group_by)
    result = []
    token = ""
    while True:
        query = params + ([("pageToken", token)] if token else [])
        page = call("https://monitoring.googleapis.com/v3/projects/%s/timeSeries?%s" % (PROJECT, urllib.parse.urlencode(query)))
        for item in page.get("timeSeries", []):
            labels = dict(item.get("metric", {}).get("labels", {}))
            labels.update(item.get("resource", {}).get("labels", {}))
            points = [[point["interval"]["endTime"], value_of(point)] for point in reversed(item.get("points", []))]
            result.append({"labels": labels, "points": points})
        token = page.get("nextPageToken", "")
        if not token:
            return result


def bucket_bounds(options, count):
    if "exponentialBuckets" in options:
        spec = options["exponentialBuckets"]
        scale, growth = float(spec["scale"]), float(spec["growthFactor"])
        return [0.0] + [scale * growth ** index for index in range(count)]
    if "linearBuckets" in options:
        spec = options["linearBuckets"]
        offset, width = float(spec.get("offset", 0)), float(spec["width"])
        return [min(0.0, offset)] + [offset + width * index for index in range(count)]
    bounds = [float(bound) for bound in options.get("explicitBuckets", {}).get("bounds", [])]
    return [0.0] + bounds + [bounds[-1] * 2 if bounds else 1.0] * max(0, count - len(bounds))


def merge(distributions):
    merged = {"counts": [], "options": None}
    for distribution in distributions:
        counts = [int(count) for count in distribution.get("bucketCounts", [])]
        merged["options"] = merged["options"] or distribution.get("bucketOptions", {})
        if len(counts) > len(merged["counts"]):
            merged["counts"].extend([0] * (len(counts) - len(merged["counts"])))
        for index, count in enumerate(counts):
            merged["counts"][index] += count
    return merged


def percentile(merged, fraction):
    # mesma interpolacao linear dentro do balde que o REDUCE_PERCENTILE do Monitoring faz
    counts = merged["counts"]
    total = sum(counts)
    if not total:
        return None
    bounds = bucket_bounds(merged["options"], len(counts) + 1)
    target = fraction * total
    seen = 0
    for index, count in enumerate(counts):
        if count and seen + count >= target:
            lower, upper = bounds[index], bounds[min(index + 1, len(bounds) - 1)]
            return lower + (upper - lower) * (target - seen) / count
        seen += count
    return bounds[len(counts)]


def percentiles(distributions):
    merged = merge(distributions)
    return {"p50": percentile(merged, 0.50), "p95": percentile(merged, 0.95), "p99": percentile(merged, 0.99)}


def by_label(items, label):
    return {item["labels"].get(label, "?"): item["points"] for item in items}


def summed_timeline(grouped, grid):
    totals = dict.fromkeys(grid, 0.0)
    for points in grouped.values():
        for moment, value in points:
            totals[moment] = totals.get(moment, 0.0) + value
    return [[moment, totals[moment]] for moment in sorted(totals)]


def percentile_timeline(grouped):
    moments = {}
    for points in grouped.values():
        for moment, distribution in points:
            moments.setdefault(moment, []).append(distribution)
    timeline = {"p50": [], "p95": [], "p99": []}
    for moment in sorted(moments):
        values = percentiles(moments[moment])
        for key in timeline:
            if values[key] is not None:
                timeline[key].append([moment, values[key]])
    return timeline


def metrics(subscription, topic, start, end):
    span = seconds_between(start, end)
    period = max(60, int(span / POINTS) // 60 * 60)
    whole = max(60, int(span + 59) // 60 * 60)
    on_subscription = ' resource.labels.subscription_id="%s"' % subscription if subscription else ""
    on_topic = ' resource.labels.topic_id="%s"' % topic if topic else ""
    by_code = ["metric.label.response_code"]
    # 11 consultas por busca (eram 32): totais saem da soma das linhas do tempo e os percentis dos baldes das distribuicoes
    queries = {
        "published": (TOPIC, "topic/send_message_operation_count", "ALIGN_DELTA", "REDUCE_SUM", BY_TOPIC, on_topic, period),
        "delivered": (SUBSCRIPTION, "subscription/sent_message_count", "ALIGN_DELTA", "REDUCE_SUM", BY_SUBSCRIPTION, on_subscription, period),
        "acked": (SUBSCRIPTION, "subscription/ack_message_count", "ALIGN_DELTA", "REDUCE_SUM", BY_SUBSCRIPTION, on_subscription, period),
        "modAck": (SUBSCRIPTION, "subscription/mod_ack_deadline_message_count", "ALIGN_DELTA", "REDUCE_SUM", BY_SUBSCRIPTION, on_subscription, whole),
        "backlog": (SUBSCRIPTION, "subscription/num_undelivered_messages", "ALIGN_MAX", "REDUCE_SUM", BY_SUBSCRIPTION, on_subscription, period),
        "oldest": (SUBSCRIPTION, "subscription/oldest_unacked_message_age", "ALIGN_MAX", "REDUCE_MAX", BY_SUBSCRIPTION, on_subscription, period),
        "streams": (SUBSCRIPTION, "subscription/open_streaming_pulls", "ALIGN_MEAN", "REDUCE_SUM", BY_SUBSCRIPTION + ["metric.label.status"], on_subscription, period),
        "ackLatency": (SUBSCRIPTION, "subscription/ack_latencies", "ALIGN_DELTA", "REDUCE_SUM", BY_SUBSCRIPTION, on_subscription, period),
        "publishLatency": (TOPIC, "topic/send_request_latencies", "ALIGN_DELTA", "REDUCE_SUM", [], on_topic, period),
        "sizes": (TOPIC, "topic/message_sizes", "ALIGN_DELTA", "REDUCE_SUM", [], on_topic, whole),
        "publishCodes": (TOPIC, "topic/send_request_count", "ALIGN_DELTA", "REDUCE_SUM", by_code, on_topic, whole),
        "pullCodes": (SUBSCRIPTION, "subscription/streaming_pull_response_count", "ALIGN_DELTA", "REDUCE_SUM", by_code, on_subscription, whole),
    }
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {key: pool.submit(series, *spec[:6], start, end, spec[6]) for key, spec in queries.items()}
        found = {key: future.result() for key, future in futures.items()}
    published = by_label(found["published"], "topic_id")
    delivered = by_label(found["delivered"], "subscription_id")
    acked = by_label(found["acked"], "subscription_id")
    backlog = by_label(found["backlog"], "subscription_id")
    oldest = by_label(found["oldest"], "subscription_id")
    ack_latency = by_label(found["ackLatency"], "subscription_id")
    streams_by_subscription = {}
    streams_by_status = {}
    for item in found["streams"]:
        status = item["labels"].get("status", "?")
        name = item["labels"].get("subscription_id", "?")
        streams_by_subscription[name] = summed_timeline({0: streams_by_subscription.get(name, []), 1: item["points"]}, [])
        streams_by_status[status] = summed_timeline({0: streams_by_status.get(status, []), 1: item["points"]}, [])
    grid = sorted({moment for points in backlog.values() for moment, _ in points})
    total = lambda grouped: {name: sum(value for _, value in points) for name, points in grouped.items()}
    peak = lambda grouped: {name: max((value for _, value in points), default=0) for name, points in grouped.items()}
    whole_codes = lambda items: {item["labels"].get("response_code", "?"): sum(value for _, value in item["points"]) for item in items}
    ack_overall = percentiles([distribution for points in ack_latency.values() for _, distribution in points])
    publish_overall = percentiles([distribution for item in found["publishLatency"] for _, distribution in item["points"]])
    sizes = percentiles([distribution for item in found["sizes"] for _, distribution in item["points"]])
    ack_timeline = percentile_timeline(ack_latency)
    publish_timeline = percentile_timeline({index: item["points"] for index, item in enumerate(found["publishLatency"])})
    oldest_timeline = {}
    for points in oldest.values():
        for moment, value in points:
            oldest_timeline[moment] = max(oldest_timeline.get(moment, 0.0), value)
    return {
        "period": period,
        "timeline": {
            "published": summed_timeline(published, grid), "delivered": summed_timeline(delivered, grid),
            "acked": summed_timeline(acked, grid), "backlog": summed_timeline(backlog, grid),
            "oldest": [[moment, oldest_timeline[moment]] for moment in sorted(oldest_timeline)],
            "ackP50": ack_timeline["p50"], "ackP95": ack_timeline["p95"], "ackP99": ack_timeline["p99"],
            "publishP50": publish_timeline["p50"], "publishP95": publish_timeline["p95"], "publishP99": publish_timeline["p99"],
        },
        "grouped": {"backlogBySubscription": backlog, "oldestBySubscription": oldest,
                    "streamsBySubscription": streams_by_subscription, "streamsByStatus": streams_by_status},
        "totals": {
            "publishedByTopic": total(published), "deliveredBySubscription": total(delivered), "ackedBySubscription": total(acked),
            "ackP95BySubscription": {name: value for name, value in
                                     ((name, percentiles([d for _, d in points])["p95"]) for name, points in ack_latency.items()) if value is not None},
            "modAckBySubscription": {item["labels"].get("subscription_id", "?"): sum(value for _, value in item["points"]) for item in found["modAck"]},
            "publishCodes": whole_codes(found["publishCodes"]), "pullCodes": whole_codes(found["pullCodes"]),
            "ackP50": {"total": ack_overall["p50"]}, "ackP95": {"total": ack_overall["p95"]}, "ackP99": {"total": ack_overall["p99"]},
            "publishP50": {"total": publish_overall["p50"]}, "publishP95": {"total": publish_overall["p95"]},
            "publishP99": {"total": publish_overall["p99"]},
            "sizeP50": {"total": sizes["p50"]}, "sizeP95": {"total": sizes["p95"]},
            "backlogMaxBySubscription": peak(backlog), "oldestMaxBySubscription": peak(oldest),
        },
    }


class Handler(BaseHTTPRequestHandler):
    def send(self, status, content_type, payload):
        data = payload.encode() if isinstance(payload, str) else payload
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, status, value):
        self.send(status, "application/json; charset=utf-8", json.dumps(value))

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        query = {key: values[0] for key, values in urllib.parse.parse_qs(parsed.query).items()}
        try:
            if parsed.path == "/":
                return self.send(200, "text/html; charset=utf-8", PAGE.replace("__PROJECT__", PROJECT))
            if parsed.path == "/api/subscriptions":
                return self.send_json(200, subscriptions())
            if parsed.path == "/api/db":
                return self.send_json(200, db_calls(query.get("subscription", ""), query["start"], query["end"], int(query.get("max", "20000"))))
            if parsed.path == "/api/metrics":
                return self.send_json(200, metrics(query.get("subscription", ""), query.get("topic", ""), query["start"], query["end"]))
            return self.send_json(404, {"error": "not found"})
        except urllib.error.HTTPError as error:
            return self.send_json(502, {"error": error.read().decode(errors="replace")})
        except Exception as error:
            return self.send_json(500, {"error": "%s: %s" % (type(error).__name__, error)})

    def log_message(self, format, *args):
        if sys.stderr:
            sys.stderr.write("%s %s\n" % (self.log_date_time_string(), format % args))


PAGE = r"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Filas do Pub/Sub</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--fg:#1d2330;--muted:#667085;--line:#e3e6eb;--accent:#2563eb;--grid:#eef0f3}
@media (prefers-color-scheme:dark){:root{--bg:#12151b;--card:#1b1f27;--fg:#e6e8ec;--muted:#98a2b3;--line:#2c323d;--accent:#5b8def;--grid:#232833}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,Segoe UI,sans-serif}
header{padding:16px 20px;border-bottom:1px solid var(--line);background:var(--card)}h1{margin:0;font-size:18px}
main{padding:16px 20px;max-width:1400px;margin:0 auto}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px;margin-bottom:14px;min-width:0}
form{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;align-items:end}
label{display:flex;flex-direction:column;gap:4px;font-size:12px;color:var(--muted)}
input,select,button{font:inherit;padding:7px 9px;border:1px solid var(--line);border-radius:7px;background:var(--bg);color:var(--fg)}
button{background:var(--accent);color:#fff;border:0;cursor:pointer}button.ghost{background:transparent;color:var(--accent);border:1px solid var(--line)}
.row{display:flex;gap:8px;flex-wrap:wrap;grid-column:1/-1;align-items:center}.row button{padding:4px 10px}
.chip{flex-direction:row;align-items:center;gap:5px;font-size:13px;font-weight:600;padding:4px 10px;border:1px solid var(--line);border-radius:7px;cursor:pointer;color:var(--fg)}
.chip input{margin:0}.wider{grid-column:span 2}@media (max-width:700px){.wider{grid-column:1/-1}}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin-bottom:14px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px}
.tile b{display:block;font-size:20px}.tile span{font-size:12px;color:var(--muted)}.tile.alert{border-color:#dc2626}.tile.alert b{color:#dc2626}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:14px}
@media (max-width:520px){.grid2{grid-template-columns:1fr}}
.grid3{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:14px}
.chart{position:relative}.chart svg{width:100%;height:auto;display:block}
.tip{position:absolute;pointer-events:none;background:var(--card);border:1px solid var(--line);border-radius:6px;padding:4px 8px;font-size:12px;white-space:nowrap;display:none;box-shadow:0 2px 8px rgba(0,0,0,.12);z-index:2}
.keys{display:flex;gap:12px;flex-wrap:wrap;font-size:12px;color:var(--muted);margin-top:4px}.keys i{display:inline-block;width:10px;height:3px;margin-right:5px;vertical-align:middle}
.pie{display:flex;gap:16px;align-items:center;flex-wrap:wrap}.pie svg{flex:none}
.legend{display:flex;flex-direction:column;gap:3px;font-size:13px;min-width:0}.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px}
.slice{cursor:pointer}div.slice:hover{text-decoration:underline}
h2{font-size:15px;margin:0 0 10px}
table{width:100%;border-collapse:collapse;font-size:12.5px}th,td{padding:5px 7px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{color:var(--muted);position:sticky;top:0;background:var(--card);cursor:pointer}td.num,th.num{text-align:right;white-space:nowrap}td.url{word-break:break-all}
td.src{word-break:break-all;max-width:420px;color:var(--muted);font-family:ui-monospace,Consolas,monospace;font-size:11px}
tr.pick{cursor:pointer}tr.pick:hover td{background:var(--bg)}
.scroll{max-height:620px;overflow:auto}.muted{color:var(--muted)}.err{color:#d92d20;white-space:pre-wrap}.bad{color:#dc2626;font-weight:700}.ok{color:#16a34a;font-weight:700}
</style></head><body>
<header><h1>Filas do Pub/Sub · __PROJECT__</h1></header>
<main>
<div class="card"><form id="f">
<label class="wider">Fila (assinatura)<select id="sub"><option value="">(todas as filas)</option></select></label>
<label>De<input type="datetime-local" id="start"></label>
<label>Até<input type="datetime-local" id="end"></label>
<button type="submit">Buscar</button>
<div class="row"><span class="muted">Período:</span><span id="presets" style="display:contents"></span>
<label class="chip" style="margin-left:auto"><input type="checkbox" id="auto">atualizar a cada minuto (últimos dados)</label></div>
</form></div>
<div id="out"></div>
</main>
<script>
const $=id=>document.getElementById(id);
const pad=n=>String(n).padStart(2,'0');
const toLocal=d=>`${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const short=n=>n.includes('.')?n.slice(n.lastIndexOf('.')+1):n;
let rangeMinutes=1440,subs=[],tableSort=['backlogNow',-1],lastData=null,lastDb=null,dbError='';
function setRange(minutes){rangeMinutes=minutes;const end=new Date();$('end').value=toLocal(end);$('start').value=toLocal(new Date(end-minutes*60000));}
[['1 h',60],['6 h',360],['24 h',1440],['7 dias',10080],['30 dias',43200],['6 semanas',60480]].forEach(([t,m])=>{const b=document.createElement('button');b.type='button';b.className='ghost';b.textContent=t;b.onclick=()=>{setRange(m);run();};$('presets').appendChild(b);});
const params=new URLSearchParams(location.search);
setRange(+(params.get('minutes')||1440));
$('f').onsubmit=e=>{e.preventDefault();rangeMinutes=null;run();};
$('sub').onchange=()=>run();
let timer=null;$('auto').onchange=()=>{clearInterval(timer);if($('auto').checked)timer=setInterval(()=>{setRange(rangeMinutes||1440);run(true);},60000);};
fetch('/api/subscriptions').then(r=>r.json()).then(list=>{subs=list;list.forEach(s=>{const o=document.createElement('option');o.value=s.name;o.textContent=short(s.name)+(short(s.topic)!==short(s.name)?'  ←  '+short(s.topic):'');o.title=s.name;$('sub').appendChild(o);});
  if(params.get('sub'))$('sub').value=params.get('sub');run();});

const fmtInt=v=>isNaN(v)?'–':Math.round(v).toLocaleString('pt-BR');
const fmtMs=v=>v==null||isNaN(v)?'–':v>=1000?(v/1000).toFixed(v>=10000?0:2)+' s':v.toFixed(v<10?1:0)+' ms';
const fmtUs=v=>fmtMs(v/1000);
function fmtAge(s){if(s==null||isNaN(s))return'–';if(s<60)return Math.round(s)+' s';if(s<3600)return Math.round(s/60)+' min';if(s<86400)return(s/3600).toFixed(1)+' h';return(s/86400).toFixed(1)+' d';}
const fmtBytes=v=>{if(v==null||isNaN(v))return'–';const u=['B','KB','MB','GB'];let i=0;while(Math.abs(v)>=1024&&i<3){v/=1024;i++;}return v.toFixed(v<10&&i?1:0)+' '+u[i];};
const last=pts=>pts&&pts.length?pts[pts.length-1][1]:NaN;
const sum=obj=>Object.values(obj||{}).reduce((a,b)=>a+b,0);
function pct(sorted,p){if(!sorted.length)return NaN;const i=(sorted.length-1)*p/100,lo=Math.floor(i),hi=Math.ceil(i);return sorted[lo]+(sorted[hi]-sorted[lo])*(i-lo);}
const dashMs=v=>v==null||isNaN(v)?'–':fmtMs(v);
const PALETTE=['#2563eb','#7c3aed','#db2777','#0d9488','#ca8a04','#ea580c','#16a34a','#0891b2','#be123c','#4f46e5','#64748b','#94a3b8'];

const charts={};
function lineChart(id,title,lines,fmt,note){
  lines=lines.filter(l=>l.points&&l.points.length);const all=lines.flatMap(l=>l.points);
  if(!all.length)return `<div class="card"><h2>${title}</h2><div class="muted">sem dados no período</div></div>`;
  const W=600,H=190,L=60,R=8,T=8,B=22;
  const times=all.map(p=>+new Date(p[0])),t0=Math.min(...times),t1=Math.max(...times);
  // contagens (inteiras) abaixo de 4: as 5 marcas cairiam em fracoes e o formato inteiro repetiria rotulos (0 0 1 1 1)
  const peak=Math.max(...all.map(p=>p[1])),integers=all.every(p=>Number.isInteger(p[1]));
  const top=integers&&peak<4?4:(peak*1.1)||1;
  const x=t=>L+(t-t0)/((t1-t0)||1)*(W-L-R),y=v=>T+(1-v/top)*(H-T-B);
  let g='';for(let k=0;k<=4;k++){const v=top*k/4,yy=y(v);g+=`<line x1="${L}" x2="${W-R}" y1="${yy}" y2="${yy}" stroke="var(--grid)"/><text x="${L-6}" y="${yy+4}" text-anchor="end" font-size="10" fill="var(--muted)">${fmt(v)}</text>`;}
  const span=t1-t0;for(let k=0;k<=4;k++){const t=t0+span*k/4,d=new Date(t);const label=span>2*86400000?`${pad(d.getDate())}/${pad(d.getMonth()+1)}`:`${pad(d.getHours())}:${pad(d.getMinutes())}`;g+=`<text x="${x(t)}" y="${H-6}" text-anchor="middle" font-size="10" fill="var(--muted)">${label}</text>`;}
  const paths=lines.map(l=>`<polyline fill="none" stroke="${l.color}" stroke-width="1.8" points="${l.points.map(p=>x(+new Date(p[0])).toFixed(1)+','+y(p[1]).toFixed(1)).join(' ')}"/>`).join('');
  const keys=lines.length>1?`<div class="keys">${lines.map(l=>`<span><i style="background:${l.color}"></i>${esc(l.name)}</span>`).join('')}</div>`:'';
  charts[id]={lines,fmt,geom:{W,L,R,t0,t1}};
  return `<div class="card"><h2>${title}${note?` <span class="muted" style="font-weight:normal;font-size:12px">${note}</span>`:''}</h2><div class="chart" data-chart="${id}"><svg viewBox="0 0 ${W} ${H}">${g}${paths}<line class="cursor" x1="0" x2="0" y1="${T}" y2="${H-B}" stroke="var(--muted)" stroke-dasharray="3 3" visibility="hidden"/></svg><div class="tip"></div></div>${keys}</div>`;
}
function wireCharts(){
  document.querySelectorAll('.chart').forEach(el=>{const c=charts[el.dataset.chart];if(!c)return;const svg=el.querySelector('svg'),tip=el.querySelector('.tip'),cur=svg.querySelector('.cursor');
    el.onmousemove=e=>{const r=svg.getBoundingClientRect(),vx=(e.clientX-r.left)/r.width*c.geom.W;const t=c.geom.t0+(vx-c.geom.L)/(c.geom.W-c.geom.L-c.geom.R)*(c.geom.t1-c.geom.t0);
      let rows='',when='';c.lines.forEach(l=>{let best=l.points[0];l.points.forEach(p=>{if(Math.abs(+new Date(p[0])-t)<Math.abs(+new Date(best[0])-t))best=p;});when=new Date(best[0]).toLocaleString('pt-BR');rows+=`<div><span style="color:${l.color}">●</span> ${esc(l.name)}: <b>${c.fmt(best[1])}</b></div>`;});
      tip.innerHTML=`<div class="muted">${when}</div>${rows}`;tip.style.display='block';const px=e.clientX-r.left;tip.style.left=Math.max(0,Math.min(px+12,r.width-tip.offsetWidth-4))+'px';tip.style.top='10px';cur.setAttribute('x1',vx);cur.setAttribute('x2',vx);cur.setAttribute('visibility','visible');};
    el.onmouseleave=()=>{tip.style.display='none';cur.setAttribute('visibility','hidden');};});
}
function pie(title,items,fmt,clickable){
  items=items.filter(i=>i.value>0).sort((a,b)=>b.value-a.value);
  if(items.length>9){const rest=items.slice(8).reduce((a,b)=>a+b.value,0);items=items.slice(0,8).concat([{label:'outras',value:rest}]);}
  items.forEach((it,i)=>it.color=it.color||PALETTE[i%PALETTE.length]);
  fmt=fmt||fmtInt;const total=items.reduce((a,b)=>a+b.value,0);let angle=-Math.PI/2;const r=80,c=90;let paths='';
  items.forEach(it=>{const a=it.value/total*2*Math.PI;const cls=clickable&&it.key?`class="slice" data-sub="${esc(it.key)}"`:'';
    if(a>=2*Math.PI-1e-9){paths+=`<circle ${cls} cx="${c}" cy="${c}" r="${r}" fill="${it.color}"><title>${esc(it.label)}</title></circle>`;return;}
    const x1=c+r*Math.cos(angle),y1=c+r*Math.sin(angle);angle+=a;const x2=c+r*Math.cos(angle),y2=c+r*Math.sin(angle);
    paths+=`<path ${cls} d="M${c},${c} L${x1},${y1} A${r},${r} 0 ${a>Math.PI?1:0} 1 ${x2},${y2} Z" fill="${it.color}" stroke="var(--card)" stroke-width="1.5"><title>${esc(it.label)}: ${fmt(it.value)} (${(it.value/total*100).toFixed(1)}%)</title></path>`;});
  const legend=items.map(i=>`<div ${clickable&&i.key?`class="slice" data-sub="${esc(i.key)}"`:''}><i style="background:${i.color}"></i>${esc(i.label)} — <b>${fmt(i.value)}</b> <span class="muted">(${(i.value/total*100).toFixed(1)}%)</span></div>`).join('');
  return `<div class="card"><h2>${title}</h2><div class="pie"><svg width="180" height="180" viewBox="0 0 180 180">${paths||'<circle cx="90" cy="90" r="80" fill="var(--line)"/>'}</svg><div class="legend">${legend||'<span class="muted">sem dados no período</span>'}</div></div></div>`;
}
const CODE_COLORS={success:'#16a34a',ok:'#16a34a',unavailable:'#f59e0b',deadline_exceeded:'#f97316',cancelled:'#94a3b8',internal:'#dc2626',permission_denied:'#7f1d1d',not_found:'#b91c1c',resource_exhausted:'#be123c',aborted:'#ea580c'};
const codeItems=obj=>Object.entries(obj||{}).map(([k,v])=>({label:k,value:v,color:CODE_COLORS[k.toLowerCase()]}));

async function run(quiet){
  const sub=subs.find(s=>s.name===$('sub').value);
  const start=new Date($('start').value).toISOString(),end=new Date($('end').value).toISOString();
  history.replaceState(null,'','?'+new URLSearchParams({...(sub?{sub:sub.name}:{}),...(rangeMinutes?{minutes:rangeMinutes}:{})}));
  if(!quiet)$('out').innerHTML='<div class="card muted">Lendo as métricas do Cloud Monitoring…</div>';
  try{
    const dbPromise=fetch('/api/db?'+new URLSearchParams({subscription:sub?sub.name:'',start,end})).then(async x=>{const v=await x.json();if(!x.ok)throw new Error(v.error);return v;});
    const r=await fetch('/api/metrics?'+new URLSearchParams({subscription:sub?sub.name:'',topic:sub?sub.topic:'',start,end}));const d=await r.json();if(!r.ok)throw new Error(d.error);
    lastData=d;if(!quiet){lastDb=null;dbError='';}render(d,sub);
    dbPromise.then(v=>{lastDb=v;dbError='';}).catch(e=>{dbError=e.message;}).finally(()=>{if(lastData===d){table(d);$('db').innerHTML=cacheCard()+dbCard();}});
  }catch(e){$('out').innerHTML=`<div class="card err">${esc(e.message)}</div>`;}
}

function render(d,sub){
  const t=d.timeline,g=d.grouped,s=d.totals;
  const published=sum(s.publishedByTopic),delivered=sum(s.deliveredBySubscription),acked=sum(s.ackedBySubscription);
  const backlogNow=last(t.backlog),oldestNow=last(t.oldest);
  const oldestMax=Math.max(0,...Object.values(s.oldestMaxBySubscription||{}));
  const streamsNow=Object.values(g.streamsBySubscription||{}).reduce((a,p)=>a+(last(p)||0),0);
  const pubErrors=Object.entries(s.publishCodes||{}).filter(([k])=>k!=='success').reduce((a,[,v])=>a+v,0);
  const tiles=[['Publicadas',fmtInt(published)],['Entregues',fmtInt(delivered)],['Confirmadas (ack)',fmtInt(acked)],
    ['Pendentes agora',fmtInt(backlogNow),backlogNow>0],['Mais antiga sem ack',fmtAge(oldestNow),oldestNow>600],['Mais antiga (máx)',fmtAge(oldestMax)],
    ['Ack p50',fmtMs(s.ackP50?.total)],['Ack p95',fmtMs(s.ackP95?.total)],['Ack p99',fmtMs(s.ackP99?.total)],
    ['Publicação p50',fmtUs(s.publishP50?.total)],['Publicação p95',fmtUs(s.publishP95?.total)],['Publicação p99',fmtUs(s.publishP99?.total)],
    ['Erros ao publicar',fmtInt(pubErrors),pubErrors>0],['Consumidores conectados',fmtInt(streamsNow),!sub||sub.delivery==='pull'?streamsNow===0:false],
    ['Tamanho p50',fmtBytes(s.sizeP50?.total)],['Tamanho p95',fmtBytes(s.sizeP95?.total)]];
  const per=m=>({acked:[t.acked,'confirmadas','#16a34a'],delivered:[t.delivered,'entregues','#2563eb'],published:[t.published,'publicadas','#7c3aed']}[m]);
  const flow=['published','delivered','acked'].map(k=>({name:per(k)[1],points:t[k],color:per(k)[2]}));
  const topBacklog=Object.entries(g.backlogBySubscription||{}).filter(([,p])=>p.some(x=>x[1]>0)).slice(0,8).map(([k,p],i)=>({name:short(k),points:p,color:PALETTE[i]}));
  const topOldest=Object.entries(g.oldestBySubscription||{}).filter(([,p])=>p.some(x=>x[1]>0)).sort((a,b)=>Math.max(...b[1].map(x=>x[1]))-Math.max(...a[1].map(x=>x[1]))).slice(0,8).map(([k,p],i)=>({name:short(k),points:p,color:PALETTE[i]}));
  const streams=Object.entries(g.streamsByStatus||{}).map(([k,p],i)=>({name:k,points:p,color:k==='ok'?'#16a34a':PALETTE[i+2]}));
  const minutes=d.period/60,unit=minutes>=60?(minutes/60)+' h':minutes+' min';
  const bySubItems=(obj,map)=>Object.entries(obj||{}).map(([k,v])=>({label:short(k),key:map?map(k):k,value:v}));
  const subOfTopic=topic=>(subs.find(x=>x.topic===topic)||{}).name;
  const backlogNowBySub=Object.fromEntries(Object.entries(g.backlogBySubscription||{}).map(([k,p])=>[k,last(p)||0]));
  $('out').innerHTML=
    `<div class="tiles">${tiles.map(([k,v,alert])=>`<div class="tile${alert?' alert':''}"><span>${k}</span><b>${v}</b></div>`).join('')}</div>`+
    `<div class="muted" style="margin:-6px 0 12px">Cada ponto dos gráficos cobre ${unit}; os totais e percentis acima cobrem o período inteiro. O Pub/Sub publica as métricas com 1 a 3 minutos de atraso.</div>`+
    `<div class="grid2">${lineChart('flow','Mensagens por intervalo',flow,fmtInt,'(por '+unit+')')}${lineChart('backlog','Pendentes (não entregues)',sub?[{name:short(sub.name),points:t.backlog,color:'#ea580c'}]:topBacklog.length?topBacklog:[{name:'todas',points:t.backlog,color:'#ea580c'}],fmtInt)}`+
    `${lineChart('oldest','Idade da mais antiga sem ack',sub?[{name:short(sub.name),points:t.oldest,color:'#dc2626'}]:topOldest,fmtAge)}`+
    `${lineChart('ack','Latência de confirmação (ack)',[{name:'p50',points:t.ackP50,color:'#16a34a'},{name:'p95',points:t.ackP95,color:'#f59e0b'},{name:'p99',points:t.ackP99,color:'#dc2626'}],fmtMs)}`+
    `${lineChart('pub','Latência de publicação',[{name:'p50',points:t.publishP50,color:'#16a34a'},{name:'p95',points:t.publishP95,color:'#f59e0b'},{name:'p99',points:t.publishP99,color:'#dc2626'}],fmtUs)}`+
    `${lineChart('streams','Consumidores conectados (streaming pull)',streams,fmtInt)}</div>`+
    `<div class="grid3">${pie('Publicadas por fila',bySubItems(s.publishedByTopic,subOfTopic),fmtInt,true)}${pie('Confirmadas por fila',bySubItems(s.ackedBySubscription),fmtInt,true)}${pie('Pendentes agora, por fila',bySubItems(backlogNowBySub),fmtInt,true)}`+
    `${pie('Respostas ao publicar',codeItems(s.publishCodes))}${pie('Respostas do streaming pull',codeItems(s.pullCodes))}${pie('Prazos de ack estendidos por fila',bySubItems(s.modAckBySubscription),fmtInt,true)}</div>`+
    `<div class="card"><h2>Filas <span class="muted" style="font-weight:normal">(clique numa linha, numa fatia ou na legenda para ver só a fila)</span></h2><div class="scroll" id="tbl"></div></div>`+
    `<div id="db">${cacheCard()}${dbCard()}</div>`;
  wireCharts();table(d);
  document.querySelectorAll('.slice[data-sub]').forEach(el=>el.onclick=()=>{$('sub').value=el.dataset.sub;run();});
}
const COLS=[['name','Fila'],['published','Publicadas',1],['delivered','Entregues',1],['acked','Confirmadas',1],['backlogNow','Pendentes agora',1],['backlogMax','Pendentes máx',1],['oldestMax','Mais antiga máx',1],['ackP95','Ack p95',1],['streams','Conectados',1],['modAck','Prazos estendidos',1],
  ['cacheReads','Cache leituras',1],['cacheHitRate','Cache hits',1],['cacheWrites','Cache escritas',1],['cacheMs','Cache cliente',1],['noDb','Sem ir ao ES',1],
  ['dbMsgs','Msgs com ES',1],['dbPerMsg','ES por msg',1],['dbP50','ES cliente p50',1],['dbP95','ES cliente p95',1],['dbShard','ES shards (soma)',1],['dbShare','% no ES',1],
  ['ackDeadline','Prazo de ack',1],['deadLetter','Mensagens mortas'],['retention','Retenção']];
function dbByTopic(){
  const byTopic={};
  (lastDb?lastDb.messages:[]).filter(m=>m.db.count).forEach(m=>{const t=byTopic[m.topic]=byTopic[m.topic]||{msgs:0,calls:0,client:[],shard:0,shardN:0,duration:0};
    t.msgs++;t.calls+=m.db.count;t.client.push(m.db.clientMs);t.duration+=m.durationMs;if(m.db.shardMs!=null){t.shard+=m.db.shardMs;t.shardN++;}});
  Object.values(byTopic).forEach(t=>{const sorted=t.client.sort((a,b)=>a-b);t.p50=pct(sorted,50);t.p95=pct(sorted,95);t.share=t.duration?Math.min(100,sorted.reduce((a,b)=>a+b,0)/t.duration*100):null;});
  return byTopic;
}
function cacheByTopic(){
  // por fila: mensagens medidas, leituras, hits, misses, escritas, tempo no cliente e as que nao precisaram do ES
  const byTopic={};
  (lastDb?lastDb.messages:[]).filter(m=>m.cache).forEach(m=>{const c=m.cache;
    const t=byTopic[m.topic]=byTopic[m.topic]||{msgs:0,reads:0,hits:0,misses:0,writes:0,ms:0,noDb:0,entities:{}};
    t.msgs++;t.reads+=c.hits+c.misses;t.hits+=c.hits;t.misses+=c.misses;t.writes+=c.writes;t.ms+=c.clientMs;if(!m.db.count)t.noDb++;
    c.byEntity.forEach(e=>{const x=t.entities[e.entity]=t.entities[e.entity]||{hits:0,misses:0};x.hits+=e.hits;x.misses+=e.misses;});});
  return byTopic;
}
function cacheCard(){
  if(dbError||!lastDb)return '';
  const byTopic=cacheByTopic(),topics=Object.entries(byTopic).sort((a,b)=>b[1].reads-a[1].reads);
  const note='<div class="muted" style="margin-bottom:8px"><b>Leituras</b> = consultas ao cache (Memorystore for Valkey) antes de ir ao Elasticsearch; <b>hit</b> = a chave estava lá e o ES não foi chamado; <b>escritas</b> = gravação depois de um miss e apagamento de chaves depois de uma gravação ou antes de uma busca; <b>Sem ir ao ES</b> = mensagens atendidas só pelo cache. Mensagens anteriores à medição do cache (05/11/2026, noite) não entram.</div>';
  if(!topics.length)return `<div class="card"><h2>Cache por fila</h2>${note}<div class="muted">Nenhuma mensagem com a medição do cache no período.</div></div>`;
  const rate=(h,r)=>r?(h/r*100).toFixed(h/r<0.1?1:0)+'%':'–';
  const name=e=>e===''?'(chaves de serviço, sem entidade)':e;
  const entityRows=topics.flatMap(([topic,t])=>Object.entries(t.entities).map(([e,x])=>({topic,entity:e,...x}))).sort((a,b)=>(b.hits+b.misses)-(a.hits+a.misses));
  return `<div class="card"><h2>Cache por fila <span class="muted" style="font-weight:normal">(em ordem de leituras)</span></h2>${note}<div class="scroll"><table><thead><tr><th>Fila</th><th class="num">Mensagens</th><th class="num">Leituras</th><th class="num">Hits</th><th class="num">Misses</th><th class="num">Hits %</th><th class="num">Escritas</th><th class="num">Cache cliente</th><th class="num">Por mensagem</th><th class="num">Sem ir ao ES</th></tr></thead><tbody>`+
    topics.map(([topic,t])=>`<tr><td title="${esc(topic)}">${esc(short(topic))}</td><td class="num">${fmtInt(t.msgs)}</td><td class="num">${fmtInt(t.reads)}</td><td class="num">${fmtInt(t.hits)}</td><td class="num">${fmtInt(t.misses)}</td><td class="num">${rate(t.hits,t.reads)}</td>`+
      `<td class="num">${fmtInt(t.writes)}</td><td class="num">${fmtMs(t.ms)}</td><td class="num">${(t.reads/t.msgs).toFixed(1)}</td><td class="num">${fmtInt(t.noDb)} (${rate(t.noDb,t.msgs)})</td></tr>`).join('')+
    `</tbody></table></div>`+
    (entityRows.length?`<h2 style="margin-top:14px">Leituras do cache por entidade</h2><div class="scroll"><table><thead><tr><th>Fila</th><th>Entidade</th><th class="num">Leituras</th><th class="num">Hits</th><th class="num">Misses</th><th class="num">Hits %</th></tr></thead><tbody>`+
      entityRows.map(r=>`<tr><td title="${esc(r.topic)}">${esc(short(r.topic))}</td><td>${esc(name(r.entity))}</td><td class="num">${fmtInt(r.hits+r.misses)}</td><td class="num">${fmtInt(r.hits)}</td><td class="num">${fmtInt(r.misses)}</td><td class="num">${rate(r.hits,r.hits+r.misses)}</td></tr>`).join('')+
      `</tbody></table></div>`:'')+`</div>`;
}
function dbCard(){
  if(dbError)return `<div class="card err">Chamadas ao Elasticsearch: ${esc(dbError)}</div>`;
  if(!lastDb)return '<div class="card muted">Lendo as chamadas ao Elasticsearch das mensagens (log mensagens e slowlog)…</div>';
  const dbMessages=lastDb.messages.filter(m=>m.db.count);
  const groups={};const manyTopics=new Set(dbMessages.map(m=>m.topic)).size>1;
  dbMessages.forEach(m=>{const seen=new Set();m.db.calls.forEach(c=>{const k=m.topic+'|'+c.signature;
    const g=groups[k]=groups[k]||{topic:m.topic,signature:c.signature,calls:0,msgs:0,client:[],took:0,tookN:0,query:0,fetch:0,write:0,shard:0,shardN:0,source:''};
    g.calls++;if(!seen.has(k)){seen.add(k);g.msgs++;}g.client.push(c.clientMs);if(c.tookMs!=null){g.took+=c.tookMs;g.tookN++;}
    if(c.shardMs!=null){g.shard+=c.shardMs;g.shardN++;g.query+=c.queryMs||0;g.fetch+=c.fetchMs||0;g.write+=c.writeMs||0;}if(!g.source&&c.source)g.source=c.source;});});
  const list=Object.values(groups).map(g=>{const sorted=g.client.sort((a,b)=>a-b);return {...g,clientSum:sorted.reduce((a,b)=>a+b,0),p50:pct(sorted,50),p95:pct(sorted,95)};}).sort((a,b)=>b.clientSum-a.clientSum);
  const slow=lastDb.slowlogLines?`${lastDb.slowlogLines} linhas do slowlog${lastDb.slowlogTruncated?' (cortado no máximo)':''}`:'nenhuma linha do slowlog no período: as colunas de shards ficam vazias enquanto o <code>33-slowlog-de-todas-as-queries.py</code> estiver desligado';
  const note=`<div class="muted" style="margin-bottom:8px">${dbMessages.length} mensagens com chamadas ao ES${lastDb.truncated?' (cortado no máximo: as mais recentes)':''} · ${slow}. <b>Cliente</b> = ida e volta vista pelo consumidor · <b>took</b> = tempo que o ES informa (só busca e bulk) · <b>shards</b> = soma do tempo de cada shard no slowlog, o esforço do ES. Mensagens anteriores a 05/11/2026 não têm a medição.</div>`;
  if(!list.length)return `<div class="card"><h2>Queries por fila</h2>${note}</div>`;
  return `<div class="card"><h2>Queries por fila <span class="muted" style="font-weight:normal">(em ordem do tempo total no cliente)</span></h2>${note}<div class="scroll"><table><thead><tr>${manyTopics?'<th>Fila</th>':''}<th>Chamada ao ES</th><th class="num">Chamadas</th><th class="num">Mensagens</th><th class="num">Por mensagem</th><th class="num">Cliente p50</th><th class="num">Cliente p95</th><th class="num">Cliente total</th><th class="num">Took médio</th><th class="num">Shards total</th><th class="num">Query</th><th class="num">Fetch</th><th class="num">Escrita</th><th>Exemplo de query</th></tr></thead><tbody>`+
    list.map(g=>`<tr>${manyTopics?`<td title="${esc(g.topic)}">${esc(short(g.topic))}</td>`:''}<td class="url">${esc(g.signature)}</td><td class="num">${g.calls}</td><td class="num">${g.msgs}</td><td class="num">${(g.calls/g.msgs).toFixed(1)}</td><td class="num">${fmtMs(g.p50)}</td><td class="num">${fmtMs(g.p95)}</td><td class="num">${fmtMs(g.clientSum)}</td>`+
      `<td class="num">${g.tookN?fmtMs(g.took/g.tookN):'–'}</td><td class="num">${g.shardN?fmtMs(g.shard):'–'}</td><td class="num">${g.shardN?fmtMs(g.query):'–'}</td><td class="num">${g.shardN?fmtMs(g.fetch):'–'}</td><td class="num">${g.shardN&&g.write?fmtMs(g.write):'–'}</td><td class="src" title="${esc(g.source)}">${esc(g.source.slice(0,140))}</td></tr>`).join('')+
    `</tbody></table></div></div>`;
}
function table(d){
  const g=d.grouped,s=d.totals;const db=dbByTopic();const dbOf=x=>db[x.name]||db[x.topic]||null;
  const cache=cacheByTopic();const cacheOf=x=>cache[x.name]||cache[x.topic]||null;
  const rows=subs.filter(x=>!$('sub').value||x.name===$('sub').value).map(x=>({name:x.name,published:(s.publishedByTopic||{})[x.topic]||0,delivered:(s.deliveredBySubscription||{})[x.name]||0,acked:(s.ackedBySubscription||{})[x.name]||0,
    backlogNow:last((g.backlogBySubscription||{})[x.name])||0,backlogMax:(s.backlogMaxBySubscription||{})[x.name]||0,oldestMax:(s.oldestMaxBySubscription||{})[x.name]||0,
    ackP95:(s.ackP95BySubscription||{})[x.name],streams:last((g.streamsBySubscription||{})[x.name])||0,modAck:(s.modAckBySubscription||{})[x.name]||0,
    ackDeadline:x.ackDeadline,deadLetter:x.deadLetter?short(x.deadLetter)+' ('+x.maxAttempts+'x)':'',retention:x.retention,delivery:x.delivery,
    cacheReads:cacheOf(x)?cacheOf(x).reads:null,cacheHitRate:cacheOf(x)&&cacheOf(x).reads?cacheOf(x).hits/cacheOf(x).reads*100:null,
    cacheWrites:cacheOf(x)?cacheOf(x).writes:null,cacheMs:cacheOf(x)?cacheOf(x).ms:null,noDb:cacheOf(x)?cacheOf(x).noDb:null,
    dbMsgs:dbOf(x)?dbOf(x).msgs:null,dbPerMsg:dbOf(x)?dbOf(x).calls/dbOf(x).msgs:null,dbP50:dbOf(x)?dbOf(x).p50:null,dbP95:dbOf(x)?dbOf(x).p95:null,
    dbShard:dbOf(x)&&dbOf(x).shardN?dbOf(x).shard:null,dbShare:dbOf(x)?dbOf(x).share:null}));
  const [key,dir]=tableSort;rows.sort((a,b)=>((a[key]??-1)>(b[key]??-1)?1:(a[key]??-1)<(b[key]??-1)?-1:0)*dir);
  $('tbl').innerHTML=`<table><thead><tr>${COLS.map(([k,t,n])=>`<th data-k="${k}" class="${n?'num':''}">${t}${k===key?(dir>0?' ▲':' ▼'):''}</th>`).join('')}</tr></thead><tbody>`+
    rows.map(r=>`<tr class="pick" data-sub="${esc(r.name)}" title="${esc(r.name)}"><td>${esc(short(r.name))}</td><td class="num">${fmtInt(r.published)}</td><td class="num">${fmtInt(r.delivered)}</td><td class="num">${fmtInt(r.acked)}</td>`+
      `<td class="num ${r.backlogNow>0?'bad':''}">${fmtInt(r.backlogNow)}</td><td class="num">${fmtInt(r.backlogMax)}</td><td class="num ${r.oldestMax>600?'bad':''}">${r.oldestMax?fmtAge(r.oldestMax):'–'}</td><td class="num">${r.ackP95==null?'–':fmtMs(r.ackP95)}</td>`+
      `<td class="num ${r.delivery==='pull'&&!r.streams?'bad':'ok'}">${r.delivery==='push'?'push':fmtInt(r.streams)}</td><td class="num">${fmtInt(r.modAck)}</td>`+
      `<td class="num">${r.cacheReads==null?(lastDb?'–':'…'):fmtInt(r.cacheReads)}</td><td class="num">${r.cacheHitRate==null?'–':r.cacheHitRate.toFixed(r.cacheHitRate<10?1:0)+'%'}</td><td class="num">${r.cacheWrites==null?'–':fmtInt(r.cacheWrites)}</td><td class="num">${dashMs(r.cacheMs)}</td><td class="num">${r.noDb==null?'–':fmtInt(r.noDb)}</td>`+
      `<td class="num">${r.dbMsgs==null?(lastDb?'0':'…'):fmtInt(r.dbMsgs)}</td><td class="num">${r.dbPerMsg==null?'–':r.dbPerMsg.toFixed(1)}</td><td class="num">${dashMs(r.dbP50)}</td><td class="num">${dashMs(r.dbP95)}</td><td class="num">${dashMs(r.dbShard)}</td><td class="num">${r.dbShare==null?'–':r.dbShare.toFixed(r.dbShare<10?1:0)+'%'}</td>`+
      `<td class="num">${r.ackDeadline} s</td><td>${esc(r.deadLetter||'–')}</td><td>${esc(fmtAge(parseInt(r.retention)))}</td></tr>`).join('')+`</tbody></table>`;
  document.querySelectorAll('#tbl th').forEach(th=>th.onclick=()=>{const k=th.dataset.k;tableSort=[k,k===tableSort[0]?-tableSort[1]:-1];table(lastData);});
  document.querySelectorAll('#tbl tr.pick').forEach(tr=>tr.onclick=()=>{$('sub').value=tr.dataset.sub;run();});
}
</script></body></html>
"""

if __name__ == "__main__":
    address = "http://127.0.0.1:%d/" % PORT
    # no Windows o SO_REUSEADDR (ligado por padrao no HTTPServer) deixa dois processos ouvirem a mesma porta
    ThreadingHTTPServer.allow_reuse_address = False
    try:
        server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError:
        # o painel ja esta no ar (atalho clicado de novo): so abre a pagina
        webbrowser.open(address)
        sys.exit(0)
    if sys.stdout:
        print("Painel em %s (Ctrl+C para parar)" % address)
    threading.Timer(1.0, webbrowser.open, [address]).start()
    server.serve_forever()
