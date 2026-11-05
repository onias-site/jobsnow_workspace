# Painel local do Memorystore for Valkey (jobsnow-prd): escolhe a instancia e o periodo; mostra configuracao,
# acertos e falhas de leitura (taxa de acerto), comandos por tipo (chamadas, tempo total e medio, falhas), memoria,
# chaves (com e sem expiracao), CPU, clientes conectados, chaves expiradas e removidas por falta de memoria, rede e
# erros, em graficos de linha, pizzas e uma tabela por comando.
# Metricas pela API do Cloud Monitoring, com o token do gcloud do usuario. Cota da API: 180 requisicoes por minuto
# por usuario; cada busca faz 22, respostas iguais sao reaproveitadas por 1 minuto e o 429 espera e tenta de novo.
# Uso: python 30-cache-do-memorystore.py [porta]   (abre http://127.0.0.1:8768; atalho na area de trabalho)
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

PROJECT = "jobsnow-prd"
REGIONS = ["southamerica-east1"]
GCLOUD = os.path.join(os.environ["LOCALAPPDATA"], "Google", "Cloud SDK", "google-cloud-sdk", "bin", "gcloud.cmd")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8768
POINTS = 240
RESOURCE = "memorystore.googleapis.com/Instance"
CACHE_SECONDS = 60
token_lock = threading.Lock()
token_cache = {"value": "", "expires": 0.0}
cache_lock = threading.Lock()
response_cache = {}


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


def call(url):
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
        for old in [old for old, (moment, _) in response_cache.items() if time.time() - moment >= CACHE_SECONDS]:
            del response_cache[old]
        response_cache[url] = (time.time(), content)
    return content


def instances():
    result = []
    for region in REGIONS:
        listed = json.loads(gcloud("memorystore", "instances", "list", "--location", region, "--project", PROJECT, "--format=json"))
        for item in listed:
            connections = [connection.get("pscAutoConnection", {}) for endpoint in item.get("endpoints", [])
                           for connection in endpoint.get("connections", [])]
            addresses = ["%s %s:%s" % (connection.get("connectionType", "").replace("CONNECTION_TYPE_", "").lower(),
                                       connection.get("ipAddress", ""), connection.get("port", "")) for connection in connections]
            result.append({
                "id": item["name"].rsplit("/", 1)[-1], "location": region, "state": item.get("state", ""),
                "engine": item.get("engineVersion", ""), "nodeType": item.get("nodeType", ""),
                "sizeGb": item.get("nodeConfig", {}).get("sizeGb", 0), "mode": item.get("mode", ""),
                "shards": item.get("shardCount", 1), "replicas": item.get("replicaCount", 0),
                "auth": item.get("authorizationMode", ""), "tls": item.get("transitEncryptionMode", ""),
                "persistence": item.get("persistenceConfig", {}).get("mode", ""),
                "backup": item.get("automatedBackupConfig", {}).get("automatedBackupMode", ""),
                "created": item.get("createTime", ""), "addresses": addresses,
                "deletionProtection": item.get("deletionProtectionEnabled", False),
            })
    return result


def value_of(point):
    value = point["value"]
    if "doubleValue" in value:
        return float(value["doubleValue"])
    if "boolValue" in value:
        return 1.0 if value["boolValue"] else 0.0
    return float(value.get("int64Value", 0))


def series(metric, aligner, reducer, group_by, instance, start, end, period):
    params = [
        # as metricas node/* sao do recurso InstanceNode (uma serie por no); as demais, do Instance
        ("filter", 'metric.type="memorystore.googleapis.com/instance/%s" resource.type="%s" resource.labels.instance_id="%s"'
         % (metric, RESOURCE + "Node" if metric.startswith("node/") else RESOURCE, instance)),
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
            points = [[point["interval"]["endTime"], value_of(point)] for point in reversed(item.get("points", []))]
            result.append({"labels": labels, "points": points})
        token = page.get("nextPageToken", "")
        if not token:
            return result


def seconds_between(start, end):
    return (datetime.fromisoformat(end.replace("Z", "+00:00")) - datetime.fromisoformat(start.replace("Z", "+00:00"))).total_seconds()


def metrics(instance, start, end):
    span = seconds_between(start, end)
    period = max(60, int(span / POINTS) // 60 * 60)
    whole = max(60, int(span + 59) // 60 * 60)
    by_command = ["metric.label.command"]
    timeline = {
        "hits": ("stats/total_keyspace_hits_count", "ALIGN_DELTA", "REDUCE_SUM", []),
        "misses": ("stats/total_keyspace_misses_count", "ALIGN_DELTA", "REDUCE_SUM", []),
        "calls": ("commandstats/total_calls_count", "ALIGN_DELTA", "REDUCE_SUM", []),
        "memoryPercent": ("memory/maximum_utilization", "ALIGN_MAX", "REDUCE_MAX", []),
        "memoryUsed": ("memory/total_used_memory", "ALIGN_MAX", "REDUCE_SUM", []),
        "memorySize": ("memory/size", "ALIGN_MAX", "REDUCE_SUM", []),
        "keys": ("keyspace/total_keys", "ALIGN_MAX", "REDUCE_SUM", []),
        "keysWithTtl": ("node/keyspace/keys_with_expiration", "ALIGN_MAX", "REDUCE_SUM", []),
        "cpu": ("cpu/maximum_utilization", "ALIGN_MAX", "REDUCE_MAX", []),
        "clients": ("clients/total_connected_clients", "ALIGN_MAX", "REDUCE_SUM", []),
        "evicted": ("stats/total_evicted_keys_count", "ALIGN_DELTA", "REDUCE_SUM", []),
        "expired": ("stats/total_expired_keys_count", "ALIGN_DELTA", "REDUCE_SUM", []),
        "netIn": ("stats/total_net_input_bytes_count", "ALIGN_DELTA", "REDUCE_SUM", []),
        "netOut": ("stats/total_net_output_bytes_count", "ALIGN_DELTA", "REDUCE_SUM", []),
    }
    totals = {
        "callsByCommand": ("commandstats/total_calls_count", "ALIGN_DELTA", "REDUCE_SUM", by_command),
        "usecByCommand": ("commandstats/total_usec_count", "ALIGN_DELTA", "REDUCE_SUM", by_command),
        "failedByCommand": ("node/commandstats/failed_calls_count", "ALIGN_DELTA", "REDUCE_SUM", by_command),
        "rejectedByCommand": ("node/commandstats/rejected_calls_count", "ALIGN_DELTA", "REDUCE_SUM", by_command),
        "errorsByType": ("node/errorstats/errors_count", "ALIGN_DELTA", "REDUCE_SUM", ["metric.label.error_type"]),
        "rejectedConnections": ("stats/total_rejected_connections_count", "ALIGN_DELTA", "REDUCE_SUM", []),
        "policy": ("node/memory/maxmemory_policy", "ALIGN_MAX", "REDUCE_MAX", ["metric.label.maxmemory_policy"]),
        "healthy": ("node/server/healthy", "ALIGN_NEXT_OLDER", "REDUCE_COUNT_FALSE", []),
    }
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {("timeline", key): pool.submit(series, *spec, instance, start, end, period) for key, spec in timeline.items()}
        futures.update({("totals", key): pool.submit(series, *spec, instance, start, end, whole) for key, spec in totals.items()})
        found = {key: future.result() for key, future in futures.items()}
    result = {"period": period, "timeline": {}, "totals": {}}
    for key in timeline:
        items = found[("timeline", key)]
        result["timeline"][key] = items[0]["points"] if items else []
    for key, spec in totals.items():
        label = spec[3][0].rsplit(".", 1)[-1] if spec[3] else ""
        result["totals"][key] = {(item["labels"].get(label, "?") if label else "total"): sum(value for _, value in item["points"])
                                 for item in found[("totals", key)]}
    # contagem sem comando no intervalo nao vem como ponto: preenche com zero na grade dos medidores (sempre presentes)
    grid = [moment for moment, _ in result["timeline"]["keys"]]
    for key in ("hits", "misses", "calls", "evicted", "expired", "netIn", "netOut"):
        known = dict(result["timeline"][key])
        result["timeline"][key] = [[moment, known.get(moment, 0)] for moment in grid] if grid else result["timeline"][key]
    return result


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
            if parsed.path == "/api/instances":
                return self.send_json(200, instances())
            if parsed.path == "/api/metrics":
                return self.send_json(200, metrics(query["instance"], query["start"], query["end"]))
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
<title>Cache do Memorystore</title>
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
.chip input{margin:0}
.facts{display:flex;gap:8px 18px;flex-wrap:wrap;font-size:13px}.facts b{font-weight:600}
.badge{display:inline-block;padding:1px 8px;border-radius:99px;font-size:12px;font-weight:700;color:#fff}
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
h2{font-size:15px;margin:0 0 10px}
table{width:100%;border-collapse:collapse;font-size:12.5px}th,td{padding:5px 7px;border-bottom:1px solid var(--line);text-align:left}
th{color:var(--muted);position:sticky;top:0;background:var(--card);cursor:pointer}td.num,th.num{text-align:right;white-space:nowrap}
.scroll{max-height:520px;overflow:auto}.muted{color:var(--muted)}.err{color:#d92d20;white-space:pre-wrap}.bad{color:#dc2626;font-weight:700}
</style></head><body>
<header><h1>Cache do Memorystore · __PROJECT__</h1></header>
<main>
<div class="card"><form id="f">
<label>Instância<select id="instance"></select></label>
<label>De<input type="datetime-local" id="start"></label>
<label>Até<input type="datetime-local" id="end"></label>
<button type="submit">Buscar</button>
<div class="row"><span class="muted">Período:</span><span id="presets" style="display:contents"></span>
<label class="chip" style="margin-left:auto"><input type="checkbox" id="auto">atualizar a cada minuto (últimos dados)</label></div>
</form></div>
<div id="info"></div>
<div id="out"></div>
</main>
<script>
const $=id=>document.getElementById(id);
const pad=n=>String(n).padStart(2,'0');
const toLocal=d=>`${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
let rangeMinutes=1440,instances=[],tableSort=['calls',-1],lastData=null;
function setRange(minutes){rangeMinutes=minutes;const end=new Date();$('end').value=toLocal(end);$('start').value=toLocal(new Date(end-minutes*60000));}
[['1 h',60],['6 h',360],['24 h',1440],['7 dias',10080],['30 dias',43200],['6 semanas',60480]].forEach(([t,m])=>{const b=document.createElement('button');b.type='button';b.className='ghost';b.textContent=t;b.onclick=()=>{setRange(m);run();};$('presets').appendChild(b);});
const params=new URLSearchParams(location.search);
setRange(+(params.get('minutes')||1440));
$('f').onsubmit=e=>{e.preventDefault();rangeMinutes=null;run();};
$('instance').onchange=()=>run();
let timer=null;$('auto').onchange=()=>{clearInterval(timer);if($('auto').checked)timer=setInterval(()=>{setRange(rangeMinutes||1440);run(true);},60000);};
fetch('/api/instances').then(async r=>{const d=await r.json();if(!r.ok)throw new Error(d.error);return d;}).then(list=>{instances=list;list.forEach(i=>{const o=document.createElement('option');o.value=i.id;o.textContent=i.id+' ('+i.location+')';$('instance').appendChild(o);});
  if(params.get('instance'))$('instance').value=params.get('instance');run();}).catch(e=>{$('out').innerHTML=`<div class="card err">${esc(e.message)}</div>`;});

const fmtInt=v=>v==null||isNaN(v)?'–':Math.round(v).toLocaleString('pt-BR');
const fmtPct=v=>v==null||isNaN(v)?'–':(v<10?v.toFixed(1):v.toFixed(0))+'%';
const fmtBytes=v=>{if(v==null||isNaN(v))return'–';const u=['B','KB','MB','GB','TB'];let i=0;while(Math.abs(v)>=1024&&i<4){v/=1024;i++;}return v.toFixed(v<10&&i?1:0)+' '+u[i];};
const fmtUs=v=>v==null||isNaN(v)?'–':v>=1e6?(v/1e6).toFixed(2)+' s':v>=1000?(v/1000).toFixed(v>=1e4?0:1)+' ms':v.toFixed(v<10?1:0)+' µs';
const last=pts=>pts&&pts.length?pts[pts.length-1][1]:NaN;
const maxOf=pts=>pts&&pts.length?Math.max(...pts.map(p=>p[1])):NaN;
const sumOf=pts=>(pts||[]).reduce((a,p)=>a+p[1],0);
const sum=obj=>Object.values(obj||{}).reduce((a,b)=>a+b,0);
const PALETTE=['#2563eb','#7c3aed','#db2777','#0d9488','#ca8a04','#ea580c','#16a34a','#0891b2','#be123c','#4f46e5','#64748b','#94a3b8'];

const charts={};
function lineChart(id,title,lines,fmt,maxY,note){
  lines=lines.filter(l=>l.points&&l.points.length);const all=lines.flatMap(l=>l.points);
  if(!all.length)return `<div class="card"><h2>${title}</h2><div class="muted">sem dados no período</div></div>`;
  const W=600,H=190,L=60,R=8,T=8,B=22;
  const times=all.map(p=>+new Date(p[0])),t0=Math.min(...times),t1=Math.max(...times);
  // contagens (inteiras) abaixo de 4: as 5 marcas cairiam em fracoes e o formato inteiro repetiria rotulos (0 0 1 1 1)
  const peak=Math.max(...all.map(p=>p[1])),integers=all.every(p=>Number.isInteger(p[1]));
  const top=maxY??(integers&&peak<4?4:(peak*1.1)||1);
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
function pie(title,items,fmt){
  items=items.filter(i=>i.value>0).sort((a,b)=>b.value-a.value);
  if(items.length>9){const rest=items.slice(8).reduce((a,b)=>a+b.value,0);items=items.slice(0,8).concat([{label:'outros',value:rest,color:'#cbd5e1'}]);}
  items.forEach((it,i)=>it.color=it.color||PALETTE[i%PALETTE.length]);
  fmt=fmt||fmtInt;const total=items.reduce((a,b)=>a+b.value,0);let angle=-Math.PI/2;const r=80,c=90;let paths='';
  items.forEach(it=>{const a=it.value/total*2*Math.PI;
    if(a>=2*Math.PI-1e-9){paths+=`<circle cx="${c}" cy="${c}" r="${r}" fill="${it.color}"><title>${esc(it.label)}</title></circle>`;return;}
    const x1=c+r*Math.cos(angle),y1=c+r*Math.sin(angle);angle+=a;const x2=c+r*Math.cos(angle),y2=c+r*Math.sin(angle);
    paths+=`<path d="M${c},${c} L${x1},${y1} A${r},${r} 0 ${a>Math.PI?1:0} 1 ${x2},${y2} Z" fill="${it.color}" stroke="var(--card)" stroke-width="1.5"><title>${esc(it.label)}: ${fmt(it.value)} (${(it.value/total*100).toFixed(1)}%)</title></path>`;});
  const legend=items.map(i=>`<div><i style="background:${i.color}"></i>${esc(i.label)} — <b>${fmt(i.value)}</b> <span class="muted">(${(i.value/total*100).toFixed(1)}%)</span></div>`).join('');
  return `<div class="card"><h2>${title}</h2><div class="pie"><svg width="180" height="180" viewBox="0 0 180 180">${paths||'<circle cx="90" cy="90" r="80" fill="var(--line)"/>'}</svg><div class="legend">${legend||'<span class="muted">sem dados no período</span>'}</div></div></div>`;
}

async function run(quiet){
  const inst=instances.find(i=>i.id===$('instance').value);if(!inst)return;
  const start=new Date($('start').value).toISOString(),end=new Date($('end').value).toISOString();
  history.replaceState(null,'','?'+new URLSearchParams({instance:inst.id,...(rangeMinutes?{minutes:rangeMinutes}:{})}));
  renderInfo(inst);
  if(!quiet)$('out').innerHTML='<div class="card muted">Lendo as métricas do Cloud Monitoring…</div>';
  try{
    const r=await fetch('/api/metrics?'+new URLSearchParams({instance:inst.id,start,end}));const d=await r.json();if(!r.ok)throw new Error(d.error);
    lastData=d;render(d,inst);
  }catch(e){$('out').innerHTML=`<div class="card err">${esc(e.message)}</div>`;}
}
function renderInfo(i){
  const color={ACTIVE:'#16a34a',CREATING:'#d97706',UPDATING:'#d97706',DELETING:'#dc2626'}[i.state]||'#64748b';
  $('info').innerHTML=`<div class="card"><div class="facts"><span><span class="badge" style="background:${color}">${esc(i.state)}</span></span>`+
    `<span>Motor <b>${esc(i.engine)}</b></span><span>Nó <b>${esc(i.nodeType)}</b> · <b>${i.sizeGb} GB</b></span><span>Modo <b>${esc(i.mode)}</b></span>`+
    `<span>Shards <b>${i.shards}</b> · réplicas <b>${i.replicas}</b></span><span>Endereços <b>${esc(i.addresses.join(', ')||'–')}</b></span>`+
    `<span>Autenticação <b>${esc(i.auth)}</b></span><span>TLS <b>${esc(i.tls||'–')}</b></span><span>Persistência <b>${esc(i.persistence)}</b></span>`+
    `<span>Backup automático <b>${esc(i.backup)}</b></span><span>Proteção contra exclusão <b>${i.deletionProtection?'sim':'não'}</b></span>`+
    `<span>Criada <b>${new Date(i.created).toLocaleString('pt-BR')}</b></span><span id="policy"></span></div></div>`;
}

function render(d,inst){
  const t=d.timeline,s=d.totals;
  const hits=sumOf(t.hits),misses=sumOf(t.misses),reads=hits+misses,ratio=reads?hits/reads*100:NaN;
  const calls=sum(s.callsByCommand),failed=sum(s.failedByCommand),rejected=sum(s.rejectedByCommand),errors=sum(s.errorsByType);
  const evicted=sumOf(t.evicted),expired=sumOf(t.expired);
  const policy=Object.keys(s.policy||{})[0];if(policy)$('policy').innerHTML=`Política de despejo <b>${esc(policy)}</b>`;
  const unhealthy=(s.healthy||{}).total||0;
  const memPct=t.memoryPercent.map(p=>[p[0],p[1]*100]),cpu=t.cpu.map(p=>[p[0],p[1]*100]);
  const tiles=[['Taxa de acerto',fmtPct(ratio),reads&&ratio<50],['Acertos',fmtInt(hits)],['Falhas de leitura',fmtInt(misses)],['Comandos',fmtInt(calls)],
    ['Chaves agora',fmtInt(last(t.keys))],['Com expiração',fmtInt(last(t.keysWithTtl))],['Memória agora',fmtPct(last(memPct)),last(memPct)>80],['Memória máx',fmtPct(maxOf(memPct)),maxOf(memPct)>90],
    ['Usada',fmtBytes(last(t.memoryUsed))+' de '+fmtBytes(last(t.memorySize))],['CPU máx',fmtPct(maxOf(cpu)),maxOf(cpu)>80],['Clientes agora',fmtInt(last(t.clients))],['Clientes máx',fmtInt(maxOf(t.clients))],
    ['Removidas por memória',fmtInt(evicted),evicted>0],['Expiradas',fmtInt(expired)],['Comandos com falha',fmtInt(failed+rejected),failed+rejected>0],['Erros',fmtInt(errors),errors>0],
    ['Conexões recusadas',fmtInt(sum(s.rejectedConnections)),sum(s.rejectedConnections)>0],['Nó fora do ar',unhealthy?'sim':'não',unhealthy>0]];
  const ratioLine=t.hits.map((p,i)=>{const m=(t.misses[i]||[0,0])[1];const all=p[1]+m;return all?[p[0],p[1]/all*100]:null;}).filter(Boolean);
  const minutes=d.period/60,unit=minutes>=60?(minutes/60)+' h':minutes+' min';
  const usec=s.usecByCommand||{},callsBy=s.callsByCommand||{};
  $('out').innerHTML=
    `<div class="tiles">${tiles.map(([k,v,alert])=>`<div class="tile${alert?' alert':''}"><span>${k}</span><b>${v}</b></div>`).join('')}</div>`+
    `<div class="muted" style="margin:-6px 0 12px">Cada ponto dos gráficos cobre ${unit}; os totais acima cobrem o período inteiro.</div>`+
    `<div class="grid2">${lineChart('reads','Leituras: acertos × falhas',[{name:'acertos',points:t.hits,color:'#16a34a'},{name:'falhas',points:t.misses,color:'#dc2626'}],fmtInt,null,'(por '+unit+')')}`+
    `${lineChart('ratio','Taxa de acerto',[{name:'taxa de acerto',points:ratioLine,color:'#2563eb'}],fmtPct,100,'(só intervalos com leitura)')}`+
    `${lineChart('calls','Comandos',[{name:'comandos',points:t.calls,color:'#7c3aed'}],fmtInt,null,'(por '+unit+')')}`+
    `${lineChart('memory','Memória usada',[{name:'memória',points:memPct,color:'#7c3aed'}],fmtPct,100)}`+
    `${lineChart('keys','Chaves',[{name:'total',points:t.keys,color:'#2563eb'},{name:'com expiração',points:t.keysWithTtl,color:'#0d9488'}],fmtInt)}`+
    `${lineChart('cpu','CPU',[{name:'CPU',points:cpu,color:'#ea580c'}],fmtPct,100)}`+
    `${lineChart('clients','Clientes conectados',[{name:'clientes',points:t.clients,color:'#0891b2'}],fmtInt)}`+
    `${lineChart('gone','Chaves expiradas e removidas por memória',[{name:'expiradas',points:t.expired,color:'#0d9488'},{name:'removidas por memória',points:t.evicted,color:'#dc2626'}],fmtInt,null,'(por '+unit+')')}`+
    `${lineChart('net','Rede',[{name:'recebido',points:t.netIn,color:'#2563eb'},{name:'enviado',points:t.netOut,color:'#db2777'}],fmtBytes,null,'(por '+unit+')')}</div>`+
    `<div class="grid3">${pie('Leituras',[{label:'acertos',value:hits,color:'#16a34a'},{label:'falhas (chave ausente)',value:misses,color:'#dc2626'}])}`+
    `${pie('Comandos por tipo',Object.entries(callsBy).map(([k,v])=>({label:k,value:v})))}`+
    `${pie('Tempo gasto por comando',Object.entries(usec).map(([k,v])=>({label:k,value:v})),fmtUs)}`+
    `${pie('Memória',[{label:'usada',value:last(t.memoryUsed)||0,color:'#7c3aed'},{label:'livre',value:Math.max(0,(last(t.memorySize)||0)-(last(t.memoryUsed)||0)),color:'#e2e8f0'}],fmtBytes)}`+
    `${pie('Chaves',[{label:'com expiração',value:last(t.keysWithTtl)||0,color:'#0d9488'},{label:'sem expiração',value:Math.max(0,(last(t.keys)||0)-(last(t.keysWithTtl)||0)),color:'#f59e0b'}])}`+
    `${pie('Erros por tipo',Object.entries(s.errorsByType||{}).map(([k,v])=>({label:k,value:v})))}</div>`+
    `<div class="card"><h2>Comandos <span class="muted" style="font-weight:normal">(tempo medido dentro do Valkey, sem a rede)</span></h2><div class="scroll" id="tbl"></div></div>`;
  wireCharts();table(d);
}
const COLS=[['command','Comando'],['calls','Chamadas',1],['share','% das chamadas',1],['usec','Tempo total',1],['mean','Tempo médio',1],['failed','Com falha',1],['rejected','Recusados',1]];
function table(d){
  const s=d.totals,calls=s.callsByCommand||{},total=sum(calls);
  const names=new Set([...Object.keys(calls),...Object.keys(s.failedByCommand||{}),...Object.keys(s.rejectedByCommand||{})]);
  const rows=[...names].map(n=>({command:n,calls:calls[n]||0,share:total?(calls[n]||0)/total*100:0,usec:(s.usecByCommand||{})[n]||0,
    mean:calls[n]?((s.usecByCommand||{})[n]||0)/calls[n]:NaN,failed:(s.failedByCommand||{})[n]||0,rejected:(s.rejectedByCommand||{})[n]||0})).filter(r=>r.calls||r.failed||r.rejected);
  const [key,dir]=tableSort;rows.sort((a,b)=>((isNaN(a[key])?-1:a[key])>(isNaN(b[key])?-1:b[key])?1:(isNaN(a[key])?-1:a[key])<(isNaN(b[key])?-1:b[key])?-1:0)*dir);
  $('tbl').innerHTML=rows.length?`<table><thead><tr>${COLS.map(([k,t,n])=>`<th data-k="${k}" class="${n?'num':''}">${t}${k===key?(dir>0?' ▲':' ▼'):''}</th>`).join('')}</tr></thead><tbody>`+
    rows.map(r=>`<tr><td>${esc(r.command)}</td><td class="num">${fmtInt(r.calls)}</td><td class="num">${fmtPct(r.share)}</td><td class="num">${fmtUs(r.usec)}</td><td class="num">${fmtUs(r.mean)}</td>`+
      `<td class="num ${r.failed?'bad':''}">${fmtInt(r.failed)}</td><td class="num ${r.rejected?'bad':''}">${fmtInt(r.rejected)}</td></tr>`).join('')+`</tbody></table>`:'<div class="muted">nenhum comando no período</div>';
  document.querySelectorAll('#tbl th').forEach(th=>th.onclick=()=>{const k=th.dataset.k;tableSort=[k,k===tableSort[0]?-tableSort[1]:-1];table(lastData);});
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
