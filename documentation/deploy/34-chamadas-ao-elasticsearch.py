# Painel local das chamadas ao Elasticsearch de producao (jobsnow-prd), por API do Elasticsearch e por indices:
# junta as chamadas que as APIs do Cloud Run (linha jobsnowDbCalls do stdout, CcpDbCallsLogFilter) e os consumidores
# das filas (log mensagens, CcpMessageReceiver) fizeram, com o tempo por dentro do Elasticsearch quando o
# 33-slowlog-de-todas-as-queries.py esta ligado (medicao_elasticsearch.py). Mostra graficos de linha e pizzas por nome
# da API (Search API, Multi get API...) e por indices, e uma tabela API x indices.
# Indices de uma chamada: os do caminho e, no _mget e no _bulk, os do corpo, sem repeticao, em ordem alfabetica e
# separados por virgula, como uma coisa so; "nenhum" quando a chamada nao usa indice (_cluster/health). Chamadas
# gravadas antes de os indices irem para o log (antes do deploy de 2026-11-05 a noite) saem do caminho, e um _mget ou
# _bulk dessas fica como "nao registrado".
# Uso: python 34-chamadas-ao-elasticsearch.py [porta]   (abre http://127.0.0.1:8770; atalho em Desktop\paineis)
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
GCLOUD = os.path.join(os.environ["LOCALAPPDATA"], "Google", "Cloud SDK", "google-cloud-sdk", "bin", "gcloud.cmd")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8770
STDOUT_LOG_NAME = "projects/%s/logs/run.googleapis.com%%2Fstdout" % PROJECT
MESSAGES_LOG_NAME = "projects/%s/logs/mensagens" % PROJECT
NO_INDEX = "nenhum"
NOT_RECORDED = "não registrado"
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
    parsed = datetime.fromisoformat(moment.replace("Z", "+00:00")) + timedelta(minutes=minutes)
    return parsed.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def indices_of(raw):
    # os indices gravados pela chamada; nas linhas antigas, os do caminho (o _mget e o _bulk delas nao tem como saber)
    if "indices" in raw:
        names = sorted(set(raw["indices"] or []))
        return ",".join(names) if names else NO_INDEX
    path = raw.get("path", "")
    first = path.lstrip("/").split("/", 1)[0].split("?", 1)[0]
    if not first or first.startswith("_"):
        return NOT_RECORDED if re.match(r"/_(mget|bulk)", path) else NO_INDEX
    return ",".join(sorted(set(first.split(","))))


def read_units(start, end, maximum):
    # as unidades (requisicoes e mensagens) que chamaram o Elasticsearch no periodo
    api_filters = ['logName="%s"' % STDOUT_LOG_NAME, 'resource.type="cloud_run_revision"', 'jsonPayload.kind="jobsnowDbCalls"',
                   'timestamp>="%s"' % start, 'timestamp<"%s"' % end]
    queue_filters = ['logName="%s"' % MESSAGES_LOG_NAME, 'jsonPayload.dbCallsCount>0', 'timestamp>="%s"' % start, 'timestamp<"%s"' % end]
    api_entries, api_truncated = medicao_elasticsearch.list_entries(access_token, forget_token, PROJECT, api_filters, maximum)
    queue_entries, queue_truncated = medicao_elasticsearch.list_entries(access_token, forget_token, PROJECT, queue_filters, maximum)
    units = []
    for entry in api_entries:
        payload = entry.get("jsonPayload", {})
        service = entry.get("resource", {}).get("labels", {}).get("service_name", "")
        units.append({"timestamp": entry.get("timestamp", ""), "kind": "API", "origin": service.replace("jobsnow-", "API "),
                      "source": "%s %s" % (payload.get("httpMethod", ""), payload.get("uri", "")), "payload": payload})
    for entry in queue_entries:
        payload = entry.get("jsonPayload", {})
        topic = payload.get("topic", "")
        units.append({"timestamp": entry.get("timestamp", ""), "kind": "Fila", "origin": "fila " + topic.rsplit(".", 1)[-1],
                      "source": topic, "payload": payload})
    return units, api_truncated or queue_truncated


def read_calls(start, end, maximum):
    units, truncated = read_units(start, end, maximum)
    # desde a medicao do cache a linha tambem sai para requisicoes que so tocaram o Memorystore: ficam de fora
    units = [unit for unit in units if unit["payload"].get("dbCalls")]
    traces = [unit["payload"].get("traceId", "") for unit in units]
    slowlog = medicao_elasticsearch.read_slowlog(access_token, forget_token, PROJECT, start, later(end, 10), traces)
    calls = []
    for unit in units:
        enriched = medicao_elasticsearch.enrich(unit["payload"], slowlog)
        raws = unit["payload"].get("dbCalls", [])
        for raw, call in zip(raws, enriched["calls"]):
            calls.append({
                "timestamp": unit["timestamp"], "kind": unit["kind"], "origin": unit["origin"], "source": unit["source"],
                "api": call["api"], "indices": indices_of(raw), "path": call["method"] + " " + call["path"], "status": call["status"],
                "clientMs": call["clientMs"], "tookMs": call["tookMs"], "shardMs": call["shardMs"], "queryMs": call["queryMs"],
                "fetchMs": call["fetchMs"], "writeMs": call["writeMs"], "hits": call["hits"],
            })
    return {"calls": calls, "units": len(units), "truncated": truncated, "slowlogLines": slowlog["lines"], "slowlogTruncated": slowlog["truncated"]}


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
            if parsed.path == "/api/calls":
                return self.send_json(200, read_calls(query["start"], query["end"], int(query.get("max", "20000"))))
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
<title>Chamadas ao Elasticsearch</title>
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
.wider{grid-column:span 2}@media (max-width:700px){.wider{grid-column:1/-1}}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin-bottom:14px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px}
.tile b{display:block;font-size:20px}.tile span{font-size:12px;color:var(--muted)}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:14px}
.grid3{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:14px}
@media (max-width:520px){.grid2,.grid3{grid-template-columns:1fr}}
.chart{position:relative}.chart svg{width:100%;height:auto;display:block}
.tip{position:absolute;pointer-events:none;background:var(--card);border:1px solid var(--line);border-radius:6px;padding:4px 8px;font-size:12px;white-space:nowrap;display:none;box-shadow:0 2px 8px rgba(0,0,0,.12);z-index:2}
.keys{display:flex;gap:12px;flex-wrap:wrap;font-size:12px;color:var(--muted);margin-top:4px}.keys i{display:inline-block;width:10px;height:3px;margin-right:5px;vertical-align:middle}
.pie{display:flex;gap:16px;align-items:center;flex-wrap:wrap}.pie svg{flex:none}
.legend{display:flex;flex-direction:column;gap:3px;font-size:13px;min-width:0;word-break:break-all}.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px}
.slice{cursor:pointer}div.slice:hover{text-decoration:underline}
h2{font-size:15px;margin:0 0 10px}
table{width:100%;border-collapse:collapse;font-size:12.5px}th,td{padding:5px 7px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{color:var(--muted);position:sticky;top:0;background:var(--card);cursor:pointer}td.num,th.num{text-align:right;white-space:nowrap}td.idx{word-break:break-all}
tr.pick{cursor:pointer}tr.pick:hover td{background:var(--bg)}
.scroll{max-height:620px;overflow:auto}.muted{color:var(--muted)}.err{color:#d92d20;white-space:pre-wrap}.bad{color:#dc2626;font-weight:700}
.active{display:flex;gap:6px;flex-wrap:wrap;align-items:center;grid-column:1/-1}.active span{background:var(--bg);border:1px solid var(--line);border-radius:7px;padding:2px 8px;font-size:12px}
</style></head><body>
<header><h1>Chamadas ao Elasticsearch · __PROJECT__</h1></header>
<main>
<div class="card"><form id="f">
<label>Origem<select id="kind"><option value="">(APIs e filas)</option><option value="API">só APIs</option><option value="Fila">só filas</option></select></label>
<label>API do Elasticsearch<select id="api"><option value="">(todas)</option></select></label>
<label class="wider">Índices<select id="indices"><option value="">(todos)</option></select></label>
<label>De<input type="datetime-local" id="start"></label>
<label>Até<input type="datetime-local" id="end"></label>
<label>Máximo de requisições e mensagens<input type="number" id="max" value="20000" min="100" step="1000"></label>
<button type="submit">Buscar</button>
<div class="row"><span class="muted">Período:</span><span id="presets" style="display:contents"></span></div>
<div class="active muted" id="active"></div>
</form></div>
<div id="out"></div>
</main>
<script>
const $=id=>document.getElementById(id);
const pad=n=>String(n).padStart(2,'0');
const toLocal=d=>`${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const fmtInt=v=>v==null||isNaN(v)?'–':Math.round(v).toLocaleString('pt-BR');
const fmtMs=v=>v==null||isNaN(v)?'–':v>=1000?(v/1000).toFixed(v>=10000?0:2)+' s':v.toFixed(v<1?2:v<10?1:0)+' ms';
function pct(sorted,p){if(!sorted.length)return NaN;const i=(sorted.length-1)*p/100,lo=Math.floor(i),hi=Math.ceil(i);return sorted[lo]+(sorted[hi]-sorted[lo])*(i-lo);}
const PALETTE=['#2563eb','#7c3aed','#db2777','#0d9488','#ca8a04','#ea580c','#16a34a','#0891b2','#be123c','#4f46e5','#64748b','#94a3b8'];
let all=[],meta=null;
function setRange(minutes){const end=new Date();$('end').value=toLocal(end);$('start').value=toLocal(new Date(end-minutes*60000));}
[['1 h',60],['6 h',360],['24 h',1440],['7 dias',10080],['30 dias',43200]].forEach(([t,m])=>{const b=document.createElement('button');b.type='button';b.className='ghost';b.textContent=t;b.onclick=()=>{setRange(m);run();};$('presets').appendChild(b);});
const params=new URLSearchParams(location.search);
setRange(+(params.get('minutes')||1440));
$('f').onsubmit=e=>{e.preventDefault();run();};
['kind','api','indices'].forEach(id=>$(id).onchange=()=>render());
function fillSelect(id,values){const select=$(id),current=select.value;select.length=1;values.forEach(v=>{const o=document.createElement('option');o.value=v;o.textContent=v;select.appendChild(o);});select.value=values.includes(current)?current:'';}

async function run(){
  $('out').innerHTML='<div class="card muted">Lendo as chamadas do Cloud Logging (APIs, filas e slowlog)…</div>';
  const q=new URLSearchParams({start:new Date($('start').value).toISOString(),end:new Date($('end').value).toISOString(),max:$('max').value});
  try{const r=await fetch('/api/calls?'+q);const d=await r.json();if(!r.ok)throw new Error(d.error);
    meta=d;all=d.calls;
    fillSelect('api',[...new Set(all.map(c=>c.api))].sort());fillSelect('indices',[...new Set(all.map(c=>c.indices))].sort());
    if(params.get('api')){$('api').value=params.get('api');params.delete('api');}if(params.get('indices')){$('indices').value=params.get('indices');params.delete('indices');}
    render();
  }catch(e){$('out').innerHTML=`<div class="card err">${esc(e.message)}</div>`;}
}
function filtered(){const kind=$('kind').value,api=$('api').value,indices=$('indices').value;
  return all.filter(c=>(!kind||c.kind===kind)&&(!api||c.api===api)&&(!indices||c.indices===indices));}

function step(spanMs){const steps=[60,300,900,1800,3600,10800,21600,43200,86400].map(s=>s*1000);return steps.find(s=>spanMs/s<=120)||86400000;}
function timeline(calls,key,value,top){
  // linhas por intervalo: as `top` maiores chaves pelo total; o resto vira "outras"
  const t0=+new Date($('start').value),t1=+new Date($('end').value),size=step(t1-t0);
  const totals={};calls.forEach(c=>totals[key(c)]=(totals[key(c)]||0)+value(c));
  const keys=Object.keys(totals).sort((a,b)=>totals[b]-totals[a]);const shown=keys.slice(0,top),rest=keys.length>top;
  const grid=[];for(let t=Math.floor(t0/size)*size;t<=t1;t+=size)grid.push(t);
  const series={};[...shown,...(rest?['outras']:[])].forEach(k=>series[k]=grid.map(()=>0));
  calls.forEach(c=>{const i=Math.floor((+new Date(c.timestamp)-grid[0])/size);if(i<0||i>=grid.length)return;const k=shown.includes(key(c))?key(c):'outras';series[k][i]+=value(c);});
  return {size,lines:Object.entries(series).map(([k,v],i)=>({name:k,color:k==='outras'?'#94a3b8':PALETTE[i%PALETTE.length],points:grid.map((t,j)=>[new Date(t).toISOString(),v[j]])}))};
}
function latencyTimeline(calls){
  const t0=+new Date($('start').value),t1=+new Date($('end').value),size=step(t1-t0);const buckets={};
  calls.forEach(c=>{const t=Math.floor(+new Date(c.timestamp)/size)*size;(buckets[t]=buckets[t]||[]).push(c.clientMs);});
  const times=Object.keys(buckets).map(Number).sort((a,b)=>a-b);
  const line=(p,name,color)=>({name,color,points:times.map(t=>[new Date(t).toISOString(),pct(buckets[t].sort((a,b)=>a-b),p)])});
  return {size,lines:[line(50,'p50','#16a34a'),line(95,'p95','#f59e0b'),line(99,'p99','#dc2626')]};
}

const charts={};
function lineChart(id,title,data,fmt,note){
  const lines=data.lines.filter(l=>l.points.length);const pts=lines.flatMap(l=>l.points);
  if(!pts.length||pts.every(p=>!p[1]))return `<div class="card"><h2>${title}</h2><div class="muted">sem dados no período</div></div>`;
  const W=600,H=190,L=60,R=8,T=8,B=22;const times=pts.map(p=>+new Date(p[0])),t0=Math.min(...times),t1=Math.max(...times);
  const peak=Math.max(...pts.map(p=>p[1])),integers=pts.every(p=>Number.isInteger(p[1]));const top=integers&&peak<4?4:(peak*1.1)||1;
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
function pie(title,items,fmt,filter){
  items=items.filter(i=>i.value>0).sort((a,b)=>b.value-a.value);
  if(items.length>9){const rest=items.slice(8).reduce((a,b)=>a+b.value,0);items=items.slice(0,8).concat([{label:'outras',value:rest,color:'#94a3b8'}]);}
  items.forEach((it,i)=>it.color=it.color||PALETTE[i%PALETTE.length]);
  const total=items.reduce((a,b)=>a+b.value,0);let angle=-Math.PI/2;const r=80,c=90;let paths='';
  const attrs=it=>filter&&it.label!=='outras'?`class="slice" data-filter="${filter}" data-value="${esc(it.label)}"`:'';
  items.forEach(it=>{const a=it.value/total*2*Math.PI;
    if(a>=2*Math.PI-1e-9){paths+=`<circle ${attrs(it)} cx="${c}" cy="${c}" r="${r}" fill="${it.color}"><title>${esc(it.label)}</title></circle>`;return;}
    const x1=c+r*Math.cos(angle),y1=c+r*Math.sin(angle);angle+=a;const x2=c+r*Math.cos(angle),y2=c+r*Math.sin(angle);
    paths+=`<path ${attrs(it)} d="M${c},${c} L${x1},${y1} A${r},${r} 0 ${a>Math.PI?1:0} 1 ${x2},${y2} Z" fill="${it.color}" stroke="var(--card)" stroke-width="1.5"><title>${esc(it.label)}: ${fmt(it.value)} (${(it.value/total*100).toFixed(1)}%)</title></path>`;});
  const legend=items.map(i=>`<div ${attrs(i)}><i style="background:${i.color}"></i>${esc(i.label)} — <b>${fmt(i.value)}</b> <span class="muted">(${(i.value/total*100).toFixed(1)}%)</span></div>`).join('');
  return `<div class="card"><h2>${title}</h2><div class="pie"><svg width="180" height="180" viewBox="0 0 180 180">${paths||'<circle cx="90" cy="90" r="80" fill="var(--line)"/>'}</svg><div class="legend">${legend||'<span class="muted">sem dados no período</span>'}</div></div></div>`;
}
const sumBy=(calls,key,value)=>{const m={};calls.forEach(c=>{const v=value(c);if(v==null)return;m[key(c)]=(m[key(c)]||0)+v;});return Object.entries(m).map(([label,value])=>({label,value}));};

let tableSort=['clientSum',-1];
function render(){
  if(!meta)return;
  const calls=filtered();
  history.replaceState(null,'','?'+new URLSearchParams({...($('api').value?{api:$('api').value}:{}),...($('indices').value?{indices:$('indices').value}:{})}));
  $('active').innerHTML=[['kind','origem'],['api','API'],['indices','índices']].filter(([id])=>$(id).value).map(([id,t])=>`<span>${t}: ${esc($(id).value)}</span>`).join('')+
    ([$('kind').value,$('api').value,$('indices').value].some(Boolean)?`<button type="button" class="ghost" id="clear">limpar filtros</button>`:'');
  if($('clear'))$('clear').onclick=()=>{$('kind').value='';$('api').value='';$('indices').value='';render();};
  const client=calls.map(c=>c.clientMs).sort((a,b)=>a-b),took=calls.filter(c=>c.tookMs!=null),shard=calls.filter(c=>c.shardMs!=null);
  const errors=calls.filter(c=>c.status>=400).length;
  const tiles=[['Chamadas',fmtInt(calls.length)],['Requisições e mensagens',fmtInt(meta.units)],['Cliente p50',fmtMs(pct(client,50))],['Cliente p95',fmtMs(pct(client,95))],['Cliente p99',fmtMs(pct(client,99))],
    ['Cliente total',fmtMs(client.reduce((a,b)=>a+b,0))],['Took médio',took.length?fmtMs(took.reduce((a,c)=>a+c.tookMs,0)/took.length):'–'],['Shards total',shard.length?fmtMs(shard.reduce((a,c)=>a+c.shardMs,0)):'–'],
    ['APIs distintas',new Set(calls.map(c=>c.api)).size],['Combinações de índices',new Set(calls.map(c=>c.indices)).size],['Status ≥ 400',fmtInt(errors)]];
  const slow=meta.slowlogLines?`${meta.slowlogLines} linhas do slowlog${meta.slowlogTruncated?' (cortado no máximo)':''}`:'nenhuma linha do slowlog no período: os gráficos e colunas de shards ficam vazios enquanto o <code>33-slowlog-de-todas-as-queries.py</code> estiver desligado';
  const byApi=timeline(calls,c=>c.api,()=>1,6),byIndices=timeline(calls,c=>c.indices,()=>1,6),lat=latencyTimeline(calls),effort=timeline(shard,c=>c.api,c=>c.shardMs,6);
  const unit=s=>{const m=s/60000;return m>=60?(m/60)+' h':m+' min';};
  $('out').innerHTML=
    (meta.truncated?`<div class="card err">Atingiu o máximo de requisições e mensagens: o resultado cobre só as mais recentes do período. Aumente o máximo ou reduza o período.</div>`:'')+
    `<div class="tiles">${tiles.map(([k,v])=>`<div class="tile"><span>${k}</span><b>${v}</b></div>`).join('')}</div>`+
    `<div class="muted" style="margin:-6px 0 12px">${slow}. <b>Cliente</b> = ida e volta vista pela API ou pelo consumidor · <b>took</b> = tempo que o Elasticsearch informa (só busca e bulk) · <b>shards</b> = soma do tempo de cada shard no slowlog, o esforço do Elasticsearch (get por id e mget nunca têm). Índices: os da chamada, em ordem alfabética, separados por vírgula; <b>nenhum</b> quando a chamada não usa índice. Clique numa fatia ou numa legenda para filtrar.</div>`+
    `<div class="grid2">${lineChart('api','Chamadas por API',byApi,fmtInt,'(por '+unit(byApi.size)+')')}${lineChart('indices','Chamadas por índices',byIndices,fmtInt,'(por '+unit(byIndices.size)+')')}`+
    `${lineChart('lat','Latência no cliente',lat,fmtMs,'(por '+unit(lat.size)+')')}${lineChart('effort','Esforço do Elasticsearch (shards) por API',effort,fmtMs,'(soma por '+unit(effort.size)+')')}</div>`+
    `<div class="grid3">${pie('Chamadas por API',sumBy(calls,c=>c.api,()=>1),fmtInt,'api')}${pie('Chamadas por índices',sumBy(calls,c=>c.indices,()=>1),fmtInt,'indices')}`+
    `${pie('Tempo no cliente por API',sumBy(calls,c=>c.api,c=>c.clientMs),fmtMs,'api')}${pie('Tempo no cliente por índices',sumBy(calls,c=>c.indices,c=>c.clientMs),fmtMs,'indices')}`+
    `${pie('Esforço (shards) por índices',sumBy(calls,c=>c.indices,c=>c.shardMs),fmtMs,'indices')}${pie('Chamadas por origem',sumBy(calls,c=>c.origin,()=>1),fmtInt)}</div>`+
    `<div class="card"><h2>API × índices <span class="muted" style="font-weight:normal">(clique numa linha para filtrar por ela)</span></h2><div class="scroll" id="tbl"></div></div>`;
  wireCharts();table(calls);
  document.querySelectorAll('.slice[data-filter]').forEach(el=>el.onclick=()=>{$(el.dataset.filter).value=el.dataset.value;render();});
}
const COLS=[['api','API'],['indices','Índices'],['calls','Chamadas',1],['origins','Origens'],['p50','Cliente p50',1],['p95','Cliente p95',1],['clientSum','Cliente total',1],
  ['tookAvg','Took médio',1],['shardSum','Shards total',1],['querySum','Query',1],['fetchSum','Fetch',1],['writeSum','Escrita',1],['errors','Status ≥ 400',1]];
function table(calls){
  const groups={};
  calls.forEach(c=>{const k=c.api+'|'+c.indices;const g=groups[k]=groups[k]||{api:c.api,indices:c.indices,calls:0,origins:new Set(),client:[],took:0,tookN:0,shardSum:null,querySum:null,fetchSum:null,writeSum:null,errors:0};
    g.calls++;g.origins.add(c.origin);g.client.push(c.clientMs);if(c.tookMs!=null){g.took+=c.tookMs;g.tookN++;}if(c.status>=400)g.errors++;
    [['shardMs','shardSum'],['queryMs','querySum'],['fetchMs','fetchSum'],['writeMs','writeSum']].forEach(([from,to])=>{if(c[from]!=null)g[to]=(g[to]||0)+c[from];});});
  const rows=Object.values(groups).map(g=>{const s=g.client.sort((a,b)=>a-b);return {...g,origins:[...g.origins].sort().join(', '),p50:pct(s,50),p95:pct(s,95),clientSum:s.reduce((a,b)=>a+b,0),tookAvg:g.tookN?g.took/g.tookN:null};});
  const [key,dir]=tableSort;const value=v=>v==null?-Infinity:v;rows.sort((a,b)=>(value(a[key])>value(b[key])?1:value(a[key])<value(b[key])?-1:0)*dir);
  const ms=v=>v==null?'–':fmtMs(v);
  $('tbl').innerHTML=rows.length?`<table><thead><tr>${COLS.map(([k,t,n])=>`<th data-k="${k}" class="${n?'num':''}">${t}${k===key?(dir>0?' ▲':' ▼'):''}</th>`).join('')}</tr></thead><tbody>`+
    rows.map(r=>`<tr class="pick" data-api="${esc(r.api)}" data-indices="${esc(r.indices)}"><td>${esc(r.api)}</td><td class="idx">${esc(r.indices)}</td><td class="num">${fmtInt(r.calls)}</td><td>${esc(r.origins)}</td>`+
      `<td class="num">${fmtMs(r.p50)}</td><td class="num">${fmtMs(r.p95)}</td><td class="num">${fmtMs(r.clientSum)}</td><td class="num">${ms(r.tookAvg)}</td><td class="num">${ms(r.shardSum)}</td>`+
      `<td class="num">${ms(r.querySum)}</td><td class="num">${ms(r.fetchSum)}</td><td class="num">${ms(r.writeSum)}</td><td class="num ${r.errors?'bad':''}">${fmtInt(r.errors)}</td></tr>`).join('')+`</tbody></table>`
    :'<div class="muted">Nenhuma chamada ao Elasticsearch no período com esses filtros.</div>';
  document.querySelectorAll('#tbl th').forEach(th=>th.onclick=()=>{const k=th.dataset.k;tableSort=[k,k===tableSort[0]?-tableSort[1]:-1];table(calls);});
  document.querySelectorAll('#tbl tr.pick').forEach(tr=>tr.onclick=()=>{$('api').value=tr.dataset.api;$('indices').value=tr.dataset.indices;render();});
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
    server.serve_forever()
