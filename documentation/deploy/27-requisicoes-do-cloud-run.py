# Painel local das requisicoes de uma URL de um servico do Cloud Run (jobsnow-prd): escolhe a API (jobsnow-vis ou
# jobsnow-js; o front fica de fora), o endpoint e o periodo; lista as requisicoes e mostra pizza por status HTTP,
# pizza por faixa de latencia e os percentis p50, p75, p90, p95, p99 e p99.9.
# Os endpoints saem dos controllers do modulo da API (servico jobsnow-X -> X_rest-api_*/.../rest/api/endpoints), lidos
# a cada abertura da lista. Uma requisicao conta para o endpoint que o Spring escolheria: entre as rotas do mesmo
# metodo que casam com o caminho, a de menos {variaveis} (GET /login/{email}/erro nao entra em /login/{email}/{sessionToken}).
# Le os logs de requisicao do Cloud Run (run.googleapis.com/requests) pela API do Cloud Logging, com o token do
# gcloud do usuario (nao usa GOOGLE_APPLICATION_CREDENTIALS, que aponta para o jn-hmg). Os logs ficam 30 dias.
# Desde 2026-11-05 cada requisicao traz tambem as suas chamadas ao Elasticsearch: a linha jobsnowDbCalls que a API
# escreve no stdout (CcpDbCallsLogFilter, ligada pelo trace da requisicao) e, com o 33-slowlog-de-todas-as-queries.py
# ligado, o tempo de cada shard por dentro do Elasticsearch (medicao_elasticsearch.py). Requisicoes de revisoes
# anteriores a essa data, ou que nao tocaram o banco, ficam com as colunas do ES vazias.
# Uso: python 27-requisicoes-do-cloud-run.py [porta]   (abre http://127.0.0.1:8765 no navegador)
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import medicao_elasticsearch  # noqa: E402

PROJECT = "jobsnow-prd"
WORKSPACE = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
IGNORED_SERVICES = {"jobsnow-front"}
CLASS_MAPPING = re.compile(r'^@RequestMapping\(\s*(?:(?:value|path)\s*=\s*)?"([^"]*)"', re.M)
METHOD_MAPPING = re.compile(r'^\s+@(Get|Post|Put|Patch|Delete|Request)Mapping(?:\((.*)\))?\s*$', re.M)
MAPPING_PATH = re.compile(r'(?:^|(?:value|path)\s*=\s*)"([^"]*)"')
MAPPING_METHOD = re.compile(r'RequestMethod\.(\w+)')
GCLOUD = os.path.join(os.environ["LOCALAPPDATA"], "Google", "Cloud SDK", "google-cloud-sdk", "bin", "gcloud.cmd")
LOG_NAME = "projects/%s/logs/run.googleapis.com%%2Frequests" % PROJECT
STDOUT_LOG_NAME = "projects/%s/logs/run.googleapis.com%%2Fstdout" % PROJECT
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
PAGE_SIZE = 1000
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


def forget_token():
    with token_lock:
        token_cache["expires"] = 0.0


def later(moment, minutes):
    # a linha das chamadas sai no fim da requisicao, depois do log dela: a janela de leitura vai um pouco alem
    parsed = datetime.fromisoformat(moment.replace("Z", "+00:00")) + timedelta(minutes=minutes)
    return parsed.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def read_db_units(service, start, end, traces, maximum):
    filters = [
        'logName="%s"' % STDOUT_LOG_NAME,
        'resource.type="cloud_run_revision"',
        'jsonPayload.kind="jobsnowDbCalls"',
        'timestamp>="%s"' % start,
        'timestamp<"%s"' % later(end, 10),
    ]
    if service:
        filters.append('resource.labels.service_name="%s"' % service)
    entries, _ = medicao_elasticsearch.list_entries(access_token, forget_token, PROJECT, filters, maximum)
    units = {}
    for entry in entries:
        payload = entry.get("jsonPayload", {})
        if payload.get("traceId") in traces:
            units[payload["traceId"]] = payload
    return units


def attach_db_calls(requests, service, start, end):
    trace_of = lambda request: request["trace"].rsplit("/", 1)[-1]
    traces = {trace_of(request) for request in requests if request["trace"]}
    units = read_db_units(service, start, end, traces, max(1000, len(traces) * 2)) if traces else {}
    slowlog = medicao_elasticsearch.read_slowlog(access_token, forget_token, PROJECT, start, later(end, 10), units.keys())
    for request in requests:
        unit = units.get(trace_of(request)) if request["trace"] else None
        request["db"] = medicao_elasticsearch.enrich(unit, slowlog) if unit else None
        request["cache"] = cache_of(unit) if unit else None
    return {"dbLines": len(units), "slowlogLines": slowlog["lines"], "slowlogTruncated": slowlog["truncated"]}


def cache_of(unit):
    # os comandos ao Memorystore da requisicao (CcpDbCallsOfTheThread desde 2026-11-05); nada nas linhas mais antigas
    if "cacheCallsCount" not in unit:
        return None
    by_entity = [{"entity": name, "hits": int(counters.get("hits", 0)), "misses": int(counters.get("misses", 0))}
                 for name, counters in (unit.get("cacheByEntity") or {}).items()]
    by_entity.sort(key=lambda item: -(item["hits"] + item["misses"]))
    return {"hits": int(unit.get("cacheHits", 0)), "misses": int(unit.get("cacheMisses", 0)), "writes": int(unit.get("cacheWrites", 0)),
            "clientMs": float(unit.get("cacheClientMs", 0)), "byEntity": by_entity}


def join_paths(prefix, suffix):
    path = "/" + "/".join(part.strip("/") for part in (prefix, suffix) if part.strip("/"))
    return path


def service_routes(service):
    module_prefix = service.replace("jobsnow-", "") + "_rest-api"
    routes = set()
    for module in os.listdir(WORKSPACE):
        if not module.startswith(module_prefix):
            continue
        for folder, _, files in os.walk(os.path.join(WORKSPACE, module, "src", "main", "java")):
            if not folder.replace("\\", "/").endswith("rest/api/endpoints"):
                continue
            for name in files:
                with open(os.path.join(folder, name), encoding="utf-8") as source:
                    text = source.read()
                class_mapping = CLASS_MAPPING.search(text)
                prefix = class_mapping.group(1) if class_mapping else ""
                for kind, arguments in METHOD_MAPPING.findall(text):
                    path_match = MAPPING_PATH.search(arguments or "")
                    method_match = MAPPING_METHOD.search(arguments or "")
                    method = method_match.group(1) if kind == "Request" and method_match else kind.upper()
                    if kind == "Request" and not method_match:
                        continue
                    routes.add((method, join_paths(prefix, path_match.group(1) if path_match else "")))
    return sorted(routes, key=lambda route: (route[1], route[0]))


def literal(text):
    # sem barra invertida: o filtro do Cloud Logging nao desfaz o \ e procuraria uma barra de verdade na URL
    return "".join(char if char.isalnum() or char in "/-_~" else "[%s]" % char for char in text)


def path_regex(path):
    parts = re.split(r"\{[^}/]*\}", path)
    return "[^/?]+".join(literal(part) for part in parts) + "/?([?].*)?$"


def url_regex(path):
    return r"^https?://[^/]+" + path_regex(path)


def variables(path):
    return path.count("{")


def compiled_routes(service):
    return [(method, path, re.compile(url_regex(path)), variables(path)) for method, path in service_routes(service)]


def endpoint_of(url, method, routes):
    # o endpoint que o Spring escolheria: entre as rotas do metodo que casam com a URL, a de menos {variaveis}
    candidates = [(count, path) for route_method, path, regex, count in routes if route_method == method and regex.search(url)]
    return method + " " + min(candidates)[1] if candidates else ""


def latency_ms(text):
    if not text:
        return None
    return float(text.rstrip("s")) * 1000


def status_filter(statuses):
    conditions = []
    for token in statuses.split(","):
        token = token.strip().lower()
        if re.fullmatch(r"[1-5]xx", token):
            first = int(token[0]) * 100
            conditions.append("(httpRequest.status>=%d AND httpRequest.status<%d)" % (first, first + 100))
            continue
        if re.fullmatch(r"\d{3}", token):
            conditions.append("httpRequest.status=%s" % token)
    return "(" + " OR ".join(conditions) + ")" if conditions else ""


def list_page(body):
    # cota de leitura do Cloud Logging por minuto: no 429 espera e tenta de novo
    data = json.dumps(body).encode()
    # token revogado antes dos 45 min (novo login do gcloud): descarta, pede outro e tenta de novo
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
                with token_lock:
                    token_cache["expires"] = 0.0
                continue
            if error.code != 429 or not wait:
                raise
            time.sleep(wait)


def read_requests(service, method, path, statuses, start, end, maximum):
    filters = [
        'logName="%s"' % LOG_NAME,
        'resource.type="cloud_run_revision"',
        'timestamp>="%s"' % start,
        'timestamp<"%s"' % end,
    ]
    if service:
        filters.append('resource.labels.service_name="%s"' % service)
    for ignored in sorted(IGNORED_SERVICES) if not service else []:
        filters.append('resource.labels.service_name!="%s"' % ignored)
    if method:
        filters.append('httpRequest.requestMethod="%s"' % method)
    status_condition = status_filter(statuses)
    if status_condition:
        filters.append(status_condition)
    if path:
        regex = url_regex(path).replace("\\", "\\\\").replace('"', '\\"')
        filters.append('httpRequest.requestUrl=~"%s"' % regex)
    body = {"resourceNames": ["projects/" + PROJECT], "filter": " AND ".join(filters), "orderBy": "timestamp desc", "pageSize": min(PAGE_SIZE, maximum)}
    requests = []
    truncated = False
    while True:
        page = list_page(body)
        for entry in page.get("entries", []):
            http = entry.get("httpRequest", {})
            labels = entry.get("resource", {}).get("labels", {})
            requests.append({
                "timestamp": entry.get("timestamp", ""),
                "service": labels.get("service_name", ""),
                "revision": labels.get("revision_name", ""),
                "method": http.get("requestMethod", ""),
                "url": http.get("requestUrl", ""),
                "status": http.get("status", 0),
                "latencyMs": latency_ms(http.get("latency")),
                "responseSize": int(http.get("responseSize", 0) or 0),
                "remoteIp": http.get("remoteIp", ""),
                "userAgent": http.get("userAgent", ""),
                "trace": entry.get("trace", ""),
            })
        next_page = page.get("nextPageToken")
        if not next_page:
            break
        if len(requests) >= maximum:
            truncated = True
            break
        body["pageToken"] = next_page
    requests = requests[:maximum]
    routes_by_service = {}
    for request in requests:
        if request["service"] not in routes_by_service:
            routes_by_service[request["service"]] = compiled_routes(request["service"])
        request["route"] = endpoint_of(request["url"], request["method"], routes_by_service[request["service"]])
    discarded = 0
    if method and path:
        kept = [request for request in requests if request["route"] == method + " " + path]
        discarded = len(requests) - len(kept)
        requests = kept
    db = attach_db_calls(requests, service, start, end)
    return {"filter": body["filter"], "truncated": truncated, "discarded": discarded, "requests": requests, **db}


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
                return self.send(200, "text/html; charset=utf-8", PAGE)
            if parsed.path == "/api/services":
                names = gcloud("run", "services", "list", "--project", PROJECT, "--format=value(metadata.name)")
                return self.send_json(200, sorted(set(names.split()) - IGNORED_SERVICES))
            if parsed.path == "/api/routes":
                routes = service_routes(query.get("service", ""))
                return self.send_json(200, [{"method": method, "path": path} for method, path in routes])
            if parsed.path == "/api/requests":
                maximum = int(query.get("max", "20000"))
                result = read_requests(query.get("service", ""), query.get("method", ""), query.get("path", ""),
                                       query.get("status", ""), query["start"], query["end"], maximum)
                return self.send_json(200, result)
            return self.send_json(404, {"error": "not found"})
        except urllib.error.HTTPError as error:
            return self.send_json(502, {"error": error.read().decode(errors="replace")})
        except Exception as error:
            return self.send_json(500, {"error": str(error)})

    def log_message(self, format, *args):
        if sys.stderr:
            sys.stderr.write("%s %s\n" % (self.log_date_time_string(), format % args))


PAGE = r"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Requisições do Cloud Run</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--fg:#1d2330;--muted:#667085;--line:#e3e6eb;--accent:#2563eb}
@media (prefers-color-scheme:dark){:root{--bg:#12151b;--card:#1b1f27;--fg:#e6e8ec;--muted:#98a2b3;--line:#2c323d;--accent:#5b8def}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,Segoe UI,sans-serif}
header{padding:16px 20px;border-bottom:1px solid var(--line);background:var(--card)}h1{margin:0;font-size:18px}
main{padding:16px 20px;max-width:1400px;margin:0 auto}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px;margin-bottom:14px}
form{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;align-items:end}
label{display:flex;flex-direction:column;gap:4px;font-size:12px;color:var(--muted)}
input,select,button{font:inherit;padding:7px 9px;border:1px solid var(--line);border-radius:7px;background:var(--bg);color:var(--fg)}
button{background:var(--accent);color:#fff;border:0;cursor:pointer}button.ghost{background:transparent;color:var(--accent);border:1px solid var(--line)}
.presets{display:flex;gap:6px;flex-wrap:wrap;grid-column:1/-1}.presets button{padding:4px 10px}
.statuses{display:flex;gap:8px;flex-wrap:wrap;grid-column:1/-1;align-items:center}
.chip{flex-direction:row;align-items:center;gap:5px;font-size:13px;font-weight:600;padding:4px 10px;border:1px solid var(--line);border-radius:7px;cursor:pointer}
.chip input{margin:0}.statuses #codes{padding:4px 8px}.slice{cursor:pointer}div.slice:hover{text-decoration:underline}
.wider{grid-column:span 3}@media (max-width:700px){.wider{grid-column:1/-1}}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:10px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px}
.tile b{display:block;font-size:20px}.tile span{font-size:12px;color:var(--muted)}
.pies{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:14px}
.pie{display:flex;gap:16px;align-items:center;flex-wrap:wrap}.pie svg{flex:none}
.legend{display:flex;flex-direction:column;gap:3px;font-size:13px}.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px}
h2{font-size:15px;margin:0 0 10px}
table{width:100%;border-collapse:collapse;font-size:12.5px}th,td{padding:5px 7px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}
td.url{white-space:normal;word-break:break-all}th{cursor:pointer;color:var(--muted);position:sticky;top:0;background:var(--card)}
.scroll{max-height:560px;overflow:auto}.muted{color:var(--muted)}.err{color:#d92d20;white-space:pre-wrap}
tr.pick{cursor:pointer}tr.pick:hover td{background:var(--bg)}tr.detail>td{background:var(--bg);padding:8px 10px}
table.calls{font-size:12px}table.calls th{position:static;cursor:default}td.num,th.num{text-align:right}
.colpick{display:none;flex-wrap:wrap;gap:6px 14px;padding:8px 0 10px;border-bottom:1px solid var(--line);margin-bottom:6px}.colpick.open{display:flex}
.colpick label{flex-direction:row;align-items:center;gap:5px;font-size:13px;color:var(--fg);cursor:pointer}.colpick input{margin:0}
td.src{white-space:normal;word-break:break-all;max-width:420px;color:var(--muted);font-family:ui-monospace,Consolas,monospace;font-size:11px}
.s2{color:#16a34a}.s3{color:#0891b2}.s4{color:#d97706}.s5{color:#dc2626}
code{font-size:11.5px;color:var(--muted);word-break:break-all}
</style></head><body>
<header><h1>Requisições do Cloud Run · jobsnow-prd</h1></header>
<main>
<div class="card"><form id="f">
<label>Serviço<select id="service"></select></label>
<label class="wider">URL (endpoint)<select id="route"><option value="">(todos os endpoints)</option></select></label>
<label>De<input type="datetime-local" id="start"></label>
<label>Até<input type="datetime-local" id="end"></label>
<label>Máximo de requisições<input type="number" id="max" value="20000" min="100" step="1000"></label>
<button type="submit">Buscar</button>
<div class="presets"><span class="muted">Período:</span></div>
<div class="statuses"><span class="muted">Status HTTP:</span>
<label class="chip s2"><input type="checkbox" value="2xx">2xx</label><label class="chip s3"><input type="checkbox" value="3xx">3xx</label>
<label class="chip s4"><input type="checkbox" value="4xx">4xx</label><label class="chip s5"><input type="checkbox" value="5xx">5xx</label>
<input id="codes" placeholder="ou códigos: 404, 503" size="22"><span class="muted">nada marcado = todos · clique numa fatia ou na legenda da pizza de status para filtrar só aquele código</span></div>
</form></div>
<div id="out"></div>
</main>
<script>
const $=id=>document.getElementById(id);
const pad=n=>String(n).padStart(2,'0');
const toLocal=d=>`${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
const presets=[['15 min',15],['1 h',60],['6 h',360],['24 h',1440],['7 dias',10080],['30 dias',43200]];
function setRange(minutes){const end=new Date();$('end').value=toLocal(end);$('start').value=toLocal(new Date(end-minutes*60000));}
presets.forEach(([t,m])=>{const b=document.createElement('button');b.type='button';b.className='ghost';b.textContent=t;b.onclick=()=>{setRange(m);run();};document.querySelector('.presets').appendChild(b);});
setRange(1440);
const params=new URLSearchParams(location.search);
function option(select,value,text){const o=document.createElement('option');o.value=value;o.textContent=text;select.appendChild(o);}
async function loadRoutes(wanted){
  const select=$('route');select.innerHTML='';option(select,'','(todos os endpoints)');
  const routes=await (await fetch('/api/routes?service='+encodeURIComponent($('service').value))).json();
  routes.forEach(r=>option(select,r.method+' '+r.path,r.path+'  ·  '+r.method));
  if(wanted&&[...select.options].some(o=>o.value===wanted))select.value=wanted;
}
fetch('/api/services').then(r=>r.json()).then(list=>{list.forEach(s=>option($('service'),s,s));
  if(params.get('service'))$('service').value=params.get('service');loadRoutes(params.get('route'));});
$('service').onchange=()=>loadRoutes('');
const statusBoxes=[...document.querySelectorAll('.statuses input[type=checkbox]')];
function statusValue(){return [...statusBoxes.filter(b=>b.checked).map(b=>b.value),...$('codes').value.split(/[\s,;]+/).filter(c=>/^\d{3}$/.test(c))].join(',');}
function setStatus(value){const tokens=value?value.split(','):[];statusBoxes.forEach(b=>b.checked=tokens.includes(b.value));$('codes').value=tokens.filter(t=>/^\d{3}$/.test(t)).join(', ');}
setStatus(params.get('status')||'');
statusBoxes.forEach(b=>b.onchange=()=>run());
$('codes').onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();run();}};
$('f').onsubmit=e=>{e.preventDefault();run();};

const BUCKETS=[[50,'< 50 ms'],[100,'50–100 ms'],[250,'100–250 ms'],[500,'250–500 ms'],[1000,'500 ms–1 s'],[2500,'1–2,5 s'],[5000,'2,5–5 s'],[10000,'5–10 s'],[Infinity,'≥ 10 s']];
const BUCKET_COLORS=['#16a34a','#4ade80','#a3e635','#facc15','#fb923c','#f97316','#ef4444','#b91c1c','#7f1d1d'];
const CLASS_SHADES={2:['#16a34a','#22c55e','#4ade80','#86efac'],3:['#0891b2','#22d3ee','#67e8f9'],4:['#d97706','#f59e0b','#fbbf24','#fcd34d','#b45309','#92400e'],5:['#dc2626','#ef4444','#f87171','#991b1b','#7f1d1d'],0:['#94a3b8']};
let rows=[],sortKey='timestamp',sortDir=-1;

function pct(sorted,p){if(!sorted.length)return NaN;const i=(sorted.length-1)*p/100,lo=Math.floor(i),hi=Math.ceil(i);return sorted[lo]+(sorted[hi]-sorted[lo])*(i-lo);}
const fmtMs=v=>v==null||isNaN(v)?'–':v>=1000?(v/1000).toFixed(2)+' s':v.toFixed(v<1?2:v<10?1:0)+' ms';
const dash=v=>v==null?'–':fmtMs(v);
const fmtPct=v=>v==null||isNaN(v)?'–':v.toFixed(v<10?1:0)+'%';
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

function pie(title,items,filterable){
  const total=items.reduce((a,b)=>a+b.value,0);let angle=-Math.PI/2;const r=80,c=90;let paths='';
  items.forEach(it=>{if(!it.value)return;const a=it.value/total*2*Math.PI;
    if(a>=2*Math.PI-1e-9){paths+=`<circle cx="${c}" cy="${c}" r="${r}" fill="${it.color}"><title>${esc(it.label)}: ${it.value}</title></circle>`;angle+=a;return;}
    const x1=c+r*Math.cos(angle),y1=c+r*Math.sin(angle);angle+=a;const x2=c+r*Math.cos(angle),y2=c+r*Math.sin(angle);
    paths+=`<path ${it.attrs?`class="slice" ${it.attrs}`:''} d="M${c},${c} L${x1},${y1} A${r},${r} 0 ${a>Math.PI?1:0} 1 ${x2},${y2} Z" fill="${it.color}" stroke="var(--card)" stroke-width="1.5"><title>${esc(it.label)}: ${it.value} (${(it.value/total*100).toFixed(1)}%)</title></path>`;});
  const legend=items.filter(i=>i.value).map(i=>`<div ${i.attrs?`class="slice" ${i.attrs}`:''}><i style="background:${i.color}"></i>${esc(i.label)} — <b>${i.value}</b> <span class="muted">(${(i.value/total*100).toFixed(1)}%)</span></div>`).join('');
  return `<div class="card"><h2>${title}</h2><div class="pie"><svg width="180" height="180" viewBox="0 0 180 180">${paths||'<circle cx="90" cy="90" r="80" fill="var(--line)"/>'}</svg><div class="legend">${legend||'<span class="muted">sem dados</span>'}</div></div></div>`;
}

async function run(){
  const route=$('route').value,space=route.indexOf(' ');
  const q=new URLSearchParams({service:$('service').value,method:route?route.slice(0,space):'',path:route?route.slice(space+1):'',
    status:statusValue(),start:new Date($('start').value).toISOString(),end:new Date($('end').value).toISOString(),max:$('max').value});
  history.replaceState(null,'','?'+new URLSearchParams({service:$('service').value,route,status:statusValue()}));
  $('out').innerHTML='<div class="card muted">Lendo os logs do Cloud Logging…</div>';
  const t0=performance.now();
  try{
    const r=await fetch('/api/requests?'+q);const data=await r.json();
    if(!r.ok)throw new Error(data.error);
    rows=data.requests;expanded=new Set();
    rows.forEach(r=>{const d=r.db;r.dbCount=d?d.count:null;r.dbClientMs=d?d.clientMs:null;r.dbTookMs=d?d.tookMs:null;r.dbShardMs=d?d.shardMs:null;
      r.dbShare=d&&r.latencyMs?Math.min(100,d.clientMs/r.latencyMs*100):null;
      const c=r.cache,reads=c?c.hits+c.misses:0;r.cacheReads=c?reads:null;r.cacheHits=c?c.hits:null;r.cacheHitRate=reads?c.hits/reads*100:null;
      r.cacheWrites=c?c.writes:null;r.cacheMs=c?c.clientMs:null;});
    render(data,(performance.now()-t0)/1000);
  }catch(e){$('out').innerHTML=`<div class="card err">${esc(e.message)}</div>`;}
}

const ROUTE_COLORS=['#2563eb','#7c3aed','#db2777','#0d9488','#ca8a04','#ea580c','#16a34a','#0891b2','#4f46e5'];
function routeItems(){
  // agrupa por endpoint (com {variaveis}), nao pela URL crua: e-mail e id no caminho fariam cada URL virar uma fatia
  const services=new Set(rows.map(r=>r.service));const groups={};
  const preflight=r=>!r.route&&r.method==='OPTIONS';
  rows.forEach(r=>{const key=r.service+'|'+(r.route||(preflight(r)?'#options':'#fora'));groups[key]=groups[key]||{service:r.service,route:r.route,options:preflight(r),value:0};groups[key].value++;});
  // fora dos endpoints da API (robos de varredura, 404) nao entra na pizza: so o aviso no titulo
  const list=Object.values(groups).filter(g=>g.route||g.options).sort((a,b)=>b.value-a.value);
  const label=g=>{const space=g.route.indexOf(' ');
    const base=g.route?g.route.slice(space+1)+'  ·  '+g.route.slice(0,space):g.options?'preflight de CORS (OPTIONS)':'fora dos endpoints da API';
    return services.size>1?base+'  ('+g.service.replace('jobsnow-','')+')':base;};
  const shown=list.length>10?list.slice(0,9):list;
  const items=shown.map((g,i)=>({label:label(g),value:g.value,color:g.route?ROUTE_COLORS[i%ROUTE_COLORS.length]:g.options?'#cbd5e1':'#94a3b8',
    attrs:g.route?`data-route="${esc(g.route)}" data-service="${esc(g.service)}"`:''}));
  if(list.length>10)items.push({label:'outros '+(list.length-9)+' endpoints',value:list.slice(9).reduce((a,g)=>a+g.value,0),color:'#e2e8f0'});
  return items;
}
function outsideNote(){
  const outside=rows.filter(r=>!r.route&&r.method!=='OPTIONS').length;
  return outside?` <span class="muted" style="font-weight:normal;font-size:12px">(sem ${outside} fora dos endpoints da API)</span>`:'';
}
function render(data,seconds){
  const lat=rows.map(r=>r.latencyMs).filter(v=>v!=null).sort((a,b)=>a-b);
  const mean=lat.reduce((a,b)=>a+b,0)/(lat.length||1);
  const errors=rows.filter(r=>r.status>=500).length;
  const tiles=[['Requisições',rows.length],['Erros 5xx',errors+(rows.length?` (${(errors/rows.length*100).toFixed(1)}%)`:'')],
    ['mín',fmtMs(lat[0])],['p50',fmtMs(pct(lat,50))],['p75',fmtMs(pct(lat,75))],['p90',fmtMs(pct(lat,90))],['p95',fmtMs(pct(lat,95))],
    ['p99',fmtMs(pct(lat,99))],['p99.9',fmtMs(pct(lat,99.9))],['máx',fmtMs(lat[lat.length-1])],['média',fmtMs(mean)]];
  const dbClient=rows.map(r=>r.dbClientMs).filter(v=>v!=null).sort((a,b)=>a-b),dbShare=rows.map(r=>r.dbShare).filter(v=>v!=null).sort((a,b)=>a-b);
  const dbShard=rows.map(r=>r.dbShardMs).filter(v=>v!=null).sort((a,b)=>a-b);
  const cacheRows=rows.filter(r=>r.cache),cacheHits=cacheRows.reduce((a,r)=>a+r.cacheHits,0),cacheReads=cacheRows.reduce((a,r)=>a+r.cacheReads,0);
  tiles.push(['Cache hits',cacheReads?fmtPct(cacheHits/cacheReads*100)+` <span class="muted" style="font-size:12px;font-weight:normal">de ${cacheReads} leituras</span>`:'–']);
  tiles.push(['ES cliente p50',fmtMs(pct(dbClient,50))],['ES cliente p95',fmtMs(pct(dbClient,95))],['ES shards p95',fmtMs(pct(dbShard,95))],['% no ES (mediana)',fmtPct(pct(dbShare,50))]);
  const byStatus={};rows.forEach(r=>byStatus[r.status]=(byStatus[r.status]||0)+1);
  const used={};const statusItems=Object.keys(byStatus).sort().map(s=>{const k=Math.floor(s/100);const shades=CLASS_SHADES[k]||CLASS_SHADES[0];used[k]=(used[k]||0);return{label:'HTTP '+s,attrs:`data-status="${s}"`,value:byStatus[s],color:shades[used[k]++%shades.length]};});
  const bucketCounts=BUCKETS.map(()=>0);lat.forEach(v=>{bucketCounts[BUCKETS.findIndex(b=>v<b[0])]++;});
  const bucketItems=BUCKETS.map((b,i)=>({label:b[1],value:bucketCounts[i],color:BUCKET_COLORS[i]}));
  const byMethod={};rows.forEach(r=>byMethod[r.method]=(byMethod[r.method]||0)+1);
  const methodColors=['#2563eb','#7c3aed','#db2777','#0d9488','#ca8a04','#64748b'];
  const methodItems=Object.entries(byMethod).sort((a,b)=>b[1]-a[1]).map(([m,v],i)=>({label:m||'(?)',value:v,color:methodColors[i%methodColors.length]}));
  $('out').innerHTML=
    (data.truncated?`<div class="card err">Atingiu o máximo de ${rows.length} requisições: o resultado cobre só as mais recentes do período. Aumente o máximo ou reduza o período.</div>`:'')+
    `<div class="tiles" style="margin-bottom:14px">${tiles.map(([k,v])=>`<div class="tile"><span>${k}</span><b>${v}</b></div>`).join('')}</div>`+dbNote(data)+
    `<div class="pies">${pie('Por status HTTP',statusItems)}${pie('Por URL (endpoint)'+outsideNote(),routeItems())}${pie('Por faixa de latência',bucketItems)}${pie('Por método',methodItems)}</div>`+
    cacheCard()+queriesCard()+
    `<div class="card"><h2>Requisições <span class="muted" style="font-weight:normal">(${rows.length}, lidas em ${seconds.toFixed(1)} s · clique numa linha para ver as queries dela)</span> <button class="ghost" id="csv" style="float:right">Baixar CSV</button><button class="ghost" id="cols" style="float:right;margin-right:8px">Colunas</button></h2><div class="colpick" id="colpick"></div><div class="scroll" id="tbl"></div></div>`+
    `<div class="card"><code>${esc(data.filter)}</code>${data.discarded?`<div class="muted" style="margin-top:6px">${data.discarded} requisições vieram do Cloud Logging mas pertencem a outro endpoint (mais específico ou mais longo) e ficaram de fora.</div>`:''}</div>`;
  $('csv').onclick=downloadCsv;$('cols').onclick=()=>$('colpick').classList.toggle('open');columnPicker();table();
  document.querySelectorAll('.slice[data-status]').forEach(p=>p.onclick=()=>{setStatus(p.dataset.status);run();});
  document.querySelectorAll('.slice[data-route]').forEach(p=>p.onclick=async()=>{
    if($('service').value!==p.dataset.service){$('service').value=p.dataset.service;await loadRoutes(p.dataset.route);}else{$('route').value=p.dataset.route;}
    run();});
}

const COLS=[['timestamp','Quando'],['service','Serviço'],['method','Método'],['status','Status'],['latencyMs','Latência',1],
  ['cacheReads','Cache leituras',1],['cacheHitRate','Cache hits',1],['cacheWrites','Cache escritas',1],['cacheMs','Cache cliente',1],
  ['dbCount','ES nº',1],['dbClientMs','ES cliente',1],['dbTookMs','ES took',1],['dbShardMs','ES shards',1],['dbShare','% no ES',1],
  ['url','URL'],['responseSize','Bytes',1],['remoteIp','IP'],['revision','Revisão']];
let expanded=new Set();
const keyOf=r=>r.trace||r.timestamp+r.url;
// colunas ocultas: guardadas no navegador (por quem abre o painel), sobrevivem a novas buscas e a reaberturas
const HIDDEN_KEY='painel27.colunasOcultas.v3';
// sem escolha guardada, as colunas do Elasticsearch e do cache comecam ocultas; a escolha da v2 (antes das colunas do
// cache) e mantida, com as do cache acrescentadas como ocultas
const CACHE_COLUMNS=['cacheReads','cacheHitRate','cacheWrites','cacheMs'];
const DEFAULT_HIDDEN=['dbCount','dbClientMs','dbTookMs','dbShardMs','dbShare',...CACHE_COLUMNS];
let hidden=new Set(DEFAULT_HIDDEN);
try{const saved=localStorage.getItem(HIDDEN_KEY),previous=localStorage.getItem('painel27.colunasOcultas.v2');
  if(saved!==null)hidden=new Set(JSON.parse(saved));else if(previous!==null)hidden=new Set([...JSON.parse(previous),...CACHE_COLUMNS]);}catch(e){}
function saveHidden(){try{localStorage.setItem(HIDDEN_KEY,JSON.stringify([...hidden]));}catch(e){}}
const CELLS={
  timestamp:r=>`<td>${new Date(r.timestamp).toLocaleString('pt-BR')}</td>`,service:r=>`<td>${esc(r.service)}</td>`,method:r=>`<td>${esc(r.method)}</td>`,
  status:r=>`<td class="s${Math.floor(r.status/100)}">${r.status}</td>`,latencyMs:r=>`<td class="num">${fmtMs(r.latencyMs??NaN)}</td>`,
  cacheReads:r=>`<td class="num">${r.cacheReads??'–'}</td>`,cacheHitRate:r=>`<td class="num">${r.cacheReads?fmtPct(r.cacheHitRate)+` <span class="muted">(${r.cacheHits}/${r.cacheReads})</span>`:'–'}</td>`,
  cacheWrites:r=>`<td class="num">${r.cacheWrites??'–'}</td>`,cacheMs:r=>`<td class="num">${dash(r.cacheMs)}</td>`,
  dbCount:r=>`<td class="num">${r.dbCount??'–'}</td>`,dbClientMs:r=>`<td class="num">${dash(r.dbClientMs)}</td>`,dbTookMs:r=>`<td class="num">${dash(r.dbTookMs)}</td>`,
  dbShardMs:r=>`<td class="num">${dash(r.dbShardMs)}</td>`,dbShare:r=>`<td class="num">${fmtPct(r.dbShare)}</td>`,
  url:r=>`<td class="url">${esc(r.url)}</td>`,responseSize:r=>`<td class="num">${r.responseSize}</td>`,remoteIp:r=>`<td>${esc(r.remoteIp)}</td>`,revision:r=>`<td>${esc(r.revision)}</td>`};
// explicacao das colunas do Elasticsearch, mostrada ao passar o mouse sobre o nome delas no seletor de colunas
const COL_HINTS={
  cacheReads:'Quantas leituras a requisição fez no cache (Memorystore for Valkey) antes de ir ao Elasticsearch. Vazio quando a requisição veio de revisão anterior à medição do cache (05/11/2026, noite).',
  cacheHitRate:'Taxa de acerto do cache: das leituras da requisição, quantas acharam a chave (hits) e evitaram o Elasticsearch. Entre parênteses, hits / leituras. Clique na linha para ver por entidade.',
  cacheWrites:'Quantos comandos de escrita a requisição mandou ao cache: gravação de um valor lido do Elasticsearch depois de um miss, e apagamento de chaves depois de uma gravação ou antes de uma busca.',
  cacheMs:'Soma do tempo de ida e volta de todos os comandos ao cache (leituras e escritas), medido pela própria API.',
  dbCount:'Quantas chamadas ao Elasticsearch a requisição fez (buscas, gets por id, mgets, gravações). Vazio quando a requisição não tocou o banco ou veio de revisão anterior a 05/11/2026.',
  dbClientMs:'Soma do tempo de ida e volta de todas as chamadas ao Elasticsearch, medido pela própria API: inclui rede entre o Cloud Run e a VM, fila no Elasticsearch, processamento e leitura da resposta.',
  dbTookMs:'Soma do tempo que o próprio Elasticsearch informa na resposta (campo took): só buscas e bulks informam; gets por id e mgets não. A diferença para o ES cliente é rede e serialização.',
  dbShardMs:'Esforço de processamento do Elasticsearch: soma do tempo de cada shard nas fases query, fetch e escrita, lida do slowlog. Pode passar do took, porque os shards rodam em paralelo. Só aparece com o 33-slowlog-de-todas-as-queries.py ligado.',
  dbShare:'Quanto da latência total da requisição foi gasto esperando o Elasticsearch (ES cliente dividido pela latência). Alto: o gargalo é o banco. Baixo: o tempo está na API ou na rede até ela.'};
function columnPicker(){
  const visible=COLS.filter(([k])=>!hidden.has(k)).length;
  $('colpick').innerHTML=COLS.map(([k,t])=>`<label${COL_HINTS[k]?` title="${esc(COL_HINTS[k])}" style="cursor:help"`:''}><input type="checkbox" data-col="${k}" ${hidden.has(k)?'':'checked'}>${t}</label>`).join('')+
    `<button type="button" class="ghost" id="allcols" style="padding:2px 10px">mostrar todas</button><span class="muted">${visible} de ${COLS.length} visíveis</span>`;
  document.querySelectorAll('#colpick input').forEach(box=>box.onchange=()=>{
    if(!box.checked&&COLS.filter(([k])=>!hidden.has(k)).length===1){box.checked=true;return;}
    box.checked?hidden.delete(box.dataset.col):hidden.add(box.dataset.col);saveHidden();columnPicker();table();});
  $('allcols').onclick=()=>{hidden.clear();saveHidden();columnPicker();table();};
}
function table(){
  const cols=COLS.filter(([k])=>!hidden.has(k));
  const value=v=>v==null?-Infinity:v;
  const sorted=[...rows].sort((a,b)=>(value(a[sortKey])>value(b[sortKey])?1:value(a[sortKey])<value(b[sortKey])?-1:0)*sortDir);const shown=sorted.slice(0,2000);
  $('tbl').innerHTML=`<table><thead><tr>${cols.map(([k,t,n])=>`<th data-k="${k}" class="${n?'num':''}">${t}${k===sortKey?(sortDir>0?' ▲':' ▼'):''}</th>`).join('')}</tr></thead><tbody>`+
    shown.map((r,i)=>`<tr class="pick" data-i="${i}">${cols.map(([k])=>CELLS[k](r)).join('')}</tr>`+
      (expanded.has(keyOf(r))?`<tr class="detail"><td colspan="${cols.length}">${callsTable(r)}</td></tr>`:'')).join('')+
    `</tbody></table>`+(rows.length>shown.length?`<div class="muted" style="padding:8px">Mostrando 2000 de ${rows.length}; o CSV traz todas.</div>`:'');
  document.querySelectorAll('#tbl th[data-k]').forEach(th=>th.onclick=()=>{const k=th.dataset.k;sortDir=k===sortKey?-sortDir:-1;sortKey=k;table();});
  document.querySelectorAll('#tbl tr.pick').forEach(tr=>tr.onclick=()=>{const k=keyOf(shown[+tr.dataset.i]);expanded.has(k)?expanded.delete(k):expanded.add(k);table();});
}
function cacheDetail(r){
  const c=r.cache;if(!c)return '';
  const name=e=>e===''?'(chaves de serviço, sem entidade)':e;
  const rowsOf=c.byEntity.map(e=>`<tr><td>${esc(name(e.entity))}</td><td class="num">${e.hits+e.misses}</td><td class="num">${e.hits}</td><td class="num">${e.misses}</td><td class="num">${fmtPct(e.hits/(e.hits+e.misses)*100)}</td></tr>`).join('');
  return `<div class="muted" style="margin-bottom:4px">Cache: ${c.hits} hits, ${c.misses} misses, ${c.writes} escritas, ${fmtMs(c.clientMs)} no cliente.</div>`+
    (rowsOf?`<table class="calls" style="margin-bottom:10px;width:auto"><thead><tr><th>Entidade lida no cache</th><th class="num">Leituras</th><th class="num">Hits</th><th class="num">Misses</th><th class="num">Hits %</th></tr></thead><tbody>${rowsOf}</tbody></table>`:'');
}
function callsTable(r){
  const d=r.db,cache=cacheDetail(r);
  if(!d||!d.calls.length)return cache+'<span class="muted">Sem chamadas ao Elasticsearch registradas (a requisição não tocou o banco, ou veio de revisão anterior a 05/11/2026).</span>';
  return cache+`<table class="calls"><thead><tr><th>#</th><th>Chamada</th><th>Status</th><th class="num">Cliente</th><th class="num">Took</th><th class="num">Query (shards)</th><th class="num">Fetch (shards)</th><th class="num">Escrita (shards)</th><th class="num">Shards</th><th class="num">Hits</th><th class="num">Bytes env. / rec.</th><th>Query enviada (slowlog)</th></tr></thead><tbody>`+
    d.calls.map(c=>`<tr><td>${c.sequence}</td><td title="${esc(c.method+' '+c.path)}" style="cursor:help;white-space:nowrap">${esc(c.api||c.method+' '+c.path)}</td><td class="s${Math.floor(c.status/100)}">${c.status}</td><td class="num">${fmtMs(c.clientMs)}</td><td class="num">${dash(c.tookMs)}</td>`+
      `<td class="num">${dash(c.queryMs)}</td><td class="num">${dash(c.fetchMs)}</td><td class="num">${c.writeMs==null?'–':fmtMs(c.writeMs)+' ('+c.writeDocs+' doc)'}</td><td class="num">${c.shards??'–'}</td><td class="num">${c.hits??'–'}</td>`+
      `<td class="num">${c.requestBytes} / ${c.responseBytes}</td><td class="src" title="${esc(c.source)}">${esc(c.source.slice(0,200))}</td></tr>`).join('')+
    `</tbody></table>`+(d.unattributedWriteMs?`<div class="muted">Escrita no slowlog sem chamada correspondente: ${fmtMs(d.unattributedWriteMs)}</div>`:'');
}
function dbNote(data){
  const measured=rows.filter(r=>r.db&&r.db.count).length;
  const slow=data.slowlogLines?`${data.slowlogLines} linhas do slowlog${data.slowlogTruncated?' (cortado no máximo)':''}`:'nenhuma linha do slowlog no período: as colunas de shards ficam vazias enquanto o <code>33-slowlog-de-todas-as-queries.py</code> estiver desligado';
  return `<div class="muted" style="margin:-6px 0 12px">Elasticsearch: ${measured} de ${rows.length} requisições com chamadas medidas · ${slow}. <b>Cliente</b> = ida e volta vista pela API · <b>took</b> = tempo que o ES informa na resposta (só busca e bulk) · <b>shards</b> = soma do tempo de cada shard no slowlog, o esforço do ES (pode passar do took: os shards rodam em paralelo). Get por id e mget só têm o tempo do cliente.</div>`;
}
function cacheCard(){
  // cache por endpoint: leituras, hits, misses e escritas somados nas requisicoes do periodo
  const groups={};const manyServices=new Set(rows.map(x=>x.service)).size>1;
  rows.forEach(r=>{if(!r.cache)return;const route=(r.route||'(fora dos endpoints)')+(manyServices?'  ('+r.service.replace('jobsnow-','')+')':'');
    const g=groups[route]=groups[route]||{route,requests:0,reads:0,hits:0,misses:0,writes:0,ms:0,dbCalls:0,noDb:0};
    g.requests++;g.reads+=r.cacheReads;g.hits+=r.cacheHits;g.misses+=r.cacheReads-r.cacheHits;g.writes+=r.cacheWrites;g.ms+=r.cacheMs;
    const calls=r.db?r.db.count:0;g.dbCalls+=calls;if(!calls)g.noDb++;});
  const list=Object.values(groups).sort((a,b)=>b.reads-a.reads);if(!list.length)return '';
  return `<div class="card"><h2>Cache por endpoint <span class="muted" style="font-weight:normal">(Memorystore for Valkey; somado nas requisições do período, em ordem de leituras)</span></h2><div class="scroll"><table><thead><tr><th>Endpoint</th><th class="num">Requisições</th><th class="num">Leituras</th><th class="num">Hits</th><th class="num">Misses</th><th class="num">Hits %</th><th class="num">Escritas</th><th class="num">Cache cliente</th><th class="num">ES por requisição</th><th class="num">Sem ir ao ES</th></tr></thead><tbody>`+
    list.map(g=>`<tr><td class="url">${esc(g.route)}</td><td class="num">${g.requests}</td><td class="num">${g.reads}</td><td class="num">${g.hits}</td><td class="num">${g.misses}</td><td class="num">${g.reads?fmtPct(g.hits/g.reads*100):'–'}</td>`+
      `<td class="num">${g.writes}</td><td class="num">${fmtMs(g.ms)}</td><td class="num">${(g.dbCalls/g.requests).toFixed(1)}</td><td class="num">${g.noDb} (${fmtPct(g.noDb/g.requests*100)})</td></tr>`).join('')+
    `</tbody></table></div><div class="muted" style="margin-top:6px"><b>Sem ir ao ES</b>: requisições atendidas só pelo cache. Requisições que não leram nem gravaram nada no cache e não chamaram o ES não entram.</div></div>`;
}
function queryGroups(){
  const groups={};const manyServices=new Set(rows.map(x=>x.service)).size>1;
  rows.forEach(r=>{if(!r.db)return;const route=r.route||'(fora dos endpoints)';const seen=new Set();
    r.db.calls.forEach(c=>{const k=r.service+'|'+route+'|'+c.signature;
      const g=groups[k]=groups[k]||{route:route+(manyServices?'  ('+r.service.replace('jobsnow-','')+')':''),signature:c.signature,calls:0,requests:0,client:[],took:0,tookN:0,query:0,fetch:0,write:0,shard:0,shardN:0,source:''};
      g.calls++;if(!seen.has(k)){seen.add(k);g.requests++;}g.client.push(c.clientMs);
      if(c.tookMs!=null){g.took+=c.tookMs;g.tookN++;}
      if(c.shardMs!=null){g.shard+=c.shardMs;g.shardN++;g.query+=c.queryMs||0;g.fetch+=c.fetchMs||0;g.write+=c.writeMs||0;}
      if(!g.source&&c.source)g.source=c.source;});});
  return Object.values(groups).map(g=>{const sorted=[...g.client].sort((a,b)=>a-b);return {...g,clientSum:sorted.reduce((a,b)=>a+b,0),p50:pct(sorted,50),p95:pct(sorted,95)};}).sort((a,b)=>b.clientSum-a.clientSum);
}
function queriesCard(){
  const list=queryGroups();if(!list.length)return '';
  const multi=new Set(list.map(g=>g.route)).size>1;
  return `<div class="card"><h2>Queries por endpoint <span class="muted" style="font-weight:normal">(somadas nas requisições do período; em ordem do tempo total no cliente)</span></h2><div class="scroll"><table><thead><tr>${multi?'<th>Endpoint</th>':''}<th>Chamada ao ES</th><th class="num">Chamadas</th><th class="num">Requisições</th><th class="num">Por requisição</th><th class="num">Cliente p50</th><th class="num">Cliente p95</th><th class="num">Cliente total</th><th class="num">Took médio</th><th class="num">Shards total</th><th class="num">Query</th><th class="num">Fetch</th><th class="num">Escrita</th><th>Exemplo de query</th></tr></thead><tbody>`+
    list.map(g=>`<tr>${multi?`<td class="url">${esc(g.route)}</td>`:''}<td class="url">${esc(g.signature)}</td><td class="num">${g.calls}</td><td class="num">${g.requests}</td><td class="num">${(g.calls/g.requests).toFixed(1)}</td><td class="num">${fmtMs(g.p50)}</td><td class="num">${fmtMs(g.p95)}</td><td class="num">${fmtMs(g.clientSum)}</td>`+
      `<td class="num">${g.tookN?fmtMs(g.took/g.tookN):'–'}</td><td class="num">${g.shardN?fmtMs(g.shard):'–'}</td><td class="num">${g.shardN?fmtMs(g.query):'–'}</td><td class="num">${g.shardN?fmtMs(g.fetch):'–'}</td><td class="num">${g.shardN&&g.write?fmtMs(g.write):'–'}</td><td class="src" title="${esc(g.source)}">${esc(g.source.slice(0,140))}</td></tr>`).join('')+
    `</tbody></table></div></div>`;
}
function downloadCsv(){
  const keys=['timestamp','service','revision','method','status','latencyMs','cacheReads','cacheHits','cacheWrites','cacheMs','dbCount','dbClientMs','dbTookMs','dbShardMs','dbShare','url','responseSize','remoteIp','userAgent','trace'];
  const q=v=>'"'+String(v??'').replace(/"/g,'""')+'"';
  const csv=[keys.join(';'),...rows.map(r=>keys.map(k=>q(r[k])).join(';'))].join('\n');
  const a=document.createElement('a');a.href=URL.createObjectURL(new Blob(['﻿'+csv],{type:'text/csv'}));a.download='requisicoes-cloud-run.csv';a.click();
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
