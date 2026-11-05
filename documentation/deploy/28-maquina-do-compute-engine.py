# Painel local de uma maquina do Compute Engine (jobsnow-prd): escolhe a instancia e o periodo; mostra situacao,
# CPU, memoria, disco, carga, rede e E/S de disco em graficos de linha, pizzas do tempo por faixa de uso de CPU e de
# memoria, memoria por processo, tabela de processos (memoria e CPU) e os logs da maquina (Ops Agent: elasticsearch,
# consumidores, syslog) com pizza por nivel e por origem e filtro de nivel, origem e texto.
# Metricas pela API do Cloud Monitoring e logs pela API do Cloud Logging, com o token do gcloud do usuario.
# Memoria, disco, carga e processos dependem do Ops Agent na VM (23-ops-agent-na-vm.sh); CPU, rede e E/S nao.
# Uso: python 28-maquina-do-compute-engine.py [porta]   (abre http://127.0.0.1:8766; atalho na area de trabalho)
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
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PROJECT = "jobsnow-prd"
GCLOUD = os.path.join(os.environ["LOCALAPPDATA"], "Google", "Cloud SDK", "google-cloud-sdk", "bin", "gcloud.cmd")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8766
POINTS = 240
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


def call(url, body=None):
    # cota das APIs do Monitoring e do Logging por usuario e minuto: resposta igual reaproveitada por 1 minuto
    # (atualizacao automatica, abas repetidas) e, no 429, espera e tenta de novo.
    data = json.dumps(body).encode() if body is not None else None
    key = url + (data.decode() if data else "")
    with cache_lock:
        cached = response_cache.get(key)
        if cached and time.time() - cached[0] < CACHE_SECONDS:
            return cached[1]
    # token revogado antes dos 45 min (novo login do gcloud): descarta, pede outro e tenta de novo
    renewed = False
    for wait in (5, 15, 30, 0):
        request = urllib.request.Request(url, data=data, method="POST" if body is not None else "GET")
        request.add_header("Authorization", "Bearer " + access_token())
        request.add_header("Content-Type", "application/json")
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
        response_cache[key] = (time.time(), content)
    return content


def instances():
    listed = json.loads(gcloud("compute", "instances", "list", "--project", PROJECT, "--format=json"))
    result = []
    for instance in listed:
        interfaces = instance.get("networkInterfaces", [{}])
        access = interfaces[0].get("accessConfigs", [{}]) if interfaces else [{}]
        result.append({
            "id": instance["id"], "name": instance["name"], "zone": instance["zone"].rsplit("/", 1)[-1],
            "machineType": instance["machineType"].rsplit("/", 1)[-1], "status": instance["status"],
            "internalIp": interfaces[0].get("networkIP", "") if interfaces else "",
            "externalIp": access[0].get("natIP", "") if access else "",
            "created": instance.get("creationTimestamp", ""), "lastStart": instance.get("lastStartTimestamp", ""),
            "disks": [disk.get("deviceName", "") + " " + str(disk.get("diskSizeGb", "")) + " GB" for disk in instance.get("disks", [])],
        })
    return result


def alignment(start, end):
    seconds = (datetime.fromisoformat(end.replace("Z", "+00:00")) - datetime.fromisoformat(start.replace("Z", "+00:00"))).total_seconds()
    return max(60, int(seconds / POINTS) // 60 * 60)


def value_of(point):
    value = point["value"]
    if "doubleValue" in value:
        return float(value["doubleValue"])
    return float(value.get("int64Value", 0))


def series(instance_id, metric, start, end, period, aligner, extra="", group_by=None, reducer="REDUCE_SUM"):
    params = [
        ("filter", 'metric.type="%s" resource.type="gce_instance" resource.labels.instance_id="%s"%s' % (metric, instance_id, extra)),
        ("interval.startTime", start), ("interval.endTime", end),
        ("aggregation.alignmentPeriod", "%ds" % period), ("aggregation.perSeriesAligner", aligner),
    ]
    if group_by is not None:
        params.append(("aggregation.crossSeriesReducer", reducer))
        params.extend(("aggregation.groupByFields", field) for field in group_by)
    result = []
    token = ""
    while True:
        query = params + ([("pageToken", token)] if token else [])
        page = call("https://monitoring.googleapis.com/v3/projects/%s/timeSeries?%s" % (PROJECT, urllib.parse.urlencode(query)))
        for item in page.get("timeSeries", []):
            points = [[point["interval"]["endTime"], value_of(point)] for point in reversed(item.get("points", []))]
            result.append({"labels": item.get("metric", {}).get("labels", {}), "points": points})
        token = page.get("nextPageToken", "")
        if not token:
            return result


def single(found):
    return found[0]["points"] if found else []


def process_name(labels):
    command = labels.get("command", "")
    line = labels.get("command_line", "")
    if "org.elasticsearch" in line:
        return "elasticsearch"
    jar = re.search(r"-jar\s+(\S+)", line)
    if jar:
        return os.path.basename(jar.group(1))
    if command.startswith("PM2"):
        return "PM2"
    return command or "?"


def processes(instance_id, start, end, period):
    grouping = ["metric.label.command", "metric.label.command_line"]
    memory = series(instance_id, "agent.googleapis.com/processes/rss_usage", start, end, period, "ALIGN_MEAN", group_by=grouping)
    cpu = series(instance_id, "agent.googleapis.com/processes/cpu_time", start, end, period, "ALIGN_RATE", group_by=grouping)
    table = {}
    for item in memory:
        name = process_name(item["labels"])
        row = table.setdefault(name, {"name": name, "rss": {}, "cpu": {}})
        for moment, value in item["points"]:
            row["rss"][moment] = row["rss"].get(moment, 0) + value
    for item in cpu:
        name = process_name(item["labels"])
        row = table.setdefault(name, {"name": name, "rss": {}, "cpu": {}})
        for moment, value in item["points"]:
            row["cpu"][moment] = row["cpu"].get(moment, 0) + value / 1e6 * 100
    result = []
    for row in table.values():
        rss = [row["rss"][moment] for moment in sorted(row["rss"])]
        cpu_values = list(row["cpu"].values())
        result.append({
            "name": row["name"], "rssNow": rss[-1] if rss else 0, "rssMax": max(rss) if rss else 0,
            "cpuMean": sum(cpu_values) / len(cpu_values) if cpu_values else 0, "cpuMax": max(cpu_values) if cpu_values else 0,
        })
    result.sort(key=lambda row: -row["rssNow"])
    return result


def metrics(instance_id, start, end):
    period = alignment(start, end)
    used = ' metric.labels.state="used"'
    queries = {
        "cpu": ("compute.googleapis.com/instance/cpu/utilization", "ALIGN_MEAN", "", None),
        "memory": ("agent.googleapis.com/memory/percent_used", "ALIGN_MEAN", used, None),
        "memoryStates": ("agent.googleapis.com/memory/bytes_used", "ALIGN_MEAN", "", ["metric.label.state"]),
        "disks": ("agent.googleapis.com/disk/percent_used", "ALIGN_MEAN", used, None),
        "load": ("agent.googleapis.com/cpu/load_1m", "ALIGN_MEAN", "", None),
        "networkIn": ("compute.googleapis.com/instance/network/received_bytes_count", "ALIGN_RATE", "", []),
        "networkOut": ("compute.googleapis.com/instance/network/sent_bytes_count", "ALIGN_RATE", "", []),
        "diskRead": ("compute.googleapis.com/instance/disk/read_bytes_count", "ALIGN_RATE", "", []),
        "diskWrite": ("compute.googleapis.com/instance/disk/write_bytes_count", "ALIGN_RATE", "", []),
        "uptime": ("compute.googleapis.com/instance/uptime_total", "ALIGN_MAX", "", None),
    }
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {key: pool.submit(series, instance_id, metric, start, end, period, aligner, extra, group_by)
                   for key, (metric, aligner, extra, group_by) in queries.items()}
        process_rows = pool.submit(processes, instance_id, start, end, period)
        found = {key: future.result() for key, future in futures.items()}
    result = {key: single(found[key]) for key in queries if key not in ("memoryStates", "disks")}
    result["period"] = period
    result["memoryStates"] = {item["labels"].get("state", "?"): (item["points"][-1][1] if item["points"] else 0)
                              for item in found["memoryStates"]}
    result["disks"] = [{"device": item["labels"].get("device", "?"), "points": item["points"]} for item in found["disks"]
                       if not item["labels"].get("device", "").startswith("/dev/loop")]
    result["processes"] = process_rows.result()
    return result


LEVELS = [
    (re.compile(r"\]\[(TRACE|DEBUG|INFO|WARN|ERROR|FATAL)\s*\]"), None),
    (re.compile(r"^(SEVERE|WARNING|INFO|CONFIG|FINE|FINER|FINEST):", re.M), None),
    (re.compile(r"\b(FATAL|CRITICAL|ERROR|SEVERE|WARN|WARNING|INFO|DEBUG|TRACE)\b"), None),
]
LEVEL_NAMES = {"SEVERE": "ERROR", "CRITICAL": "FATAL", "WARNING": "WARN", "CONFIG": "INFO", "FINE": "DEBUG",
               "FINER": "TRACE", "FINEST": "TRACE"}


def level_of(entry, message):
    severity = entry.get("severity", "")
    if severity and severity != "DEFAULT":
        return LEVEL_NAMES.get(severity, severity)
    for pattern, _ in LEVELS:
        found = pattern.search(message[:400])
        if found:
            return LEVEL_NAMES.get(found.group(1), found.group(1))
    return "SEM NÍVEL"


def logs(instance_id, start, end, maximum):
    body = {
        "resourceNames": ["projects/" + PROJECT],
        "filter": 'resource.type="gce_instance" AND resource.labels.instance_id="%s" AND timestamp>="%s" AND timestamp<"%s"' % (instance_id, start, end),
        "orderBy": "timestamp desc", "pageSize": min(1000, maximum),
    }
    entries = []
    truncated = False
    while True:
        page = call("https://logging.googleapis.com/v2/entries:list", body)
        entries.extend(page.get("entries", []))
        if not page.get("nextPageToken"):
            break
        if len(entries) >= maximum:
            truncated = True
            break
        body["pageToken"] = page["nextPageToken"]
    result = []
    for entry in entries[:maximum]:
        payload = entry.get("jsonPayload") or {}
        message = entry.get("textPayload") or payload.get("message") or json.dumps(payload, ensure_ascii=False)
        result.append({
            "timestamp": entry.get("timestamp", ""), "source": urllib.parse.unquote(entry.get("logName", "").rsplit("/", 1)[-1]),
            "level": level_of(entry, message), "message": message,
        })
    return {"truncated": truncated, "entries": result}


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
            if parsed.path == "/api/logs":
                return self.send_json(200, logs(query["instance"], query["start"], query["end"], int(query.get("max", "5000"))))
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
<title>Máquina do Compute Engine</title>
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
.facts{display:flex;gap:18px;flex-wrap:wrap;font-size:13px}.facts b{font-weight:600}
.badge{display:inline-block;padding:1px 8px;border-radius:99px;font-size:12px;font-weight:700;color:#fff}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;margin-bottom:14px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px}
.tile b{display:block;font-size:20px}.tile span{font-size:12px;color:var(--muted)}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:14px}
@media (max-width:520px){.grid2{grid-template-columns:1fr}}
.grid3{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:14px}
.chart{position:relative}.chart svg{width:100%;height:auto;display:block}
.tip{position:absolute;pointer-events:none;background:var(--card);border:1px solid var(--line);border-radius:6px;padding:4px 8px;font-size:12px;white-space:nowrap;display:none;box-shadow:0 2px 8px rgba(0,0,0,.12)}
.keys{display:flex;gap:12px;font-size:12px;color:var(--muted);margin-top:4px}.keys i{display:inline-block;width:10px;height:3px;margin-right:5px;vertical-align:middle}
.pie{display:flex;gap:16px;align-items:center;flex-wrap:wrap}.pie svg{flex:none}
.legend{display:flex;flex-direction:column;gap:3px;font-size:13px}.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px}
.slice{cursor:pointer}div.slice:hover{text-decoration:underline}
h2{font-size:15px;margin:0 0 10px}h3{font-size:14px;margin:18px 0 10px;color:var(--muted);font-weight:600}
table{width:100%;border-collapse:collapse;font-size:12.5px}th,td{padding:5px 7px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{color:var(--muted);position:sticky;top:0;background:var(--card)}td.num,th.num{text-align:right;white-space:nowrap}
td.msg{font-family:Consolas,monospace;font-size:12px;white-space:pre-wrap;word-break:break-word}
.scroll{max-height:560px;overflow:auto}.muted{color:var(--muted)}.err{color:#d92d20;white-space:pre-wrap}
.lv-FATAL,.lv-ERROR{color:#dc2626;font-weight:700}.lv-WARN{color:#d97706;font-weight:700}.lv-INFO{color:#2563eb}.lv-DEBUG,.lv-TRACE{color:#64748b}
</style></head><body>
<header><h1>Máquina do Compute Engine · __PROJECT__</h1></header>
<main>
<div class="card"><form id="f">
<label>Instância<select id="instance"></select></label>
<label>De<input type="datetime-local" id="start"></label>
<label>Até<input type="datetime-local" id="end"></label>
<label>Máximo de linhas de log<input type="number" id="max" value="5000" min="100" step="1000"></label>
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
let rangeMinutes=360,instances=[],logRows=[],levelFilter=new Set(),sourceFilter=new Set();
function setRange(minutes){rangeMinutes=minutes;const end=new Date();$('end').value=toLocal(end);$('start').value=toLocal(new Date(end-minutes*60000));}
[['15 min',15],['1 h',60],['6 h',360],['24 h',1440],['7 dias',10080],['30 dias',43200]].forEach(([t,m])=>{const b=document.createElement('button');b.type='button';b.className='ghost';b.textContent=t;b.onclick=()=>{setRange(m);run();};$('presets').appendChild(b);});
const params=new URLSearchParams(location.search);
setRange(+(params.get('minutes')||360));
$('f').onsubmit=e=>{e.preventDefault();rangeMinutes=null;run();};
let timer=null;$('auto').onchange=()=>{clearInterval(timer);if($('auto').checked)timer=setInterval(()=>{setRange(rangeMinutes||360);run(true);},60000);};
fetch('/api/instances').then(r=>r.json()).then(list=>{instances=list;list.forEach(i=>{const o=document.createElement('option');o.value=i.id;o.textContent=i.name+' ('+i.zone+')';$('instance').appendChild(o);});
  const wanted=list.find(i=>i.name===params.get('instance'));if(wanted)$('instance').value=wanted.id;run();});
$('instance').onchange=()=>run();

const fmtBytes=v=>{if(v==null||isNaN(v))return'–';const u=['B','KB','MB','GB','TB'];let i=0;while(Math.abs(v)>=1024&&i<4){v/=1024;i++;}return v.toFixed(v<10&&i?1:0)+' '+u[i];};
const fmtRate=v=>fmtBytes(v)+'/s';
const fmtPct=v=>v==null||isNaN(v)?'–':(v<10?v.toFixed(1):v.toFixed(0))+'%';
const fmtNum=v=>v==null||isNaN(v)?'–':v.toFixed(2);
function fmtDuration(s){if(s==null||isNaN(s))return'–';const d=Math.floor(s/86400),h=Math.floor(s%86400/3600),m=Math.floor(s%3600/60);return(d?d+' d ':'')+h+' h '+m+' min';}
function pct(sorted,p){if(!sorted.length)return NaN;const i=(sorted.length-1)*p/100,lo=Math.floor(i),hi=Math.ceil(i);return sorted[lo]+(sorted[hi]-sorted[lo])*(i-lo);}
const vals=pts=>pts.map(p=>p[1]);
const sortedVals=pts=>vals(pts).sort((a,b)=>a-b);
const last=pts=>pts.length?pts[pts.length-1][1]:NaN;

const charts={};
function lineChart(id,title,lines,fmt,maxY){
  const all=lines.flatMap(l=>l.points);
  if(!all.length)return `<div class="card"><h2>${title}</h2><div class="muted">sem dados no período (memória, disco e carga dependem do Ops Agent)</div></div>`;
  charts[id]={lines,fmt};
  const W=600,H=190,L=56,R=8,T=8,B=22;
  const times=all.map(p=>+new Date(p[0])),t0=Math.min(...times),t1=Math.max(...times)||t0+1;
  const top=maxY??(Math.max(...all.map(p=>p[1]))*1.1||1);
  const x=t=>L+(t-t0)/((t1-t0)||1)*(W-L-R),y=v=>T+(1-v/top)*(H-T-B);
  let g='';for(let k=0;k<=4;k++){const v=top*k/4,yy=y(v);g+=`<line x1="${L}" x2="${W-R}" y1="${yy}" y2="${yy}" stroke="var(--grid)"/><text x="${L-6}" y="${yy+4}" text-anchor="end" font-size="10" fill="var(--muted)">${fmt(v)}</text>`;}
  const span=t1-t0;for(let k=0;k<=4;k++){const t=t0+span*k/4,d=new Date(t);const label=span>2*86400000?`${pad(d.getDate())}/${pad(d.getMonth()+1)}`:`${pad(d.getHours())}:${pad(d.getMinutes())}`;g+=`<text x="${x(t)}" y="${H-6}" text-anchor="middle" font-size="10" fill="var(--muted)">${label}</text>`;}
  const paths=lines.map(l=>`<polyline fill="none" stroke="${l.color}" stroke-width="1.8" points="${l.points.map(p=>x(+new Date(p[0])).toFixed(1)+','+y(p[1]).toFixed(1)).join(' ')}"/>`).join('');
  const keys=lines.length>1?`<div class="keys">${lines.map(l=>`<span><i style="background:${l.color}"></i>${esc(l.name)}</span>`).join('')}</div>`:'';
  charts[id].geom={W,L,R,t0,t1};
  return `<div class="card"><h2>${title}</h2><div class="chart" data-chart="${id}"><svg viewBox="0 0 ${W} ${H}">${g}${paths}<line class="cursor" x1="0" x2="0" y1="${T}" y2="${H-B}" stroke="var(--muted)" stroke-dasharray="3 3" visibility="hidden"/></svg><div class="tip"></div></div>${keys}</div>`;
}
function wireCharts(){
  document.querySelectorAll('.chart').forEach(el=>{const c=charts[el.dataset.chart];if(!c)return;const svg=el.querySelector('svg'),tip=el.querySelector('.tip'),cur=svg.querySelector('.cursor');
    el.onmousemove=e=>{const r=svg.getBoundingClientRect(),vx=(e.clientX-r.left)/r.width*c.geom.W;const t=c.geom.t0+(vx-c.geom.L)/(c.geom.W-c.geom.L-c.geom.R)*(c.geom.t1-c.geom.t0);
      let rows='',when='';c.lines.forEach(l=>{if(!l.points.length)return;let best=l.points[0];l.points.forEach(p=>{if(Math.abs(+new Date(p[0])-t)<Math.abs(+new Date(best[0])-t))best=p;});when=new Date(best[0]).toLocaleString('pt-BR');rows+=`<div><span style="color:${l.color}">●</span> ${esc(l.name)}: <b>${c.fmt(best[1])}</b></div>`;});
      tip.innerHTML=`<div class="muted">${when}</div>${rows}`;tip.style.display='block';const px=e.clientX-r.left;tip.style.left=Math.min(px+12,r.width-tip.offsetWidth-4)+'px';tip.style.top='10px';cur.setAttribute('x1',vx);cur.setAttribute('x2',vx);cur.setAttribute('visibility','visible');};
    el.onmouseleave=()=>{tip.style.display='none';cur.setAttribute('visibility','hidden');};});
}

function pie(title,items,kind){
  const total=items.reduce((a,b)=>a+b.value,0);let angle=-Math.PI/2;const r=80,c=90;let paths='';
  const fmt=items.fmt||(v=>v);
  items.forEach(it=>{if(!it.value)return;const a=it.value/total*2*Math.PI;const cls=kind?`class="slice" data-${kind}="${esc(it.label)}"`:'';
    if(a>=2*Math.PI-1e-9){paths+=`<circle ${cls} cx="${c}" cy="${c}" r="${r}" fill="${it.color}"><title>${esc(it.label)}</title></circle>`;angle+=a;return;}
    const x1=c+r*Math.cos(angle),y1=c+r*Math.sin(angle);angle+=a;const x2=c+r*Math.cos(angle),y2=c+r*Math.sin(angle);
    paths+=`<path ${cls} d="M${c},${c} L${x1},${y1} A${r},${r} 0 ${a>Math.PI?1:0} 1 ${x2},${y2} Z" fill="${it.color}" stroke="var(--card)" stroke-width="1.5"><title>${esc(it.label)}: ${fmt(it.value)} (${(it.value/total*100).toFixed(1)}%)</title></path>`;});
  const legend=items.filter(i=>i.value).map(i=>`<div ${kind?`class="slice" data-${kind}="${esc(i.label)}"`:''}><i style="background:${i.color}"></i>${esc(i.label)} — <b>${fmt(i.value)}</b> <span class="muted">(${(i.value/total*100).toFixed(1)}%)</span></div>`).join('');
  return `<div class="card"><h2>${title}</h2><div class="pie"><svg width="180" height="180" viewBox="0 0 180 180">${paths||'<circle cx="90" cy="90" r="80" fill="var(--line)"/>'}</svg><div class="legend">${legend||'<span class="muted">sem dados</span>'}</div></div></div>`;
}
const BANDS=[[25,'< 25%'],[50,'25–50%'],[75,'50–75%'],[90,'75–90%'],[Infinity,'≥ 90%']];
const BAND_COLORS=['#16a34a','#a3e635','#facc15','#f97316','#dc2626'];
function bandPie(title,pts,period){const counts=BANDS.map(()=>0);pts.forEach(p=>counts[BANDS.findIndex(b=>p[1]<b[0])]++);
  const items=BANDS.map((b,i)=>({label:b[1],value:counts[i]*period,color:BAND_COLORS[i]}));items.fmt=v=>fmtDuration(v);return pie(title,items);}
const PALETTE=['#2563eb','#7c3aed','#db2777','#0d9488','#ca8a04','#ea580c','#64748b','#94a3b8'];

async function run(quiet){
  const inst=instances.find(i=>i.id===$('instance').value);if(!inst)return;
  const start=new Date($('start').value).toISOString(),end=new Date($('end').value).toISOString();
  history.replaceState(null,'','?'+new URLSearchParams({instance:inst.name,...(rangeMinutes?{minutes:rangeMinutes}:{})}));
  renderInfo(inst);
  if(!quiet)$('out').innerHTML='<div class="card muted">Lendo métricas do Cloud Monitoring e logs do Cloud Logging…</div>';
  const q=new URLSearchParams({instance:inst.id,start,end,max:$('max').value});
  try{
    const [m,l]=await Promise.all([fetch('/api/metrics?'+q),fetch('/api/logs?'+q)].map(p=>p.then(async r=>{const d=await r.json();if(!r.ok)throw new Error(d.error);return d;})));
    render(inst,m,l);
  }catch(e){$('out').innerHTML=`<div class="card err">${esc(e.message)}</div>`;}
}
function renderInfo(i){
  const color={RUNNING:'#16a34a',TERMINATED:'#dc2626',STOPPING:'#d97706',SUSPENDED:'#d97706'}[i.status]||'#64748b';
  $('info').innerHTML=`<div class="card"><div class="facts"><span><span class="badge" style="background:${color}">${esc(i.status)}</span></span><span>Tipo <b>${esc(i.machineType)}</b></span><span>Zona <b>${esc(i.zone)}</b></span><span>IP interno <b>${esc(i.internalIp||'–')}</b></span><span>IP externo <b>${esc(i.externalIp||'nenhum')}</b></span><span>Discos <b>${esc(i.disks.join(', '))}</b></span><span>Último início <b>${i.lastStart?new Date(i.lastStart).toLocaleString('pt-BR'):'–'}</b></span><span id="uptime"></span></div></div>`;
}

function render(inst,m,l){
  const cpu=m.cpu.map(p=>[p[0],p[1]*100]),mem=m.memory,load=m.load;
  const root=m.disks.find(d=>d.device==='/dev/sda1')||m.disks[0];
  const cpuS=sortedVals(cpu),memS=sortedVals(mem);
  $('uptime').innerHTML=`No ar há <b>${fmtDuration(last(m.uptime))}</b>`;
  const tiles=[['CPU agora',fmtPct(last(cpu))],['CPU p50',fmtPct(pct(cpuS,50))],['CPU p95',fmtPct(pct(cpuS,95))],['CPU p99',fmtPct(pct(cpuS,99))],['CPU máx',fmtPct(cpuS[cpuS.length-1])],
    ['Memória agora',fmtPct(last(mem))],['Memória p95',fmtPct(pct(memS,95))],['Memória máx',fmtPct(memS[memS.length-1])],
    ['Disco '+(root?root.device:''),fmtPct(root?last(root.points):NaN)],['Carga (1 min)',fmtNum(last(load))],['Carga máx',fmtNum(Math.max(...vals(load)))]];
  const states=m.memoryStates,total=Object.values(states).reduce((a,b)=>a+b,0);
  const procs=m.processes.filter(p=>p.rssNow>0);const top=procs.slice(0,6);const procSum=top.reduce((a,p)=>a+p.rssNow,0);
  const memItems=[...top.map((p,i)=>({label:p.name,value:p.rssNow,color:PALETTE[i]})),
    {label:'outros processos',value:Math.max(0,(states.used||0)-procSum),color:'#94a3b8'},
    {label:'cache e buffers',value:(states.cached||0)+(states.buffered||0)+(states.slab||0),color:'#cbd5e1'},
    {label:'livre',value:states.free||0,color:'#e2e8f0'}];memItems.fmt=fmtBytes;
  const diskLines=m.disks.map((d,i)=>({name:d.device,points:d.points,color:PALETTE[i]}));
  $('out').innerHTML=
    `<div class="tiles">${tiles.map(([k,v])=>`<div class="tile"><span>${k}</span><b>${v}</b></div>`).join('')}</div>`+
    `<div class="muted" style="margin:-6px 0 12px">Cada ponto é a média de ${m.period>=3600?m.period/3600+' h':m.period/60+' min'}; os percentis são calculados sobre esses pontos. Memória total: ${fmtBytes(total)}.</div>`+
    `<div class="grid2">${lineChart('cpu','CPU',[{name:'CPU',points:cpu,color:'#2563eb'}],fmtPct,100)}${lineChart('mem','Memória usada',[{name:'memória',points:mem,color:'#7c3aed'}],fmtPct,100)}`+
    `${lineChart('disk','Disco usado',diskLines,fmtPct,100)}${lineChart('load','Carga (load average de 1 min)',[{name:'carga',points:load,color:'#0d9488'}],fmtNum)}`+
    `${lineChart('net','Rede',[{name:'recebido',points:m.networkIn,color:'#2563eb'},{name:'enviado',points:m.networkOut,color:'#db2777'}],fmtRate)}`+
    `${lineChart('io','E/S de disco',[{name:'leitura',points:m.diskRead,color:'#0d9488'},{name:'escrita',points:m.diskWrite,color:'#ea580c'}],fmtRate)}</div>`+
    `<div class="grid3">${bandPie('Tempo por faixa de CPU',cpu,m.period)}${bandPie('Tempo por faixa de memória',mem,m.period)}${pie('Memória agora, por processo',memItems)}</div>`+
    `<div class="card"><h2>Processos <span class="muted" style="font-weight:normal">(agrupados por programa; CPU em % de um núcleo)</span></h2><div class="scroll" style="max-height:340px"><table><thead><tr><th>Processo</th><th class="num">Memória agora</th><th class="num">Memória máx</th><th class="num">CPU média</th><th class="num">CPU máx</th></tr></thead><tbody>`+
    procs.slice(0,40).map(p=>`<tr><td>${esc(p.name)}</td><td class="num">${fmtBytes(p.rssNow)}</td><td class="num">${fmtBytes(p.rssMax)}</td><td class="num">${fmtPct(p.cpuMean)}</td><td class="num">${fmtPct(p.cpuMax)}</td></tr>`).join('')+`</tbody></table></div></div>`+
    `<div id="logs"></div>`;
  wireCharts();
  logRows=l.entries;logTruncated=l.truncated;renderLogs();
}

const LEVEL_ORDER=['FATAL','ERROR','WARN','INFO','DEBUG','TRACE','SEM NÍVEL'];
const LEVEL_COLORS={FATAL:'#7f1d1d',ERROR:'#dc2626',WARN:'#f59e0b',INFO:'#2563eb',DEBUG:'#64748b',TRACE:'#94a3b8','SEM NÍVEL':'#cbd5e1'};
let logTruncated=false;
function renderLogs(){
  const text=($('logtext')?.value||'').toLowerCase();
  const byLevel={},bySource={};logRows.forEach(r=>{byLevel[r.level]=(byLevel[r.level]||0)+1;bySource[r.source]=(bySource[r.source]||0)+1;});
  const levels=Object.keys(byLevel).sort((a,b)=>LEVEL_ORDER.indexOf(a)-LEVEL_ORDER.indexOf(b));
  const sources=Object.keys(bySource).sort((a,b)=>bySource[b]-bySource[a]);
  const shown=logRows.filter(r=>(!levelFilter.size||levelFilter.has(r.level))&&(!sourceFilter.size||sourceFilter.has(r.source))&&(!text||r.message.toLowerCase().includes(text)));
  const chips=(set,list,kind)=>list.map(v=>`<label class="chip"><input type="checkbox" data-${kind}="${esc(v)}" ${set.has(v)?'checked':''}>${esc(v)}</label>`).join('');
  $('logs').innerHTML=`<h3>Logs da máquina</h3>`+
    (logTruncated?`<div class="card err">Atingiu o máximo de linhas: os logs cobrem só a parte mais recente do período.</div>`:'')+
    `<div class="grid3">${pie('Por nível',levels.map(v=>({label:v,value:byLevel[v],color:LEVEL_COLORS[v]||'#94a3b8'})),'level')}${pie('Por origem',sources.map((v,i)=>({label:v,value:bySource[v],color:PALETTE[i%PALETTE.length]})),'source')}</div>`+
    `<div class="card"><div class="row" style="margin-bottom:10px"><span class="muted">Nível:</span>${chips(levelFilter,levels,'level')}<span class="muted" style="margin-left:10px">Origem:</span>${chips(sourceFilter,sources,'source')}
     <input id="logtext" placeholder="contém o texto…" value="${esc($('logtext')?.value||'')}" style="margin-left:auto;min-width:200px"></div>
     <h2>${shown.length} de ${logRows.length} linhas <span class="muted" style="font-weight:normal">· nada marcado = todos · clique nas pizzas para filtrar</span></h2>
     <div class="scroll"><table><thead><tr><th>Quando</th><th>Origem</th><th>Nível</th><th>Mensagem</th></tr></thead><tbody>`+
    shown.slice(0,1000).map(r=>`<tr><td style="white-space:nowrap">${new Date(r.timestamp).toLocaleString('pt-BR')}</td><td>${esc(r.source)}</td><td class="lv-${r.level.replace(' ','_')}">${esc(r.level)}</td><td class="msg">${esc(r.message.length>2000?r.message.slice(0,2000)+' …':r.message)}</td></tr>`).join('')+
    `</tbody></table>${shown.length>1000?`<div class="muted" style="padding:8px">Mostrando 1000 de ${shown.length}.</div>`:''}</div></div>`;
  document.querySelectorAll('#logs input[data-level]').forEach(b=>b.onchange=()=>{b.checked?levelFilter.add(b.dataset.level):levelFilter.delete(b.dataset.level);renderLogs();});
  document.querySelectorAll('#logs input[data-source]').forEach(b=>b.onchange=()=>{b.checked?sourceFilter.add(b.dataset.source):sourceFilter.delete(b.dataset.source);renderLogs();});
  document.querySelectorAll('#logs .slice[data-level]').forEach(s=>s.onclick=()=>{levelFilter=new Set([s.dataset.level]);renderLogs();});
  document.querySelectorAll('#logs .slice[data-source]').forEach(s=>s.onclick=()=>{sourceFilter=new Set([s.dataset.source]);renderLogs();});
  const input=$('logtext');input.oninput=()=>{clearTimeout(input.t);input.t=setTimeout(()=>{const pos=input.selectionStart;renderLogs();const again=$('logtext');again.focus();again.setSelectionRange(pos,pos);},300);};
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
