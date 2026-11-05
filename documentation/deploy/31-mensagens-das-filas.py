# Painel local das mensagens processadas pelos consumidores pull da VM (jobsnow-prd): escolhe a fila, o resultado e o
# periodo; lista as mensagens e mostra pizzas por resultado, por fila, por faixa de duracao e por faixa de espera na
# fila, os percentis da duracao e uma tabela por fila. Irmao do 27 (requisicoes do Cloud Run), no mesmo formato.
# Fonte: o log "mensagens" do Cloud Logging, uma linha JSON por mensagem gravada por CcpPubSubWriteMessageLog em
# /opt/jobsnow/logs/mensagens.jsonl e enviada pelo Ops Agent (23-ops-agent-na-vm.sh) como jsonPayload. So ha dados a
# partir do deploy de 2026-11-04 que criou essa linha; os logs ficam 30 dias.
# As filas saem de topicos.tsv (mesma pasta). Uma mensagem rejeitada (nack) volta e aparece de novo com o mesmo id:
# a coluna "entrega" conta as vezes em que o id apareceu no periodo lido.
# Token do gcloud do usuario (nao usa GOOGLE_APPLICATION_CREDENTIALS, que aponta para o jn-hmg).
# Uso: python 31-mensagens-das-filas.py [porta]   (abre http://127.0.0.1:8769 no navegador)
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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PROJECT = "jobsnow-prd"
HERE = os.path.dirname(os.path.abspath(__file__))
GCLOUD = os.path.join(os.environ["LOCALAPPDATA"], "Google", "Cloud SDK", "google-cloud-sdk", "bin", "gcloud.cmd")
LOG_NAME = "projects/%s/logs/mensagens" % PROJECT
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8769
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


def queues():
    names = []
    with open(os.path.join(HERE, "topicos.tsv"), encoding="utf-8") as source:
        for line in source:
            columns = line.strip().split("\t")
            if columns and columns[0]:
                names.append({"topic": columns[0], "threads": int(columns[1]) if len(columns) > 1 else 0})
    return names


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


def quoted(text):
    return '"%s"' % text.replace("\\", "\\\\").replace('"', '\\"')


def number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def read_messages(topic, results, start, end, maximum):
    filters = [
        'logName="%s"' % LOG_NAME,
        'timestamp>="%s"' % start,
        'timestamp<"%s"' % end,
    ]
    if topic:
        filters.append("jsonPayload.topic=%s" % quoted(topic))
    chosen = [result for result in results.split(",") if result in ("ok", "error")]
    if len(chosen) == 1:
        filters.append("jsonPayload.result=%s" % quoted(chosen[0]))
    body = {"resourceNames": ["projects/" + PROJECT], "filter": " AND ".join(filters), "orderBy": "timestamp desc", "pageSize": min(PAGE_SIZE, maximum)}
    messages = []
    truncated = False
    while True:
        page = list_page(body)
        for entry in page.get("entries", []):
            payload = entry.get("jsonPayload", {})
            messages.append({
                "timestamp": entry.get("timestamp", ""),
                "startedAt": payload.get("startedAt", ""),
                "topic": payload.get("topic", ""),
                "result": payload.get("result", ""),
                "durationMs": number(payload.get("durationMs")),
                "waitMs": number(payload.get("waitMs")),
                "messageId": payload.get("message_id", ""),
                "errorClass": payload.get("errorClass", ""),
                "errorMessage": payload.get("errorMessage", ""),
            })
        next_page = page.get("nextPageToken")
        if not next_page:
            break
        if len(messages) >= maximum:
            truncated = True
            break
        body["pageToken"] = next_page
    messages = messages[:maximum]
    # entrega: a ordem da linha entre as do mesmo id (mais antiga = 1); o maior numero do id diz quantas vezes voltou
    seen = {}
    for message in reversed(messages):
        key = message["messageId"]
        seen[key] = seen.get(key, 0) + 1
        message["delivery"] = seen[key]
    return {"filter": body["filter"], "truncated": truncated, "messages": messages}


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
            if parsed.path == "/api/queues":
                return self.send_json(200, queues())
            if parsed.path == "/api/messages":
                maximum = int(query.get("max", "20000"))
                result = read_messages(query.get("topic", ""), query.get("result", ""), query["start"], query["end"], maximum)
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
<title>Mensagens das filas</title>
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
.chip input{margin:0}.slice{cursor:pointer}div.slice:hover,tr.slice:hover td{text-decoration:underline}
.wider{grid-column:span 3}@media (max-width:700px){.wider{grid-column:1/-1}}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:10px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px}
.tile b{display:block;font-size:20px}.tile span{font-size:12px;color:var(--muted)}
.pies{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:14px}
.pie{display:flex;gap:16px;align-items:center;flex-wrap:wrap}.pie svg{flex:none}
.legend{display:flex;flex-direction:column;gap:3px;font-size:13px}.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px}
h2{font-size:15px;margin:0 0 10px}
table{width:100%;border-collapse:collapse;font-size:12.5px}th,td{padding:5px 7px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}
td.wrap{white-space:normal;word-break:break-word;min-width:260px}th{cursor:pointer;color:var(--muted);position:sticky;top:0;background:var(--card)}
.scroll{max-height:560px;overflow:auto}.muted{color:var(--muted)}.err{color:#d92d20;white-space:pre-wrap}
.ok{color:#16a34a}.error{color:#dc2626}
code{font-size:11.5px;color:var(--muted);word-break:break-all}
</style></head><body>
<header><h1>Mensagens das filas · consumidores da VM · jobsnow-prd</h1></header>
<main>
<div class="card"><form id="f">
<label class="wider">Fila<select id="topic"><option value="">(todas as filas)</option></select></label>
<label>De<input type="datetime-local" id="start"></label>
<label>Até<input type="datetime-local" id="end"></label>
<label>Máximo de mensagens<input type="number" id="max" value="20000" min="100" step="1000"></label>
<button type="submit">Buscar</button>
<div class="presets"><span class="muted">Período:</span></div>
<div class="statuses"><span class="muted">Resultado:</span>
<label class="chip ok"><input type="checkbox" value="ok">ok</label><label class="chip error"><input type="checkbox" value="error">erro</label>
<span class="muted">nada marcado = todos · clique numa fatia, numa legenda ou numa linha da tabela por fila para filtrar</span></div>
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
const short=t=>t.slice(t.lastIndexOf('.')+1);
function option(select,value,text){const o=document.createElement('option');o.value=value;o.textContent=text;select.appendChild(o);}
let threadsOf={};
fetch('/api/queues').then(r=>r.json()).then(list=>{
  list.sort((a,b)=>short(a.topic).localeCompare(short(b.topic))).forEach(q=>{threadsOf[q.topic]=q.threads;option($('topic'),q.topic,short(q.topic)+'  ·  '+q.threads+(q.threads>1?' threads':' thread'));});
  if(params.get('topic'))$('topic').value=params.get('topic');run();});
const resultBoxes=[...document.querySelectorAll('.statuses input[type=checkbox]')];
function resultValue(){return resultBoxes.filter(b=>b.checked).map(b=>b.value).join(',');}
function setResult(value){const tokens=value?value.split(','):[];resultBoxes.forEach(b=>b.checked=tokens.includes(b.value));}
setResult(params.get('result')||'');
resultBoxes.forEach(b=>b.onchange=()=>run());
$('topic').onchange=()=>run();
$('f').onsubmit=e=>{e.preventDefault();run();};

const DURATION=[[100,'< 100 ms'],[500,'100–500 ms'],[1000,'500 ms–1 s'],[5000,'1–5 s'],[30000,'5–30 s'],[120000,'30 s–2 min'],[Infinity,'≥ 2 min']];
const WAIT=[[1000,'< 1 s'],[5000,'1–5 s'],[30000,'5–30 s'],[60000,'30 s–1 min'],[600000,'1–10 min'],[3600000,'10 min–1 h'],[Infinity,'≥ 1 h']];
const BAND_COLORS=['#16a34a','#a3e635','#facc15','#fb923c','#ef4444','#b91c1c','#7f1d1d'];
const QUEUE_COLORS=['#2563eb','#7c3aed','#db2777','#0d9488','#ca8a04','#ea580c','#16a34a','#0891b2','#4f46e5'];
let rows=[],sortKey='timestamp',sortDir=-1;

function pct(sorted,p){if(!sorted.length)return NaN;const i=(sorted.length-1)*p/100,lo=Math.floor(i),hi=Math.ceil(i);return sorted[lo]+(sorted[hi]-sorted[lo])*(i-lo);}
const fmtMs=v=>v==null||isNaN(v)?'–':v>=3600000?(v/3600000).toFixed(1)+' h':v>=60000?(v/60000).toFixed(1)+' min':v>=1000?(v/1000).toFixed(2)+' s':v.toFixed(v<10?1:0)+' ms';
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

function pie(title,items){
  const total=items.reduce((a,b)=>a+b.value,0);let angle=-Math.PI/2;const r=80,c=90;let paths='';
  items.forEach(it=>{if(!it.value)return;const a=it.value/total*2*Math.PI;
    if(a>=2*Math.PI-1e-9){paths+=`<circle ${it.attrs?`class="slice" ${it.attrs}`:''} cx="${c}" cy="${c}" r="${r}" fill="${it.color}"><title>${esc(it.label)}: ${it.value}</title></circle>`;angle+=a;return;}
    const x1=c+r*Math.cos(angle),y1=c+r*Math.sin(angle);angle+=a;const x2=c+r*Math.cos(angle),y2=c+r*Math.sin(angle);
    paths+=`<path ${it.attrs?`class="slice" ${it.attrs}`:''} d="M${c},${c} L${x1},${y1} A${r},${r} 0 ${a>Math.PI?1:0} 1 ${x2},${y2} Z" fill="${it.color}" stroke="var(--card)" stroke-width="1.5"><title>${esc(it.label)}: ${it.value} (${(it.value/total*100).toFixed(1)}%)</title></path>`;});
  const legend=items.filter(i=>i.value).map(i=>`<div ${i.attrs?`class="slice" ${i.attrs}`:''}><i style="background:${i.color}"></i>${esc(i.label)} — <b>${i.value}</b> <span class="muted">(${(i.value/total*100).toFixed(1)}%)</span></div>`).join('');
  return `<div class="card"><h2>${title}</h2><div class="pie"><svg width="180" height="180" viewBox="0 0 180 180">${paths||'<circle cx="90" cy="90" r="80" fill="var(--line)"/>'}</svg><div class="legend">${legend||'<span class="muted">sem dados</span>'}</div></div></div>`;
}
function bands(values,limits){const counts=limits.map(()=>0);values.forEach(v=>{counts[limits.findIndex(b=>v<b[0])]++;});return limits.map((b,i)=>({label:b[1],value:counts[i],color:BAND_COLORS[i]}));}

async function run(){
  const q=new URLSearchParams({topic:$('topic').value,result:resultValue(),start:new Date($('start').value).toISOString(),end:new Date($('end').value).toISOString(),max:$('max').value});
  history.replaceState(null,'','?'+new URLSearchParams({topic:$('topic').value,result:resultValue()}));
  $('out').innerHTML='<div class="card muted">Lendo os logs do Cloud Logging…</div>';
  const t0=performance.now();
  try{
    const r=await fetch('/api/messages?'+q);const data=await r.json();
    if(!r.ok)throw new Error(data.error);
    rows=data.messages;render(data,(performance.now()-t0)/1000);
  }catch(e){$('out').innerHTML=`<div class="card err">${esc(e.message)}</div>`;}
}

function perQueue(){
  const groups={};
  rows.forEach(r=>{const g=groups[r.topic]=groups[r.topic]||{topic:r.topic,total:0,errors:0,durations:[],waits:[],ids:new Set(),repeated:new Set()};
    g.total++;if(r.result==='error')g.errors++;if(r.durationMs!=null)g.durations.push(r.durationMs);if(r.waitMs!=null)g.waits.push(r.waitMs);
    if(g.ids.has(r.messageId))g.repeated.add(r.messageId);g.ids.add(r.messageId);});
  return Object.values(groups).map(g=>{g.durations.sort((a,b)=>a-b);g.waits.sort((a,b)=>a-b);return g;}).sort((a,b)=>b.total-a.total);
}
function render(data,seconds){
  const dur=rows.map(r=>r.durationMs).filter(v=>v!=null).sort((a,b)=>a-b);
  const waits=rows.map(r=>r.waitMs).filter(v=>v!=null).sort((a,b)=>a-b);
  const errors=rows.filter(r=>r.result==='error').length;
  const repeated=new Set(rows.filter(r=>r.delivery>1).map(r=>r.messageId)).size;
  const tiles=[['Mensagens',rows.length],['Erros',errors+(rows.length?` (${(errors/rows.length*100).toFixed(1)}%)`:'')],['Ids que voltaram',repeated],
    ['p50',fmtMs(pct(dur,50))],['p75',fmtMs(pct(dur,75))],['p90',fmtMs(pct(dur,90))],['p95',fmtMs(pct(dur,95))],
    ['p99',fmtMs(pct(dur,99))],['máx',fmtMs(dur[dur.length-1])],['espera p50',fmtMs(pct(waits,50))],['espera p95',fmtMs(pct(waits,95))]];
  const resultItems=[{label:'ok',value:rows.length-errors,color:'#16a34a',attrs:'data-result="ok"'},{label:'erro',value:errors,color:'#dc2626',attrs:'data-result="error"'}];
  const queues=perQueue();const shown=queues.length>10?queues.slice(0,9):queues;
  const queueItems=shown.map((g,i)=>({label:short(g.topic),value:g.total,color:QUEUE_COLORS[i%QUEUE_COLORS.length],attrs:`data-topic="${esc(g.topic)}"`}));
  if(queues.length>10)queueItems.push({label:'outras '+(queues.length-9)+' filas',value:queues.slice(9).reduce((a,g)=>a+g.total,0),color:'#e2e8f0'});
  const queueTable=`<table><thead><tr><th>Fila</th><th>Threads</th><th>Mensagens</th><th>Erros</th><th>% erro</th><th>p50</th><th>p95</th><th>máx</th><th>espera p50</th><th>espera p95</th><th>Ids que voltaram</th></tr></thead><tbody>`+
    queues.map(g=>`<tr class="slice" data-topic="${esc(g.topic)}"><td>${esc(short(g.topic))}</td><td>${threadsOf[g.topic]??'–'}</td><td>${g.total}</td><td class="${g.errors?'error':''}">${g.errors}</td><td>${(g.errors/g.total*100).toFixed(1)}%</td>`+
      `<td>${fmtMs(pct(g.durations,50))}</td><td>${fmtMs(pct(g.durations,95))}</td><td>${fmtMs(g.durations[g.durations.length-1])}</td><td>${fmtMs(pct(g.waits,50))}</td><td>${fmtMs(pct(g.waits,95))}</td><td>${g.repeated.size}</td></tr>`).join('')+`</tbody></table>`;
  $('out').innerHTML=
    (data.truncated?`<div class="card err">Atingiu o máximo de ${rows.length} mensagens: o resultado cobre só as mais recentes do período. Aumente o máximo ou reduza o período.</div>`:'')+
    (rows.length?'':`<div class="card muted">Nenhuma mensagem no período. O log "mensagens" só existe desde o deploy do consumidor que grava uma linha por mensagem.</div>`)+
    `<div class="tiles" style="margin-bottom:14px">${tiles.map(([k,v])=>`<div class="tile"><span>${k}</span><b>${v}</b></div>`).join('')}</div>`+
    `<div class="pies">${pie('Por resultado',resultItems)}${pie('Por fila',queueItems)}${pie('Por faixa de duração',bands(dur,DURATION))}${pie('Por espera na fila (publicação → início)',bands(waits,WAIT))}</div>`+
    `<div class="card"><h2>Por fila</h2><div class="scroll">${queueTable}</div></div>`+
    `<div class="card"><h2>Mensagens <span class="muted" style="font-weight:normal">(${rows.length}, lidas em ${seconds.toFixed(1)} s)</span> <button class="ghost" id="csv" style="float:right">Baixar CSV</button></h2><div class="scroll" id="tbl"></div></div>`+
    `<div class="card"><code>${esc(data.filter)}</code></div>`;
  $('csv').onclick=downloadCsv;table();
  document.querySelectorAll('.slice[data-result]').forEach(p=>p.onclick=()=>{setResult(p.dataset.result);run();});
  document.querySelectorAll('.slice[data-topic]').forEach(p=>p.onclick=()=>{$('topic').value=p.dataset.topic;run();});
}

const COLS=[['timestamp','Quando'],['topic','Fila'],['result','Resultado'],['durationMs','Duração'],['waitMs','Espera'],['delivery','Entrega'],['messageId','Id'],['errorMessage','Erro']];
function table(){
  const sorted=[...rows].sort((a,b)=>(a[sortKey]>b[sortKey]?1:a[sortKey]<b[sortKey]?-1:0)*sortDir);const shown=sorted.slice(0,2000);
  $('tbl').innerHTML=`<table><thead><tr>${COLS.map(([k,t])=>`<th data-k="${k}">${t}${k===sortKey?(sortDir>0?' ▲':' ▼'):''}</th>`).join('')}</tr></thead><tbody>`+
    shown.map(r=>`<tr><td>${esc(r.startedAt||new Date(r.timestamp).toLocaleString('pt-BR'))}</td><td>${esc(short(r.topic))}</td><td class="${esc(r.result)}">${r.result==='error'?'erro':esc(r.result)}</td><td>${fmtMs(r.durationMs)}</td><td>${fmtMs(r.waitMs)}</td><td>${r.delivery}</td><td>${esc(r.messageId)}</td>`+
      `<td class="wrap">${r.errorClass?`<b>${esc(short(r.errorClass))}</b> ${esc(r.errorMessage)}`:''}</td></tr>`).join('')+
    `</tbody></table>`+(rows.length>shown.length?`<div class="muted" style="padding:8px">Mostrando 2000 de ${rows.length}; o CSV traz todas.</div>`:'');
  document.querySelectorAll('#tbl th').forEach(th=>th.onclick=()=>{const k=th.dataset.k;sortDir=k===sortKey?-sortDir:-1;sortKey=k;table();});
}
function downloadCsv(){
  const keys=['startedAt','timestamp','topic','result','durationMs','waitMs','delivery','messageId','errorClass','errorMessage'];
  const q=v=>'"'+String(v??'').replace(/"/g,'""')+'"';
  const csv=[keys.join(';'),...rows.map(r=>keys.map(k=>q(r[k])).join(';'))].join('\n');
  const a=document.createElement('a');a.href=URL.createObjectURL(new Blob(['﻿'+csv],{type:'text/csv'}));a.download='mensagens-das-filas.csv';a.click();
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
