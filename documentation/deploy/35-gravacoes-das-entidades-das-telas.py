# Painel local das gravacoes, em producao (jobsnow-prd), das 18 entidades alimentadas pelas telas do site (levantamento
# de 2026-11-05: as que um endpoint chamado pelo front grava na requisicao ou manda gravar por fila). O "quando" de cada
# gravacao vem, por entidade:
#   - versionable (@CcpEntityVersionable): jn_versionable, uma linha por gravacao com operation (create, update, delete) e
#     timestamp, ate o expurgo do historico;
#   - expurgable (@CcpEntityDisposable): jn_disposable_record, uma copia por chave com trueTimestamp, o momento da ULTIMA
#     gravacao daquela chave (as anteriores nao ficam);
#   - nenhum dos dois: logs das chamadas de escrita ao Elasticsearch (linha jobsnowDbCalls das APIs e log mensagens dos
#     consumidores, ver medicao_elasticsearch.py), so a partir de 2026-11-05; um _bulk conta uma vez por entidade que toca.
# Le o Elasticsearch de producao por um tunel IAP proprio (porta local 9211, aberto pelo painel e fechado ao sair), com o
# Authorization de C:\segredos\producao.json lido so na memoria do processo. Nada e gravado.
# Uso: python 35-gravacoes-das-entidades-das-telas.py [porta]   (abre http://127.0.0.1:8771; atalho em Desktop\paineis)
import atexit
import calendar
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import medicao_elasticsearch  # noqa: E402

PROJECT = "jobsnow-prd"
GCLOUD = os.path.join(os.environ["LOCALAPPDATA"], "Google", "Cloud SDK", "google-cloud-sdk", "bin", "gcloud.cmd")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8771
TUNNEL_PORT = 9211
PROPERTIES_FILE = r"C:\segredos\producao.json"
STDOUT_LOG_NAME = "projects/%s/logs/run.googleapis.com%%2Fstdout" % PROJECT
MESSAGES_LOG_NAME = "projects/%s/logs/mensagens" % PROJECT
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# entidade (indice), classe, fonte do "quando", quem grava (a tela, na requisicao, ou o consumidor da fila) e detalhe
ENTITIES = [
    ("vis_viewed_resume", "VisEntityViewedResume", "versionable", "tela", ""),
    ("vis_recruiter", "VisEntityRecruiter", "versionable", "tela", "só apaga (descadastro)"),
    ("js_login_answers", "JsEntityLoginAnswers", "versionable", "tela", ""),
    ("vis_resume", "VisEntityResume", "versionable", "fila", ""),
    ("vis_skill_pending", "VisEntitySkillPending", "versionable", "fila", ""),
    ("vis_skill_fix_hierarchy_pending", "VisEntitySkillFixHierarchyPending", "versionable", "fila", ""),
    ("js_login_password", "JsEntityLoginPassword", "versionable", "fila", "a tela apaga no bloqueio"),
    ("jn_ticket_daily_limit", "JnEntityTicketDailyLimit", "expurgable", "tela", "diário"),
    ("js_login_password_attempts", "JsEntityLoginPasswordAttempts", "expurgable", "tela", "diário"),
    ("js_login_token", "JsEntityLoginToken", "expurgable", "fila", "mensal; a tela apaga no bloqueio"),
    ("js_login_token_request_resend", "JsEntityLoginTokenRequestResend", "expurgable", "fila", "diário"),
    ("js_login_token_request_unlock", "JsEntityLoginTokenRequestUnlock", "expurgable", "fila", "diário"),
    ("js_login_session_validation", "JsEntityLoginSessionValidation", "expurgable", "fila", "por hora"),
    ("js_login_session_conflict", "JsEntityLoginSessionConflict", "expurgable", "fila", "por hora; o logout apaga"),
    ("js_contact_us", "JsEntityContactUs", "logs", "tela", ""),
    ("vis_skill_synonym", "VisEntitySkillSynonym", "logs", "tela", "bulk"),
    ("jn_login_email", "JnEntityLoginEmail", "logs", "tela", ""),
    ("js_login_token_attempts", "JsEntityLoginTokenAttempts", "logs", "tela", ""),
]
NAMES_BY_SOURCE = {source: [entity[0] for entity in ENTITIES if entity[2] == source] for source in ("versionable", "expurgable", "logs")}
VERSIONABLE_OPERATIONS = {"create": "cria", "update": "atualiza", "delete": "apaga"}
OPERATION_BY_API = {"Index API": "grava", "Create API": "cria", "Update API": "atualiza", "Update by query API": "atualiza",
                    "Delete API": "apaga", "Delete by query API": "apaga", "Bulk API": "bulk"}
LAST_WRITE = "última gravação"

token_lock = threading.Lock()
token_cache = {"value": "", "expires": 0.0}
tunnel_lock = threading.Lock()
tunnel_state = {"process": None}


def gcloud(*args):
    result = subprocess.run([GCLOUD, *args], capture_output=True, text=True, creationflags=NO_WINDOW)
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


def port_open():
    with socket.socket() as probe:
        probe.settimeout(1)
        return probe.connect_ex(("127.0.0.1", TUNNEL_PORT)) == 0


def ensure_tunnel():
    # o tunel IAP ate a VM, aberto na primeira consulta e reaberto se cair; um tunel ja aberto na porta e reaproveitado
    with tunnel_lock:
        if port_open():
            return
        arguments = [GCLOUD, "compute", "ssh", "jobsnow-vm", "--project=%s" % PROJECT, "--zone=southamerica-east1-a",
                     "--tunnel-through-iap", "--quiet", "--", "-L", "%d:localhost:9200" % TUNNEL_PORT, "-N"]
        tunnel_state["process"] = subprocess.Popen(arguments, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=NO_WINDOW)
        for _ in range(60):
            time.sleep(1.5)
            if port_open():
                return
        raise RuntimeError("o túnel até o Elasticsearch de produção não abriu (porta %d)" % TUNNEL_PORT)


def close_tunnel():
    process = tunnel_state["process"]
    if process and process.poll() is None:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(process.pid)], capture_output=True, creationflags=NO_WINDOW)


atexit.register(close_tunnel)


def es_auth():
    # o valor nunca sai deste processo: nem tela, nem log, nem linha de comando
    with open(PROPERTIES_FILE, encoding="utf-8") as source:
        properties = json.load(source)
    auth = properties.get("elasticsearch.secret") or properties.get("elasticsearch", {}).get("secret", "")
    return auth


def es_search(index, body):
    ensure_tunnel()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request = urllib.request.Request("http://127.0.0.1:%d/%s/_search" % (TUNNEL_PORT, index), data=json.dumps(body).encode("utf-8"), method="POST")
    request.add_header("Content-Type", "application/json")
    auth = es_auth()
    if auth:
        request.add_header("Authorization", auth)
    with opener.open(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def es_cat_indices():
    # a mesma lista de /_cat/indices?s=docs.count:desc,index:asc&v=true, em texto, do ES de producao
    ensure_tunnel()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request = urllib.request.Request("http://127.0.0.1:%d/_cat/indices?s=docs.count:desc,index:asc&v=true" % TUNNEL_PORT)
    auth = es_auth()
    if auth:
        request.add_header("Authorization", auth)
    with opener.open(request, timeout=120) as response:
        return response.read().decode("utf-8")


def histogram(field, interval, offset):
    return {"histogram": {"field": field, "interval": interval, "offset": offset, "min_doc_count": 1}}


def read_versionable(start, end, interval, offset):
    body = {"size": 0, "track_total_hits": False,
            "query": {"bool": {"filter": [{"terms": {"entity": NAMES_BY_SOURCE["versionable"]}}, {"range": {"timestamp": {"gte": start, "lt": end}}}]}},
            "aggs": {"entity": {"terms": {"field": "entity", "size": 100}, "aggs": {
                "last": {"max": {"field": "timestamp"}},
                "operation": {"terms": {"field": "operation", "size": 10}, "aggs": {"time": histogram("timestamp", interval, offset)}}}}}}
    result = es_search("jn_versionable", body)
    rows, last = [], {}
    for entity in result["aggregations"]["entity"]["buckets"]:
        last[entity["key"]] = entity["last"]["value"]
        for operation in entity["operation"]["buckets"]:
            label = VERSIONABLE_OPERATIONS.get(operation["key"], operation["key"])
            for bucket in operation["time"]["buckets"]:
                rows.append({"entity": entity["key"], "operation": label, "bucket": int(bucket["key"]), "count": bucket["doc_count"]})
    return rows, last


def read_expurgable(start, end, interval, offset):
    body = {"size": 0, "track_total_hits": False,
            "query": {"bool": {"filter": [{"terms": {"entity": NAMES_BY_SOURCE["expurgable"]}}, {"range": {"trueTimestamp": {"gte": start, "lt": end}}}]}},
            "aggs": {"entity": {"terms": {"field": "entity", "size": 100}, "aggs": {
                "last": {"max": {"field": "trueTimestamp"}}, "time": histogram("trueTimestamp", interval, offset)}}}}
    result = es_search("jn_disposable_record", body)
    rows, last = [], {}
    for entity in result["aggregations"]["entity"]["buckets"]:
        last[entity["key"]] = entity["last"]["value"]
        for bucket in entity["time"]["buckets"]:
            rows.append({"entity": entity["key"], "operation": LAST_WRITE, "bucket": int(bucket["key"]), "count": bucket["doc_count"]})
    return rows, last


def indices_of(raw):
    if "indices" in raw:
        return set(raw["indices"] or [])
    path = raw.get("path", "")
    first = path.lstrip("/").split("/", 1)[0].split("?", 1)[0]
    return set() if not first or first.startswith("_") else set(first.split(","))


def iso(millis):
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(millis / 1000)) + ".%03dZ" % (millis % 1000)


def read_logs(start, end, interval, offset, maximum):
    window = ['timestamp>="%s"' % iso(start), 'timestamp<"%s"' % iso(end)]
    api_filters = ['logName="%s"' % STDOUT_LOG_NAME, 'resource.type="cloud_run_revision"', 'jsonPayload.kind="jobsnowDbCalls"', "jsonPayload.dbCallsCount>0"] + window
    queue_filters = ['logName="%s"' % MESSAGES_LOG_NAME, "jsonPayload.dbCallsCount>0"] + window
    api_entries, api_truncated = medicao_elasticsearch.list_entries(access_token, forget_token, PROJECT, api_filters, maximum)
    queue_entries, queue_truncated = medicao_elasticsearch.list_entries(access_token, forget_token, PROJECT, queue_filters, maximum)
    wanted = set(NAMES_BY_SOURCE["logs"])
    counts, last = {}, {}
    for entry in api_entries + queue_entries:
        moment = entry.get("timestamp", "")
        millis = calendar.timegm(time.strptime(moment[:19], "%Y-%m-%dT%H:%M:%S")) * 1000
        bucket = (millis - offset) // interval * interval + offset
        for raw in entry.get("jsonPayload", {}).get("dbCalls", []):
            operation = OPERATION_BY_API.get(medicao_elasticsearch.api_name(raw.get("method", ""), raw.get("path", "")))
            if not operation:
                continue
            for entity in indices_of(raw) & wanted:
                key = (entity, operation, bucket)
                counts[key] = counts.get(key, 0) + 1
                last[entity] = max(last.get(entity, 0), millis)
    rows = [{"entity": entity, "operation": operation, "bucket": bucket, "count": count} for (entity, operation, bucket), count in counts.items()]
    return rows, last, {"units": len(api_entries) + len(queue_entries), "truncated": api_truncated or queue_truncated}


def read_writes(query):
    start, end = int(query["start"]), int(query["end"])
    interval = max(60000, int(query["interval"]))
    offset = int(query.get("offset", "0")) % interval
    result = {"entities": [{"entity": name, "className": class_name, "source": source, "writer": writer, "detail": detail}
                           for name, class_name, source, writer, detail in ENTITIES],
              "interval": interval, "offset": offset, "rows": [], "last": {}, "errors": {}, "logs": {"units": 0, "truncated": False}}
    readers = {"versionable": lambda: read_versionable(start, end, interval, offset), "expurgable": lambda: read_expurgable(start, end, interval, offset),
               "logs": lambda: read_logs(start, end, interval, offset, int(query.get("max", "20000")))}
    for source, reader in readers.items():
        try:
            read = reader()
            result["rows"] += read[0]
            result["last"].update(read[1])
            if source == "logs":
                result["logs"] = read[2]
        except urllib.error.HTTPError as error:
            result["errors"][source] = "%s: %s" % (error.code, error.read().decode(errors="replace")[:300])
        except Exception as error:
            result["errors"][source] = "%s: %s" % (type(error).__name__, error)
    return result


class Handler(BaseHTTPRequestHandler):
    def send(self, status, content_type, payload):
        data = payload.encode() if isinstance(payload, str) else payload
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        query = {key: values[0] for key, values in urllib.parse.parse_qs(parsed.query).items()}
        try:
            if parsed.path == "/":
                return self.send(200, "text/html; charset=utf-8", PAGE.replace("__PROJECT__", PROJECT))
            if parsed.path == "/api/writes":
                return self.send(200, "application/json; charset=utf-8", json.dumps(read_writes(query)))
            if parsed.path == "/api/indices":
                return self.send(200, "text/plain; charset=utf-8", es_cat_indices())
            return self.send(404, "application/json; charset=utf-8", json.dumps({"error": "not found"}))
        except Exception as error:
            return self.send(500, "application/json; charset=utf-8", json.dumps({"error": "%s: %s" % (type(error).__name__, error)}))

    def log_message(self, format, *args):
        if sys.stderr:
            sys.stderr.write("%s %s\n" % (self.log_date_time_string(), format % args))


PAGE = r"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Gravações das telas</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--fg:#1d2330;--muted:#667085;--line:#e3e6eb;--accent:#2563eb;--grid:#eef0f3}
@media (prefers-color-scheme:dark){:root{--bg:#12151b;--card:#1b1f27;--fg:#e6e8ec;--muted:#98a2b3;--line:#2c323d;--accent:#5b8def;--grid:#232833}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,Segoe UI,sans-serif}
header{padding:16px 20px;border-bottom:1px solid var(--line);background:var(--card)}h1{margin:0;font-size:18px}
main{padding:16px 20px;max-width:1400px;margin:0 auto}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px;margin-bottom:14px;min-width:0}
.range{display:flex;gap:10px;flex-wrap:wrap;align-items:end;margin-bottom:12px}
label{display:flex;flex-direction:column;gap:4px;font-size:12px;color:var(--muted)}
input,button{font:inherit;padding:7px 9px;border:1px solid var(--line);border-radius:7px;background:var(--bg);color:var(--fg)}
button{background:var(--accent);color:#fff;border:0;cursor:pointer}button.ghost{background:transparent;color:var(--accent);border:1px solid var(--line);padding:3px 9px}
.checks{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px}
fieldset{border:1px solid var(--line);border-radius:8px;padding:8px 10px;margin:0;min-width:0}legend{font-size:12px;color:var(--muted);padding:0 4px}
fieldset label{flex-direction:row;align-items:center;gap:6px;font-size:13px;color:var(--fg);padding:2px 0;cursor:pointer;word-break:break-all}
fieldset label input{padding:0;margin:0}fieldset .muted{font-size:11.5px}
.bar{display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin:4px 0 8px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-bottom:14px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px}.tile b{display:block;font-size:20px}.tile span{font-size:12px;color:var(--muted)}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:14px}.grid4{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}
@media (max-width:520px){.grid2,.grid4{grid-template-columns:1fr}}
.chart{position:relative}.chart svg{width:100%;height:auto;display:block}
.tip{position:absolute;pointer-events:none;background:var(--card);border:1px solid var(--line);border-radius:6px;padding:4px 8px;font-size:12px;white-space:nowrap;display:none;box-shadow:0 2px 8px rgba(0,0,0,.12);z-index:2}
.keys{display:flex;gap:12px;flex-wrap:wrap;font-size:12px;color:var(--muted);margin-top:4px}.keys i{display:inline-block;width:10px;height:3px;margin-right:5px;vertical-align:middle}
.pie{display:flex;gap:16px;align-items:center;flex-wrap:wrap}.pie svg{flex:none}
.legend{display:flex;flex-direction:column;gap:3px;font-size:13px;min-width:0;word-break:break-all}.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px}
h2{font-size:15px;margin:0 0 10px}
table{width:100%;border-collapse:collapse;font-size:12.5px}th,td{padding:5px 7px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{color:var(--muted);position:sticky;top:0;background:var(--card);cursor:pointer}td.num,th.num{text-align:right;white-space:nowrap}
tr.zero td{color:var(--muted)}.scroll{max-height:620px;overflow:auto}.muted{color:var(--muted)}.err{color:#d92d20;white-space:pre-wrap}
</style></head><body>
<header><h1>Gravações das entidades das telas · __PROJECT__</h1></header>
<main>
<div class="card">
<div class="range"><label>De<input type="datetime-local" id="start"></label><label>Até<input type="datetime-local" id="end"></label>
<button type="button" id="go">Buscar</button><span class="muted">Período:</span><span id="presets" style="display:contents"></span></div>
<div class="bar"><b style="font-size:13px">Entidades</b><button type="button" class="ghost" id="all">todas</button><button type="button" class="ghost" id="none">nenhuma</button>
<button type="button" class="ghost" id="screen">só as que a tela grava</button><button type="button" class="ghost" id="queue">só as que a fila grava</button><span class="muted" id="count"></span></div>
<div class="checks" id="entities"></div>
<div class="bar" style="margin-top:10px"><b style="font-size:13px">Operações</b><span id="operations" style="display:contents"></span></div>
</div>
<div id="out"><div class="card muted">Abrindo o túnel até o Elasticsearch de produção e lendo as gravações…</div></div>
<div class="card"><h2>Índices de produção <span class="muted" style="font-weight:normal;font-size:12px">(<code>_cat/indices?s=docs.count:desc,index:asc&amp;v=true</code>, só as entidades marcadas no filtro)</span></h2>
<div class="bar" style="margin:0 0 8px"><button type="button" class="ghost" id="reloadIndices">Atualizar</button>
<button type="button" class="ghost" id="autoIndices">Auto atualizar: desligado</button>
<label style="flex-direction:row;align-items:center;gap:6px">a cada<select id="autoEvery"><option value="10">10 s</option><option value="30">30 s</option><option value="60">1 min</option><option value="300">5 min</option></select></label>
<span class="muted" id="indicesAt"></span></div>
<pre id="indices" style="margin:0;overflow:auto;max-height:620px;font:12px/1.4 Consolas,monospace">…</pre></div>
</main>
<script>
const $=id=>document.getElementById(id);
const pad=n=>String(n).padStart(2,'0');
const toLocal=d=>`${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const fmtInt=v=>v==null||isNaN(v)?'–':Math.round(v).toLocaleString('pt-BR');
const when=ms=>ms?new Date(ms).toLocaleString('pt-BR'):'–';
const PALETTE=['#2563eb','#7c3aed','#db2777','#0d9488','#ca8a04','#ea580c','#16a34a','#0891b2','#be123c','#4f46e5','#64748b','#94a3b8'];
const OPERATIONS=['cria','atualiza','apaga','grava','bulk','última gravação'];
const OP_COLORS={'cria':'#16a34a','atualiza':'#2563eb','apaga':'#dc2626','grava':'#0d9488','bulk':'#7c3aed','última gravação':'#ca8a04'};
const SOURCES={versionable:'Versionable (jn_versionable): cada gravação',expurgable:'Expurgable (jn_disposable_record): última gravação de cada chave',logs:'Logs das chamadas ao ES (desde 05/11/2026)'};
const SOURCE_SHORT={versionable:'versionable',expurgable:'expurgable',logs:'logs'};
const STORE='painel35.selecao';
let data=null,entities=[],selected=null,ops=new Set(OPERATIONS);
try{const saved=JSON.parse(localStorage.getItem(STORE)||'null');if(saved){selected=new Set(saved.entities);ops=new Set(saved.ops);}}catch(e){}
function save(){try{localStorage.setItem(STORE,JSON.stringify({entities:[...selected],ops:[...ops]}));}catch(e){}}
function setRange(minutes){const end=new Date();$('end').value=toLocal(end);$('start').value=toLocal(new Date(end-minutes*60000));}
[['24 h',1440],['7 dias',10080],['30 dias',43200],['90 dias',129600],['1 ano',525600]].forEach(([t,m])=>{const b=document.createElement('button');b.type='button';b.className='ghost';b.textContent=t;b.onclick=()=>{setRange(m);run();};$('presets').appendChild(b);});
setRange(10080);
$('go').onclick=run;
function step(span){const steps=[60,300,900,1800,3600,10800,21600,43200,86400,604800].map(s=>s*1000);return steps.find(s=>span/s<=120)||604800000;}

function checks(){
  $('entities').innerHTML=Object.keys(SOURCES).map(source=>`<fieldset><legend>${SOURCES[source]}</legend>`+
    entities.filter(e=>e.source===source).map(e=>`<label title="${esc(e.className)} · grava: ${e.writer==='tela'?'a tela, na requisição':'o consumidor da fila'}${e.detail?' · '+esc(e.detail):''}"><input type="checkbox" data-entity="${e.entity}" ${selected.has(e.entity)?'checked':''}>${esc(e.entity)} <span class="muted">(${e.writer})</span></label>`).join('')+`</fieldset>`).join('');
  document.querySelectorAll('#entities input').forEach(box=>box.onchange=()=>{box.checked?selected.add(box.dataset.entity):selected.delete(box.dataset.entity);save();render();});
  $('operations').innerHTML=OPERATIONS.map(o=>`<label style="flex-direction:row;align-items:center;gap:5px;color:var(--fg);font-size:13px;cursor:pointer"><input type="checkbox" data-op="${o}" ${ops.has(o)?'checked':''}>${o}</label>`).join('');
  document.querySelectorAll('#operations input').forEach(box=>box.onchange=()=>{box.checked?ops.add(box.dataset.op):ops.delete(box.dataset.op);save();render();});
  $('count').textContent=`${selected.size} de ${entities.length} marcadas`;
}
const pick=filter=>{selected=new Set(entities.filter(filter).map(e=>e.entity));save();checks();render();};
$('all').onclick=()=>pick(()=>true);$('none').onclick=()=>pick(()=>false);$('screen').onclick=()=>pick(e=>e.writer==='tela');$('queue').onclick=()=>pick(e=>e.writer==='fila');

async function run(){
  const start=+new Date($('start').value),end=+new Date($('end').value),interval=step(end-start);
  const offset=((new Date().getTimezoneOffset()*60000)%interval+interval)%interval;
  $('out').innerHTML='<div class="card muted">Lendo jn_versionable e jn_disposable_record pelo túnel e os logs das chamadas ao ES…</div>';
  try{const r=await fetch('/api/writes?'+new URLSearchParams({start,end,interval,offset}));const d=await r.json();if(!r.ok)throw new Error(d.error);
    data={...d,start,end};entities=d.entities;if(!selected)selected=new Set(entities.map(e=>e.entity));checks();render();
  }catch(e){$('out').innerHTML=`<div class="card err">${esc(e.message)}</div>`;}
}

const charts={};
function lineChart(id,title,lines,note){
  const pts=lines.flatMap(l=>l.points);
  if(!pts.length||pts.every(p=>!p[1]))return `<div class="card"><h2>${title}</h2><div class="muted">nenhuma gravação no período</div></div>`;
  const W=600,H=200,L=50,R=8,T=8,B=22;const t0=data.start,t1=data.end;
  const peak=Math.max(...pts.map(p=>p[1]));const top=peak<4?4:peak*1.1;
  const x=t=>L+(t-t0)/((t1-t0)||1)*(W-L-R),y=v=>T+(1-v/top)*(H-T-B);
  let g='';for(let k=0;k<=4;k++){const v=top*k/4,yy=y(v);g+=`<line x1="${L}" x2="${W-R}" y1="${yy}" y2="${yy}" stroke="var(--grid)"/><text x="${L-6}" y="${yy+4}" text-anchor="end" font-size="10" fill="var(--muted)">${fmtInt(v)}</text>`;}
  const span=t1-t0;for(let k=0;k<=4;k++){const t=t0+span*k/4,d=new Date(t);const label=span>2*86400000?`${pad(d.getDate())}/${pad(d.getMonth()+1)}`:`${pad(d.getHours())}:${pad(d.getMinutes())}`;g+=`<text x="${x(t)}" y="${H-6}" text-anchor="middle" font-size="10" fill="var(--muted)">${label}</text>`;}
  const paths=lines.map(l=>`<polyline fill="none" stroke="${l.color}" stroke-width="1.8" points="${l.points.map(p=>x(p[0]).toFixed(1)+','+y(p[1]).toFixed(1)).join(' ')}"/>`).join('');
  charts[id]={lines,geom:{W,L,R,t0,t1}};
  return `<div class="card"><h2>${title}${note?` <span class="muted" style="font-weight:normal;font-size:12px">${note}</span>`:''}</h2><div class="chart" data-chart="${id}"><svg viewBox="0 0 ${W} ${H}">${g}${paths}<line class="cursor" x1="0" x2="0" y1="${T}" y2="${H-B}" stroke="var(--muted)" stroke-dasharray="3 3" visibility="hidden"/></svg><div class="tip"></div></div>`+
    `<div class="keys">${lines.map(l=>`<span><i style="background:${l.color}"></i>${esc(l.name)}</span>`).join('')}</div></div>`;
}
function wireCharts(){
  document.querySelectorAll('.chart').forEach(el=>{const c=charts[el.dataset.chart];if(!c)return;const svg=el.querySelector('svg'),tip=el.querySelector('.tip'),cur=svg.querySelector('.cursor');
    el.onmousemove=e=>{const r=svg.getBoundingClientRect(),vx=(e.clientX-r.left)/r.width*c.geom.W;const t=c.geom.t0+(vx-c.geom.L)/(c.geom.W-c.geom.L-c.geom.R)*(c.geom.t1-c.geom.t0);
      let rows='',at='';c.lines.forEach(l=>{let best=l.points[0];l.points.forEach(p=>{if(Math.abs(p[0]-t)<Math.abs(best[0]-t))best=p;});at=new Date(best[0]).toLocaleString('pt-BR');if(best[1])rows+=`<div><span style="color:${l.color}">●</span> ${esc(l.name)}: <b>${fmtInt(best[1])}</b></div>`;});
      tip.innerHTML=`<div class="muted">${at}</div>${rows||'<div class="muted">nenhuma gravação</div>'}`;tip.style.display='block';const px=e.clientX-r.left;tip.style.left=Math.max(0,Math.min(px+12,r.width-tip.offsetWidth-4))+'px';tip.style.top='10px';cur.setAttribute('x1',vx);cur.setAttribute('x2',vx);cur.setAttribute('visibility','visible');};
    el.onmouseleave=()=>{tip.style.display='none';cur.setAttribute('visibility','hidden');};});
}
function pie(title,items){
  items=items.filter(i=>i.value>0).sort((a,b)=>b.value-a.value);
  if(items.length>10){const rest=items.slice(9).reduce((a,b)=>a+b.value,0);items=items.slice(0,9).concat([{label:'outras',value:rest,color:'#94a3b8'}]);}
  items.forEach((it,i)=>it.color=it.color||PALETTE[i%PALETTE.length]);
  const total=items.reduce((a,b)=>a+b.value,0);let angle=-Math.PI/2;const r=80,c=90;let paths='';
  items.forEach(it=>{const a=it.value/total*2*Math.PI;
    if(a>=2*Math.PI-1e-9){paths+=`<circle cx="${c}" cy="${c}" r="${r}" fill="${it.color}"><title>${esc(it.label)}</title></circle>`;return;}
    const x1=c+r*Math.cos(angle),y1=c+r*Math.sin(angle);angle+=a;const x2=c+r*Math.cos(angle),y2=c+r*Math.sin(angle);
    paths+=`<path d="M${c},${c} L${x1},${y1} A${r},${r} 0 ${a>Math.PI?1:0} 1 ${x2},${y2} Z" fill="${it.color}" stroke="var(--card)" stroke-width="1.5"><title>${esc(it.label)}: ${fmtInt(it.value)} (${(it.value/total*100).toFixed(1)}%)</title></path>`;});
  const legend=items.map(i=>`<div><i style="background:${i.color}"></i>${esc(i.label)} — <b>${fmtInt(i.value)}</b> <span class="muted">(${(i.value/total*100).toFixed(1)}%)</span></div>`).join('');
  return `<div class="card"><h2>${title}</h2><div class="pie"><svg width="180" height="180" viewBox="0 0 180 180">${paths||'<circle cx="90" cy="90" r="80" fill="var(--line)"/>'}</svg><div class="legend">${legend||'<span class="muted">nenhuma gravação no período</span>'}</div></div></div>`;
}
const sumBy=(rows,key)=>{const m={};rows.forEach(r=>m[key(r)]=(m[key(r)]||0)+r.count);return Object.entries(m).map(([label,value])=>({label,value}));};
function series(rows,key,top,colors){
  const totals={};rows.forEach(r=>totals[key(r)]=(totals[key(r)]||0)+r.count);
  const keys=Object.keys(totals).sort((a,b)=>totals[b]-totals[a]);const shown=keys.slice(0,top),rest=keys.length>top;
  const grid=[];for(let t=Math.floor((data.start-data.offset)/data.interval)*data.interval+data.offset;t<=data.end;t+=data.interval)grid.push(t);
  const index=new Map(grid.map((t,i)=>[t,i]));const values={};[...shown,...(rest?['outras']:[])].forEach(k=>values[k]=grid.map(()=>0));
  rows.forEach(r=>{const i=index.get(r.bucket);if(i==null)return;const k=shown.includes(key(r))?key(r):'outras';values[k][i]+=r.count;});
  return Object.entries(values).map(([k,v],i)=>({name:k,color:k==='outras'?'#94a3b8':(colors&&colors[k])||PALETTE[i%PALETTE.length],points:grid.map((t,j)=>[t,v[j]])}));
}
let sort=['total',-1];
function render(){
  if(!data)return;
  const byName=Object.fromEntries(entities.map(e=>[e.entity,e]));
  const rows=data.rows.filter(r=>selected.has(r.entity)&&ops.has(r.operation));
  const total=rows.reduce((a,r)=>a+r.count,0),written=new Set(rows.map(r=>r.entity));
  const opCount=o=>rows.filter(r=>r.operation===o).reduce((a,r)=>a+r.count,0);
  const errors=Object.entries(data.errors).map(([s,m])=>`<div class="card err">Fonte ${esc(SOURCE_SHORT[s])}: ${esc(m)}</div>`).join('');
  const unit=data.interval>=86400000?(data.interval/86400000)+' dia(s)':data.interval>=3600000?(data.interval/3600000)+' h':(data.interval/60000)+' min';
  const tiles=[['Gravações',fmtInt(total)],['Entidades gravadas',`${written.size} de ${selected.size}`],['Cria',fmtInt(opCount('cria'))],['Atualiza',fmtInt(opCount('atualiza'))],['Apaga',fmtInt(opCount('apaga'))],
    ['Grava / bulk (logs)',fmtInt(opCount('grava')+opCount('bulk'))],['Última gravação (expurgable)',fmtInt(opCount('última gravação'))]];
  $('out').innerHTML=errors+`<div class="tiles">${tiles.map(([k,v])=>`<div class="tile"><span>${k}</span><b>${v}</b></div>`).join('')}</div>`+
    `<div class="muted" style="margin:-6px 0 12px"><b>Versionable</b>: cada gravação, até o expurgo do histórico. <b>Expurgable</b>: só a última gravação de cada chave (uma sessão gravada 5 vezes no período conta 1, na hora da última). <b>Logs</b>: chamadas de escrita ao ES desde 05/11/2026; um _bulk conta 1 por entidade que toca${data.logs.truncated?' (logs cortados no máximo: só os mais recentes)':''}; ${fmtInt(data.logs.units)} requisições e mensagens lidas.</div>`+
    `<div class="grid2">${lineChart('entity','Gravações por entidade',series(rows,r=>r.entity,8),'(por '+unit+')')}${lineChart('op','Gravações por operação',series(rows,r=>r.operation,6,OP_COLORS),'(por '+unit+')')}</div>`+
    `<div class="grid4">${pie('Por entidade',sumBy(rows,r=>r.entity))}${pie('Por operação',sumBy(rows,r=>r.operation).map(i=>({...i,color:OP_COLORS[i.label]})))}`+
    `${pie('Por quem grava',sumBy(rows,r=>byName[r.entity].writer==='tela'?'a tela (na requisição)':'o consumidor da fila'))}${pie('Por fonte do dado',sumBy(rows,r=>SOURCE_SHORT[byName[r.entity].source]))}</div>`+
    `<div class="card"><h2>Entidades marcadas <span class="muted" style="font-weight:normal">(as sem gravação no período ficam apagadas)</span></h2><div class="scroll" id="tbl"></div></div>`;
  wireCharts();table(rows);showIndices();
}
let indicesText='',indicesLoading=false,autoTimer=null;
async function loadIndices(){
  // sem limpar a lista: no auto atualizar ela so troca quando a nova chega
  if(indicesLoading)return;indicesLoading=true;$('indicesAt').textContent='lendo…';
  try{const r=await fetch('/api/indices');const t=await r.text();if(!r.ok)throw new Error(t);indicesText=t;showIndices();$('indicesAt').textContent='lida às '+new Date().toLocaleTimeString('pt-BR');}
  catch(e){$('indicesAt').innerHTML=`<span class="err">${esc(e.message)}</span>`;}
  finally{indicesLoading=false;}
}
function showIndices(){
  if(!indicesText||!selected)return;
  // o cabecalho e as linhas das entidades marcadas no filtro (a coluna index e a terceira), na ordem do _cat
  const lines=indicesText.split('\n').filter(Boolean),header=lines[0];
  const marked=lines.slice(1).filter(line=>selected&&selected.has(line.trim().split(/\s+/)[2]));
  $('indices').textContent=marked.length?[header,...marked].join('\n'):'Nenhuma entidade marcada no filtro.';
}
function setAuto(on){
  clearInterval(autoTimer);autoTimer=null;
  if(on)autoTimer=setInterval(loadIndices,+$('autoEvery').value*1000);
  $('autoIndices').textContent='Auto atualizar: '+(on?'ligado':'desligado');$('autoIndices').style.fontWeight=on?'700':'';
  try{localStorage.setItem('painel35.auto',JSON.stringify({on,every:$('autoEvery').value}));}catch(e){}
}
try{const auto=JSON.parse(localStorage.getItem('painel35.auto')||'null');if(auto){$('autoEvery').value=auto.every;if(auto.on)setAuto(true);}}catch(e){}
$('autoIndices').onclick=()=>setAuto(!autoTimer);
$('autoEvery').onchange=()=>setAuto(!!autoTimer);
$('reloadIndices').onclick=loadIndices;
loadIndices();
const COLS=[['entity','Entidade'],['className','Classe'],['writer','Quem grava'],['source','Fonte'],['total','Gravações',1],['cria','Cria',1],['atualiza','Atualiza',1],['apaga','Apaga',1],['grava','Grava',1],['bulk','Bulk',1],['ultima','Última gravação (chaves)',1],['last','Última no período',1],['detail','Observação']];
function table(rows){
  const list=entities.filter(e=>selected.has(e.entity)).map(e=>{const mine=rows.filter(r=>r.entity===e.entity),c=o=>mine.filter(r=>r.operation===o).reduce((a,r)=>a+r.count,0);
    return {...e,total:mine.reduce((a,r)=>a+r.count,0),cria:c('cria'),atualiza:c('atualiza'),apaga:c('apaga'),grava:c('grava'),bulk:c('bulk'),ultima:c('última gravação'),last:data.last[e.entity]||0};});
  const [key,dir]=sort;list.sort((a,b)=>(a[key]>b[key]?1:a[key]<b[key]?-1:0)*dir);
  $('tbl').innerHTML=list.length?`<table><thead><tr>${COLS.map(([k,t,n])=>`<th data-k="${k}" class="${n?'num':''}">${t}${k===key?(dir>0?' ▲':' ▼'):''}</th>`).join('')}</tr></thead><tbody>`+
    list.map(r=>`<tr class="${r.total?'':'zero'}"><td>${esc(r.entity)}</td><td>${esc(r.className)}</td><td>${r.writer==='tela'?'a tela':'a fila'}</td><td>${SOURCE_SHORT[r.source]}</td><td class="num"><b>${fmtInt(r.total)}</b></td>`+
      ['cria','atualiza','apaga','grava','bulk','ultima'].map(k=>`<td class="num">${r[k]?fmtInt(r[k]):'–'}</td>`).join('')+`<td class="num">${when(r.last)}</td><td class="muted">${esc(r.detail)}</td></tr>`).join('')+`</tbody></table>`
    :'<div class="muted">Marque ao menos uma entidade.</div>';
  document.querySelectorAll('#tbl th').forEach(th=>th.onclick=()=>{const k=th.dataset.k;sort=[k,k===sort[0]?-sort[1]:-1];table(rows);});
}
run();
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
    try:
        server.serve_forever()
    finally:
        close_tunnel()
