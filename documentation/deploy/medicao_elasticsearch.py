# Medicao das chamadas ao Elasticsearch, comum aos paineis 27 (requisicoes do Cloud Run) e 29 (filas do Pub/Sub).
# Cada unidade de trabalho (requisicao de API ou mensagem de fila) traz, no seu log, o traceId e as chamadas que fez ao
# Elasticsearch (CcpDbCallsOfTheThread, gravadas pelo ElasticSearchDbRequester): sequencia, metodo, caminho, status,
# latencia vista pelo cliente (clientMs) e o took da resposta (so busca e bulk informam). Por dentro do Elasticsearch, o
# slowlog (log elasticsearch_slowlog, so com o 33-slowlog-de-todas-as-queries.py ligado) da o tempo de cada shard:
#   - busca: uma linha por shard e fase (query, fetch), com elasticsearch.slowlog.id = <traceId>-<sequencia> (o
#     X-Opaque-Id da chamada), entao cada linha cai na chamada exata;
#   - escrita: uma linha por documento e shard, so com trace.id (o id do slowlog de escrita e o id do documento): cai na
#     primeira chamada de escrita da unidade naquele indice, ou no primeiro _bulk da unidade.
# A soma do tempo dos shards e o esforco do Elasticsearch: os shards rodam em paralelo, entao ela pode passar do took.
# Get por id e mget nao passam pelo slowlog: deles so ha a latencia do cliente.
import json
import re
import time
import urllib.error
import urllib.request

UNITS_IN_MS = {"nanos": 1e-6, "micros": 1e-3, "ms": 1.0, "s": 1000.0, "m": 60000.0, "h": 3600000.0}
READS = ("_search", "_mget", "_count", "_msearch", "_source", "_doc")
ID_SEGMENTS = ("_doc", "_source", "_create", "_update")


def list_entries(access_token, forget_token, project, filters, maximum):
    # mesma leitura dos paineis: pagina de 1000, 429 espera e tenta de novo, 401 pede outro token uma vez
    body = {"resourceNames": ["projects/" + project], "filter": " AND ".join(filters), "orderBy": "timestamp desc",
            "pageSize": min(1000, maximum)}
    entries = []
    truncated = False
    while True:
        page = _page(body, access_token, forget_token)
        entries.extend(page.get("entries", []))
        next_page = page.get("nextPageToken")
        if not next_page:
            break
        if len(entries) >= maximum:
            truncated = True
            break
        body["pageToken"] = next_page
    return entries[:maximum], truncated


def _page(body, access_token, forget_token):
    data = json.dumps(body).encode()
    renewed = False
    for wait in (5, 15, 30, 0):
        request = urllib.request.Request("https://logging.googleapis.com/v2/entries:list", data=data, method="POST")
        request.add_header("Authorization", "Bearer " + access_token())
        request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code == 401 and not renewed:
                renewed = True
                forget_token()
                continue
            if error.code != 429 or not wait:
                raise
            time.sleep(wait)


def took_ms(text):
    match = re.fullmatch(r"([\d.]+)\s*([a-z]+)", str(text or "").strip())
    if not match or match.group(2) not in UNITS_IN_MS:
        return None
    return float(match.group(1)) * UNITS_IN_MS[match.group(2)]


def signature(method, path):
    # o mesmo tipo de chamada em requisicoes diferentes: ids (depois de _doc, _source etc. ou hashes) viram {id}
    parts = path.split("?", 1)[0].split("/")
    normalized = []
    previous = ""
    for part in parts:
        is_id = previous in ID_SEGMENTS or re.fullmatch(r"[0-9a-f]{24,}", part)
        normalized.append("{id}" if is_id else part)
        previous = part
    return "%s %s" % (method, "/".join(normalized))


# o nome da API do Elasticsearch, como a documentacao chama, pelo endpoint do caminho (o primeiro que aparecer)
API_BY_ENDPOINT = (
    ("/_msearch", "Multi search API"), ("/_search", "Search API"), ("/_count", "Count API"), ("/_mget", "Multi get API"),
    ("/_bulk", "Bulk API"), ("/_delete_by_query", "Delete by query API"), ("/_update_by_query", "Update by query API"),
    ("/_update/", "Update API"), ("/_create/", "Create API"), ("/_source/", "Get source API"), ("/_refresh", "Refresh API"),
    ("/_snapshot", "Snapshot API"), ("/_cat/", "cat API"), ("/_settings", "Index settings API"), ("/_mapping", "Mapping API"),
    ("/_cluster/health", "Cluster health API"),
)
DOCUMENT_API_BY_METHOD = {"GET": "Get API", "HEAD": "Exists API", "DELETE": "Delete API", "PUT": "Index API", "POST": "Index API"}
INDEX_API_BY_METHOD = {"PUT": "Create index API", "DELETE": "Delete index API", "HEAD": "Index exists API", "GET": "Get index API"}


def api_name(method, path):
    route = path.split("?", 1)[0]
    for endpoint, name in API_BY_ENDPOINT:
        if endpoint in route:
            return name
    if "/_doc" in route:
        return DOCUMENT_API_BY_METHOD.get(method, "Document API")
    only_index = re.fullmatch(r"/[^/_][^/]*/?", route)
    if only_index:
        return INDEX_API_BY_METHOD.get(method, "Index API")
    return "%s %s" % (method, route)


def read_slowlog(access_token, forget_token, project, start, end, trace_ids, maximum=50000):
    empty = {"calls": {}, "writes": {}, "lines": 0, "truncated": False}
    ids = sorted({trace for trace in trace_ids if trace})
    if not ids:
        return empty
    filters = ['logName="projects/%s/logs/elasticsearch_slowlog"' % project, 'timestamp>="%s"' % start, 'timestamp<"%s"' % end]
    # poucos traces: o filtro vai ate o Cloud Logging; muitos: le a janela toda e descarta aqui
    if len(ids) <= 150:
        filters.append('jsonPayload."trace.id"=(%s)' % " OR ".join('"%s"' % trace for trace in ids))
    entries, truncated = list_entries(access_token, forget_token, project, filters, maximum)
    wanted = set(ids)
    calls = {}
    writes = {}
    for entry in entries:
        payload = entry.get("jsonPayload", {})
        trace = payload.get("trace.id", "")
        if trace not in wanted:
            continue
        ms = took_ms(payload.get("elasticsearch.slowlog.took"))
        if ms is None:
            continue
        logger = payload.get("log.logger", "")
        message = payload.get("elasticsearch.slowlog.message", "")
        index_match = re.match(r"\[([^\]/]+)", message)
        index = index_match.group(1) if index_match else ""
        if logger.startswith("index.indexing"):
            write = writes.setdefault(trace, {}).setdefault(index, {"ms": 0.0, "docs": 0})
            write["ms"] += ms
            write["docs"] += 1
            continue
        call = calls.setdefault(payload.get("elasticsearch.slowlog.id", ""),
                                {"queryMs": 0.0, "fetchMs": 0.0, "shards": set(), "hits": None, "source": ""})
        call["shards"].add(message)
        if logger.endswith(".fetch"):
            call["fetchMs"] += ms
            continue
        call["queryMs"] += ms
        hits = re.match(r"(\d+)", str(payload.get("elasticsearch.slowlog.total_hits", "")))
        call["hits"] = int(hits.group(1)) if hits else call["hits"]
        call["source"] = str(payload.get("elasticsearch.slowlog.source", "")).replace('\\"', '"')
    for call in calls.values():
        call["shards"] = len(call["shards"])
    return {"calls": calls, "writes": writes, "lines": len(entries), "truncated": truncated}


def is_write(call):
    return call["method"] in ("PUT", "POST", "DELETE") and not any(read in call["path"] for read in READS[:4])


def enrich(unit, slowlog):
    # as chamadas da unidade com o tempo por dentro do Elasticsearch; devolve o resumo usado nas colunas
    trace = unit.get("traceId", "")
    calls = []
    for raw in unit.get("dbCalls", []):
        sequence = int(float(raw.get("sequence", 0)))
        call = {
            "sequence": sequence, "method": raw.get("method", ""), "path": raw.get("path", ""),
            "status": int(float(raw.get("status", 0))), "clientMs": float(raw.get("clientMs", 0)),
            "tookMs": float(raw["tookMs"]) if "tookMs" in raw else None,
            "requestBytes": int(float(raw.get("requestBytes", 0))), "responseBytes": int(float(raw.get("responseBytes", 0))),
            "queryMs": None, "fetchMs": None, "writeMs": None, "writeDocs": 0, "shards": None, "hits": None, "source": "",
        }
        call["signature"] = signature(call["method"], call["path"])
        call["api"] = api_name(call["method"], call["path"])
        inside = slowlog["calls"].get("%s-%d" % (trace, sequence))
        if inside:
            call.update({"queryMs": inside["queryMs"], "fetchMs": inside["fetchMs"], "shards": inside["shards"],
                         "hits": inside["hits"], "source": inside["source"]})
        calls.append(call)
    unattributed = 0.0
    for index, write in slowlog["writes"].get(trace, {}).items():
        target = next((call for call in calls if is_write(call) and (call["path"] + "/").startswith("/%s/" % index)), None)
        target = target or next((call for call in calls if call["path"].startswith("/_bulk")), None)
        if not target:
            unattributed += write["ms"]
            continue
        target["writeMs"] = (target["writeMs"] or 0.0) + write["ms"]
        target["writeDocs"] += write["docs"]
    for call in calls:
        parts = [call[key] for key in ("queryMs", "fetchMs", "writeMs") if call[key] is not None]
        call["shardMs"] = sum(parts) if parts else None
    shard_parts = [call["shardMs"] for call in calls if call["shardMs"] is not None]
    took_parts = [call["tookMs"] for call in calls if call["tookMs"] is not None]
    return {
        "traceId": trace,
        "count": len(calls),
        "clientMs": round(sum(call["clientMs"] for call in calls), 1),
        "tookMs": sum(took_parts) if took_parts else None,
        "shardMs": round(sum(shard_parts) + unattributed, 3) if shard_parts or unattributed else None,
        "unattributedWriteMs": unattributed,
        "calls": calls,
    }
