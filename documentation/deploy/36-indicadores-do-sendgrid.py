# Painel local dos indicadores do SendGrid de producao: volume e resultado dos envios por dia, semana ou mes (/v3/stats),
# provedores, dispositivos, clientes de e-mail, navegadores e paises (/v3/<tipo>/stats), mensagens uma a uma com assunto,
# status, aberturas e cliques (Email Activity, /v3/messages, ate 1000 por consulta), listas de supressao (/v3/suppression)
# e creditos do plano (/v3/user/credits). O envio nao marca categorias (/v3/categories vazio): o assunto faz esse papel.
# A chave e a tokenEmailKey de C:\segredos\producao.json, lida so na memoria do processo e mandada so a api.sendgrid.com.
# Essa chave tem acesso total (208 escopos, inclusive api_keys e teammates): o painel so faz GET.
# Os e-mails dos destinatarios aparecem por inteiro (decisao do usuario: so ele ve o painel).
# Uso: python 36-indicadores-do-sendgrid.py [porta]   (abre http://127.0.0.1:8772; atalho em Desktop\paineis)
import json
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8772
PROPERTIES_FILE = r"C:\segredos\producao.json"
API = "https://api.sendgrid.com"
# cota mensal do plano, como a tela de cobranca do SendGrid mostra: nenhum endpoint lido por esta chave a expoe,
# e o /v3/user/credits devolve outro numero (500.000, o limite tecnico da conta)
PLAN_MONTHLY_EMAILS = 50000
BREAKDOWNS = ("mailbox_providers", "devices", "clients", "browsers", "geo")
SUPPRESSIONS = ("bounces", "blocks", "spam_reports", "invalid_emails", "unsubscribes")
MESSAGES_LIMIT = 1000
SUPPRESSION_PAGE = 500
SUPPRESSION_MAX = 5000


def sendgrid_key():
    # o valor nunca sai deste processo, a nao ser no cabecalho Authorization das chamadas a api.sendgrid.com
    with open(PROPERTIES_FILE, encoding="utf-8") as source:
        return json.load(source)["tokenEmailKey"]


def get(path, params):
    query = urllib.parse.urlencode(params, doseq=True)
    request = urllib.request.Request("%s%s?%s" % (API, path, query), headers={"Authorization": "Bearer " + sendgrid_key()})
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.load(response)


def day_of(millis):
    return time.strftime("%Y-%m-%d", time.gmtime(millis / 1000))


def read_stats(start, end, by):
    dates = {"start_date": day_of(start), "end_date": day_of(end), "aggregated_by": by}
    result = {"global": [], "breakdowns": {}, "errors": {}}
    try:
        result["global"] = [{"date": item["date"], "metrics": item["stats"][0]["metrics"] if item["stats"] else {}} for item in get("/v3/stats", dates)]
    except Exception as error:
        result["errors"]["stats"] = describe(error)
    for kind in BREAKDOWNS:
        try:
            totals = {}
            for item in get("/v3/%s/stats" % kind, dict(dates, aggregated_by="month")):
                for stat in item["stats"]:
                    summed = totals.setdefault(stat.get("name") or "(sem nome)", {})
                    for metric, value in stat.get("metrics", {}).items():
                        summed[metric] = summed.get(metric, 0) + (value or 0)
            result["breakdowns"][kind] = totals
        except Exception as error:
            result["errors"][kind] = describe(error)
    try:
        result["credits"] = get("/v3/user/credits", {})
        result["credits"]["plan"] = PLAN_MONTHLY_EMAILS
    except Exception as error:
        result["errors"]["credits"] = describe(error)
    return result


def iso_seconds(millis):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(millis / 1000))


def read_messages(start, end):
    query = 'last_event_time BETWEEN TIMESTAMP "%s" AND TIMESTAMP "%s"' % (iso_seconds(start), iso_seconds(end))
    found = get("/v3/messages", {"query": query, "limit": MESSAGES_LIMIT}).get("messages", [])
    messages = [{"time": item.get("last_event_time", ""), "subject": item.get("subject", ""), "to": item.get("to_email", ""),
                 "status": item.get("status", ""), "opens": item.get("opens_count", 0), "clicks": item.get("clicks_count", 0)} for item in found]
    return {"messages": messages, "truncated": len(found) >= MESSAGES_LIMIT}


def read_suppressions(start, end):
    window = {"start_time": start // 1000, "end_time": end // 1000, "limit": SUPPRESSION_PAGE}
    result = {"items": [], "truncated": [], "errors": {}}
    for kind in SUPPRESSIONS:
        try:
            for offset in range(0, SUPPRESSION_MAX, SUPPRESSION_PAGE):
                page = get("/v3/suppression/%s" % kind, dict(window, offset=offset))
                for item in page:
                    result["items"].append({"kind": kind, "created": int(item.get("created", 0)) * 1000, "to": item.get("email", ""),
                                            "reason": str(item.get("reason", ""))[:300], "status": item.get("status", "")})
                if len(page) < SUPPRESSION_PAGE:
                    break
                if offset + SUPPRESSION_PAGE >= SUPPRESSION_MAX:
                    result["truncated"].append(kind)
        except Exception as error:
            result["errors"][kind] = describe(error)
    return result


def describe(error):
    if isinstance(error, urllib.error.HTTPError):
        return "%s: %s" % (error.code, error.read().decode(errors="replace")[:300])
    return "%s: %s" % (type(error).__name__, error)


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
            start, end = int(query.get("start", "0")), int(query.get("end", "0"))
            if parsed.path == "/api/stats":
                return self.send_json(200, read_stats(start, end, query.get("by", "day")))
            if parsed.path == "/api/messages":
                return self.send_json(200, read_messages(start, end))
            if parsed.path == "/api/suppressions":
                return self.send_json(200, read_suppressions(start, end))
            return self.send_json(404, {"error": "not found"})
        except Exception as error:
            return self.send_json(502, {"error": describe(error)})

    def log_message(self, format, *args):
        if sys.stderr:
            sys.stderr.write("%s %s\n" % (self.log_date_time_string(), format % args))


PAGE = r"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Indicadores do SendGrid</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--fg:#1d2330;--muted:#667085;--line:#e3e6eb;--accent:#2563eb;--grid:#eef0f3}
@media (prefers-color-scheme:dark){:root{--bg:#12151b;--card:#1b1f27;--fg:#e6e8ec;--muted:#98a2b3;--line:#2c323d;--accent:#5b8def;--grid:#232833}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,Segoe UI,sans-serif}
header{padding:16px 20px;border-bottom:1px solid var(--line);background:var(--card)}h1{margin:0;font-size:18px}
main{padding:16px 20px;max-width:1400px;margin:0 auto}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px;margin-bottom:14px;min-width:0}
.range{display:flex;gap:10px;flex-wrap:wrap;align-items:end}
label{display:flex;flex-direction:column;gap:4px;font-size:12px;color:var(--muted)}
input,select,button{font:inherit;padding:7px 9px;border:1px solid var(--line);border-radius:7px;background:var(--bg);color:var(--fg)}
button{background:var(--accent);color:#fff;border:0;cursor:pointer}button.ghost{background:transparent;color:var(--accent);border:1px solid var(--line);padding:3px 9px}
.checks{display:flex;flex-wrap:wrap;gap:4px 14px;margin:6px 0}.checks label{flex-direction:row;align-items:center;gap:5px;font-size:13px;color:var(--fg);cursor:pointer}
.checks label input{padding:0;margin:0}
.bar{display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin-top:10px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-bottom:14px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px}.tile b{display:block;font-size:20px}.tile span{font-size:12px;color:var(--muted)}.tile small{color:var(--muted)}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:14px}.grid3{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:14px}
@media (max-width:520px){.grid2,.grid3{grid-template-columns:1fr}}
.chart{position:relative}.chart svg{width:100%;height:auto;display:block}
.tip{position:absolute;pointer-events:none;background:var(--card);border:1px solid var(--line);border-radius:6px;padding:4px 8px;font-size:12px;white-space:nowrap;display:none;box-shadow:0 2px 8px rgba(0,0,0,.12);z-index:2}
.keys{display:flex;gap:12px;flex-wrap:wrap;font-size:12px;color:var(--muted);margin-top:4px}.keys i{display:inline-block;width:10px;height:3px;margin-right:5px;vertical-align:middle}
.pie{display:flex;gap:16px;align-items:center;flex-wrap:wrap}.pie svg{flex:none}
.legend{display:flex;flex-direction:column;gap:3px;font-size:13px;min-width:0;word-break:break-word}.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px}
h2{font-size:15px;margin:0 0 10px}
table{width:100%;border-collapse:collapse;font-size:12.5px}th,td{padding:5px 7px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{color:var(--muted);position:sticky;top:0;background:var(--card)}td.num,th.num{text-align:right;white-space:nowrap}
.scroll{max-height:520px;overflow:auto}.muted{color:var(--muted)}.err{color:#d92d20;white-space:pre-wrap}.bad{color:#dc2626;font-weight:700}
</style></head><body>
<header><h1>Indicadores do SendGrid · produção</h1></header>
<main>
<div class="card">
<div class="range"><label>De<input type="datetime-local" id="start"></label><label>Até<input type="datetime-local" id="end"></label>
<label>Agrupar por<select id="by"><option value="day">dia</option><option value="week">semana</option><option value="month">mês</option></select></label>
<button type="button" id="go">Buscar</button><span class="muted">Período:</span><span id="presets" style="display:contents"></span></div>
<div class="bar"><b style="font-size:13px">Métricas no gráfico de volume</b><button type="button" class="ghost" id="mAll">todas</button><button type="button" class="ghost" id="mNone">nenhuma</button></div>
<div class="checks" id="metrics"></div>
<div class="bar"><b style="font-size:13px">Assuntos</b><span class="muted">(o envio não marca categorias: o assunto as substitui; filtra a seção das mensagens)</span><button type="button" class="ghost" id="sAll">todos</button><button type="button" class="ghost" id="sNone">nenhum</button></div>
<div class="checks" id="subjects"><span class="muted">…</span></div>
</div>
<div id="out"><div class="card muted">Lendo o SendGrid…</div></div>
<div id="msgs"></div>
<div id="supp"></div>
</main>
<script>
const $=id=>document.getElementById(id);
const pad=n=>String(n).padStart(2,'0');
const toLocal=d=>`${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const fmtInt=v=>v==null||isNaN(v)?'–':Math.round(v).toLocaleString('pt-BR');
const fmtPct=v=>v==null||isNaN(v)||!isFinite(v)?'–':v.toFixed(v<10?1:0)+'%';
const PALETTE=['#2563eb','#7c3aed','#db2777','#0d9488','#ca8a04','#ea580c','#16a34a','#0891b2','#be123c','#4f46e5','#64748b','#94a3b8'];
const METRICS=[['requests','pedidos','#64748b'],['delivered','entregues','#16a34a'],['opens','aberturas','#2563eb'],['unique_opens','aberturas únicas','#0891b2'],['clicks','cliques','#7c3aed'],['unique_clicks','cliques únicos','#db2777'],
  ['bounces','bounces','#dc2626'],['blocks','bloqueios','#ea580c'],['deferred','adiados','#ca8a04'],['spam_reports','spam','#be123c'],['unsubscribes','descadastros','#4f46e5'],['invalid_emails','inválidos','#94a3b8'],
  ['bounce_drops','descartados por bounce','#f97316'],['spam_report_drops','descartados por spam','#e11d48'],['unsubscribe_drops','descartados por descadastro','#6366f1']];
const DEFAULT_METRICS=['requests','delivered','unique_opens','unique_clicks','bounces','blocks'];
const KIND_NAMES={bounces:'bounce',blocks:'bloqueio',spam_reports:'spam',invalid_emails:'inválido',unsubscribes:'descadastro'};
const STATUS_NAMES={delivered:'entregue',not_delivered:'não entregue',processing:'processando'};
const STORE='painel36.selecao';
let metrics=new Set(DEFAULT_METRICS),subjects=null,stats=null,msgs=null,supp=null,range=null;
try{const saved=JSON.parse(localStorage.getItem(STORE)||'null');if(saved)metrics=new Set(saved.metrics);}catch(e){}
function save(){try{localStorage.setItem(STORE,JSON.stringify({metrics:[...metrics]}));}catch(e){}}
function setRange(days){const end=new Date();$('end').value=toLocal(end);$('start').value=toLocal(new Date(end-days*86400000));}
[['7 dias',7],['30 dias',30],['90 dias',90],['1 ano',365]].forEach(([t,d])=>{const b=document.createElement('button');b.type='button';b.className='ghost';b.textContent=t;b.onclick=()=>{setRange(d);run();};$('presets').appendChild(b);});
setRange(30);$('go').onclick=run;$('by').onchange=run;
function metricChecks(){$('metrics').innerHTML=METRICS.map(([k,t])=>`<label><input type="checkbox" data-m="${k}" ${metrics.has(k)?'checked':''}>${t}</label>`).join('');
  document.querySelectorAll('#metrics input').forEach(b=>b.onchange=()=>{b.checked?metrics.add(b.dataset.m):metrics.delete(b.dataset.m);save();renderStats();});}
$('mAll').onclick=()=>{metrics=new Set(METRICS.map(m=>m[0]));save();metricChecks();renderStats();};$('mNone').onclick=()=>{metrics=new Set();save();metricChecks();renderStats();};
function subjectChecks(){const all=[...new Set((msgs?msgs.messages:[]).map(m=>m.subject))].sort();if(!subjects)subjects=new Set(all);
  $('subjects').innerHTML=all.length?all.map(s=>`<label title="${esc(s)}"><input type="checkbox" data-s="${esc(s)}" ${subjects.has(s)?'checked':''}>${esc(s.length>70?s.slice(0,70)+'…':s)}</label>`).join(''):'<span class="muted">nenhuma mensagem no período</span>';
  document.querySelectorAll('#subjects input').forEach(b=>b.onchange=()=>{b.checked?subjects.add(b.dataset.s):subjects.delete(b.dataset.s);renderMessages();});}
$('sAll').onclick=()=>{subjects=new Set((msgs?msgs.messages:[]).map(m=>m.subject));subjectChecks();renderMessages();};$('sNone').onclick=()=>{subjects=new Set();subjectChecks();renderMessages();};
metricChecks();

async function load(path){const r=await fetch(path+'?'+new URLSearchParams(range));const d=await r.json();if(!r.ok)throw new Error(d.error);return d;}
async function run(){
  range={start:+new Date($('start').value),end:+new Date($('end').value),by:$('by').value};subjects=null;
  $('out').innerHTML='<div class="card muted">Lendo as estatísticas do SendGrid…</div>';$('msgs').innerHTML='<div class="card muted">Lendo as mensagens (Email Activity)…</div>';$('supp').innerHTML='<div class="card muted">Lendo as listas de supressão…</div>';
  load('/api/stats').then(d=>{stats=d;renderStats();}).catch(e=>$('out').innerHTML=`<div class="card err">Estatísticas: ${esc(e.message)}</div>`);
  load('/api/messages').then(d=>{msgs=d;subjectChecks();renderMessages();}).catch(e=>{$('msgs').innerHTML=`<div class="card err">Mensagens (Email Activity): ${esc(e.message)}</div>`;$('subjects').innerHTML='<span class="muted">indisponível</span>';});
  load('/api/suppressions').then(d=>{supp=d;renderSuppressions();}).catch(e=>$('supp').innerHTML=`<div class="card err">Supressões: ${esc(e.message)}</div>`);
}

const charts={};
function lineChart(id,title,lines,fmt,note){
  const pts=lines.flatMap(l=>l.points);
  if(!pts.length||pts.every(p=>!p[1]))return `<div class="card"><h2>${title}</h2><div class="muted">sem dados no período</div></div>`;
  const W=600,H=200,L=50,R=8,T=8,B=22;const times=pts.map(p=>p[0]),t0=Math.min(...times),t1=Math.max(...times);
  const peak=Math.max(...pts.map(p=>p[1]));const top=fmt===fmtPct?Math.min(100,Math.max(10,peak*1.1)):(peak<4?4:peak*1.1);
  const x=t=>L+(t-t0)/((t1-t0)||1)*(W-L-R),y=v=>T+(1-v/top)*(H-T-B);
  let g='';for(let k=0;k<=4;k++){const v=top*k/4,yy=y(v);g+=`<line x1="${L}" x2="${W-R}" y1="${yy}" y2="${yy}" stroke="var(--grid)"/><text x="${L-6}" y="${yy+4}" text-anchor="end" font-size="10" fill="var(--muted)">${fmt(v)}</text>`;}
  for(let k=0;k<=4;k++){const t=t0+(t1-t0)*k/4,d=new Date(t);g+=`<text x="${x(t)}" y="${H-6}" text-anchor="middle" font-size="10" fill="var(--muted)">${pad(d.getUTCDate())}/${pad(d.getUTCMonth()+1)}</text>`;}
  const paths=lines.map(l=>l.points.length===1?`<circle cx="${x(l.points[0][0])}" cy="${y(l.points[0][1])}" r="3" fill="${l.color}"/>`:`<polyline fill="none" stroke="${l.color}" stroke-width="1.8" points="${l.points.map(p=>x(p[0]).toFixed(1)+','+y(p[1]).toFixed(1)).join(' ')}"/>`).join('');
  charts[id]={lines,fmt,geom:{W,L,R,t0,t1}};
  return `<div class="card"><h2>${title}${note?` <span class="muted" style="font-weight:normal;font-size:12px">${note}</span>`:''}</h2><div class="chart" data-chart="${id}"><svg viewBox="0 0 ${W} ${H}">${g}${paths}<line class="cursor" x1="0" x2="0" y1="${T}" y2="${H-B}" stroke="var(--muted)" stroke-dasharray="3 3" visibility="hidden"/></svg><div class="tip"></div></div>`+
    `<div class="keys">${lines.map(l=>`<span><i style="background:${l.color}"></i>${esc(l.name)}</span>`).join('')}</div></div>`;
}
function wireCharts(){
  document.querySelectorAll('.chart').forEach(el=>{const c=charts[el.dataset.chart];if(!c)return;const svg=el.querySelector('svg'),tip=el.querySelector('.tip'),cur=svg.querySelector('.cursor');
    el.onmousemove=e=>{const r=svg.getBoundingClientRect(),vx=(e.clientX-r.left)/r.width*c.geom.W;const t=c.geom.t0+(vx-c.geom.L)/(c.geom.W-c.geom.L-c.geom.R)*(c.geom.t1-c.geom.t0);
      let rows='',at='';c.lines.forEach(l=>{let best=l.points[0];l.points.forEach(p=>{if(Math.abs(p[0]-t)<Math.abs(best[0]-t))best=p;});const d=new Date(best[0]);at=`${pad(d.getUTCDate())}/${pad(d.getUTCMonth()+1)}/${d.getUTCFullYear()}`;rows+=`<div><span style="color:${l.color}">●</span> ${esc(l.name)}: <b>${c.fmt(best[1])}</b></div>`;});
      tip.innerHTML=`<div class="muted">${at}</div>${rows}`;tip.style.display='block';const px=e.clientX-r.left;tip.style.left=Math.max(0,Math.min(px+12,r.width-tip.offsetWidth-4))+'px';tip.style.top='10px';cur.setAttribute('x1',vx);cur.setAttribute('x2',vx);cur.setAttribute('visibility','visible');};
    el.onmouseleave=()=>{tip.style.display='none';cur.setAttribute('visibility','hidden');};});
}
function pie(title,items,note){
  items=items.filter(i=>i.value>0).sort((a,b)=>b.value-a.value);
  if(items.length>10){const rest=items.slice(9).reduce((a,b)=>a+b.value,0);items=items.slice(0,9).concat([{label:'outros',value:rest,color:'#94a3b8'}]);}
  items.forEach((it,i)=>it.color=it.color||PALETTE[i%PALETTE.length]);
  const total=items.reduce((a,b)=>a+b.value,0);let angle=-Math.PI/2;const r=80,c=90;let paths='';
  items.forEach(it=>{const a=it.value/total*2*Math.PI;
    if(a>=2*Math.PI-1e-9){paths+=`<circle cx="${c}" cy="${c}" r="${r}" fill="${it.color}"><title>${esc(it.label)}</title></circle>`;return;}
    const x1=c+r*Math.cos(angle),y1=c+r*Math.sin(angle);angle+=a;const x2=c+r*Math.cos(angle),y2=c+r*Math.sin(angle);
    paths+=`<path d="M${c},${c} L${x1},${y1} A${r},${r} 0 ${a>Math.PI?1:0} 1 ${x2},${y2} Z" fill="${it.color}" stroke="var(--card)" stroke-width="1.5"><title>${esc(it.label)}: ${fmtInt(it.value)} (${(it.value/total*100).toFixed(1)}%)</title></path>`;});
  const legend=items.map(i=>`<div><i style="background:${i.color}"></i>${esc(i.label)} — <b>${fmtInt(i.value)}</b> <span class="muted">(${(i.value/total*100).toFixed(1)}%)</span></div>`).join('');
  return `<div class="card"><h2>${title}${note?` <span class="muted" style="font-weight:normal;font-size:12px">${note}</span>`:''}</h2><div class="pie"><svg width="180" height="180" viewBox="0 0 180 180">${paths||'<circle cx="90" cy="90" r="80" fill="var(--line)"/>'}</svg><div class="legend">${legend||'<span class="muted">sem dados no período</span>'}</div></div></div>`;
}
const dayMs=s=>Date.parse(s+'T00:00:00Z');

function renderStats(){
  if(!stats)return;const g=stats.global,sum=k=>g.reduce((a,d)=>a+(d.metrics[k]||0),0);
  const req=sum('requests'),del=sum('delivered'),uo=sum('unique_opens'),uc=sum('unique_clicks'),drops=sum('bounce_drops')+sum('spam_report_drops')+sum('unsubscribe_drops');
  const c=stats.credits;
  const tiles=[['Pedidos de envio',fmtInt(req)],['Entregues',`${fmtInt(del)} <small>${fmtPct(del/req*100)}</small>`],['Aberturas únicas',`${fmtInt(uo)} <small>${fmtPct(uo/del*100)} das entregues</small>`],
    ['Cliques únicos',`${fmtInt(uc)} <small>${fmtPct(uc/del*100)} das entregues</small>`],['Bounces',`<span class="${sum('bounces')?'bad':''}">${fmtInt(sum('bounces'))}</span>`],['Bloqueios',fmtInt(sum('blocks'))],['Adiados',fmtInt(sum('deferred'))],
    ['Spam',`<span class="${sum('spam_reports')?'bad':''}">${fmtInt(sum('spam_reports'))}</span>`],['Descadastros',fmtInt(sum('unsubscribes'))],['Descartados',fmtInt(drops)],
    ['Cota do plano no mês',c?`${fmtInt(c.plan-c.used)} <small>restam de ${fmtInt(c.plan)} (${fmtInt(c.used)} usados, ${fmtPct(c.used/c.plan*100)}); renova ${esc(c.next_reset||'')}</small>`:'–',
     c?`Cota de ${fmtInt(c.plan)} do plano (tela de cobrança do SendGrid). O /v3/user/credits informa ${fmtInt(c.total)}: limite técnico da conta, não a cota do plano.`:'']];
  const errors=Object.entries(stats.errors).map(([k,m])=>`<div class="card err">${esc(k)}: ${esc(m)}</div>`).join('');
  const volume=METRICS.filter(([k])=>metrics.has(k)).map(([k,t,color])=>({name:t,color,points:g.map(d=>[dayMs(d.date),d.metrics[k]||0])}));
  const rate=(n,d,name,color)=>({name,color,points:g.filter(x=>x.metrics[d]).map(x=>[dayMs(x.date),(x.metrics[n]||0)/x.metrics[d]*100])});
  const rates=[rate('delivered','requests','entrega','#16a34a'),rate('unique_opens','delivered','abertura','#2563eb'),rate('unique_clicks','delivered','clique','#7c3aed'),rate('bounces','requests','bounce','#dc2626')];
  const by={day:'dia',week:'semana',month:'mês'}[range.by];
  const outcome=[['entregues',del,'#16a34a'],['bounces',sum('bounces'),'#dc2626'],['bloqueios',sum('blocks'),'#ea580c'],['descartados',drops,'#94a3b8'],['inválidos',sum('invalid_emails'),'#64748b']].map(([label,value,color])=>({label,value,color}));
  const bd=(kind,metric)=>Object.entries(stats.breakdowns[kind]||{}).map(([label,m])=>({label,value:m[metric]||0}));
  $('out').innerHTML=errors+`<div class="tiles">${tiles.map(([k,v,hint])=>`<div class="tile"${hint?` title="${esc(hint)}"`:''}><span>${k}</span><b>${v}</b></div>`).join('')}</div>`+
    `<div class="grid2">${lineChart('vol','Volume',volume,fmtInt,'(por '+by+', em UTC)')}${lineChart('rate','Taxas',rates,fmtPct,'(por '+by+'; abertura e clique sobre as entregues)')}</div>`+
    `<div class="grid3">${pie('Resultado dos pedidos',outcome)}${pie('Provedores de e-mail',bd('mailbox_providers','delivered'),'(entregues)')}${pie('Clientes de e-mail',bd('clients','opens'),'(aberturas)')}`+
    `${pie('Dispositivos',bd('devices','opens'),'(aberturas)')}${pie('Navegadores',bd('browsers','clicks'),'(cliques)')}${pie('Países',bd('geo','opens'),'(aberturas)')}</div>`;
  wireCharts();
}
function renderMessages(){
  if(!msgs)return;const list=msgs.messages.filter(m=>subjects.has(m.subject));
  const bySubject={};list.forEach(m=>{const s=bySubject[m.subject]=bySubject[m.subject]||{n:0,delivered:0,opened:0,clicked:0,opens:0,clicks:0};s.n++;if(m.status==='delivered')s.delivered++;if(m.opens)s.opened++;if(m.clicks)s.clicked++;s.opens+=m.opens;s.clicks+=m.clicks;});
  const days={};list.forEach(m=>{const d=Date.parse(m.time.slice(0,10)+'T00:00:00Z');(days[m.subject]=days[m.subject]||{})[d]=((days[m.subject]||{})[d]||0)+1;});
  const allDays=[...new Set(Object.values(days).flatMap(o=>Object.keys(o).map(Number)))].sort((a,b)=>a-b);
  const top=Object.entries(bySubject).sort((a,b)=>b[1].n-a[1].n).slice(0,8).map(([s])=>s);
  const lines=top.map((s,i)=>({name:s.length>40?s.slice(0,40)+'…':s,color:PALETTE[i%PALETTE.length],points:allDays.map(d=>[d,(days[s]||{})[d]||0])}));
  const sorted=[...list].sort((a,b)=>b.time.localeCompare(a.time));
  $('msgs').innerHTML=`<h2 style="margin:6px 0 10px">Mensagens <span class="muted" style="font-weight:normal;font-size:13px">(Email Activity: ${fmtInt(list.length)} de ${fmtInt(msgs.messages.length)} no período${msgs.truncated?'; cortado em 1000, as mais recentes':''})</span></h2>`+
    `<div class="grid3">${pie('Por status',Object.entries(list.reduce((a,m)=>(a[STATUS_NAMES[m.status]||m.status]=(a[STATUS_NAMES[m.status]||m.status]||0)+1,a),{})).map(([label,value])=>({label,value,color:{'entregue':'#16a34a','não entregue':'#dc2626','processando':'#ca8a04'}[label]})))}`+
    `${pie('Por assunto',Object.entries(bySubject).map(([label,s])=>({label,value:s.n})))}${pie('Engajamento',[{label:'abertas e clicadas',value:list.filter(m=>m.opens&&m.clicks).length,color:'#7c3aed'},{label:'só abertas',value:list.filter(m=>m.opens&&!m.clicks).length,color:'#2563eb'},{label:'não abertas',value:list.filter(m=>!m.opens).length,color:'#94a3b8'}])}</div>`+
    lineChart('subj','Mensagens por assunto',lines,fmtInt,'(por dia, em UTC)')+
    `<div class="card"><h2>Por assunto</h2><div class="scroll"><table><thead><tr><th>Assunto</th><th class="num">Mensagens</th><th class="num">Entregues</th><th class="num">Abertas</th><th class="num">Clicadas</th><th class="num">Aberturas</th><th class="num">Cliques</th></tr></thead><tbody>`+
      Object.entries(bySubject).sort((a,b)=>b[1].n-a[1].n).map(([s,x])=>`<tr><td>${esc(s)}</td><td class="num">${fmtInt(x.n)}</td><td class="num">${fmtInt(x.delivered)} <span class="muted">${fmtPct(x.delivered/x.n*100)}</span></td><td class="num">${fmtInt(x.opened)} <span class="muted">${fmtPct(x.opened/x.n*100)}</span></td><td class="num">${fmtInt(x.clicked)} <span class="muted">${fmtPct(x.clicked/x.n*100)}</span></td><td class="num">${fmtInt(x.opens)}</td><td class="num">${fmtInt(x.clicks)}</td></tr>`).join('')+`</tbody></table></div></div>`+
    `<div class="card"><h2>Uma a uma</h2><div class="scroll"><table><thead><tr><th>Último evento</th><th>Assunto</th><th>Para</th><th>Status</th><th class="num">Aberturas</th><th class="num">Cliques</th></tr></thead><tbody>`+
      sorted.map(m=>`<tr><td>${new Date(m.time).toLocaleString('pt-BR')}</td><td>${esc(m.subject)}</td><td>${esc(m.to)}</td><td class="${m.status==='not_delivered'?'bad':''}">${esc(STATUS_NAMES[m.status]||m.status)}</td><td class="num">${fmtInt(m.opens)}</td><td class="num">${fmtInt(m.clicks)}</td></tr>`).join('')+`</tbody></table></div></div>`;
  wireCharts();
}
function renderSuppressions(){
  const items=supp.items.sort((a,b)=>b.created-a.created);const counts={};items.forEach(i=>counts[KIND_NAMES[i.kind]]=(counts[KIND_NAMES[i.kind]]||0)+1);
  const errors=Object.entries(supp.errors).map(([k,m])=>`<div class="card err">Supressão ${esc(k)}: ${esc(m)}</div>`).join('');
  $('supp').innerHTML=errors+`<h2 style="margin:6px 0 10px">Supressões <span class="muted" style="font-weight:normal;font-size:13px">(entradas criadas no período${supp.truncated.length?'; cortado em 5000: '+supp.truncated.join(', '):''})</span></h2>`+
    `<div class="grid3">${pie('Por tipo',Object.entries(counts).map(([label,value])=>({label,value})))}${pie('Por domínio',Object.entries(items.reduce((a,i)=>{const d=i.to.split('@')[1]||'?';a[d]=(a[d]||0)+1;return a;},{})).map(([label,value])=>({label,value})))}</div>`+
    `<div class="card"><h2>Entradas</h2>${items.length?`<div class="scroll"><table><thead><tr><th>Quando</th><th>Tipo</th><th>Para</th><th>Status</th><th>Motivo</th></tr></thead><tbody>`+
      items.map(i=>`<tr><td>${new Date(i.created).toLocaleString('pt-BR')}</td><td>${esc(KIND_NAMES[i.kind])}</td><td>${esc(i.to)}</td><td>${esc(i.status)}</td><td class="muted">${esc(i.reason)}</td></tr>`).join('')+`</tbody></table></div>`:'<div class="muted">Nenhuma entrada nas listas de supressão no período.</div>'}</div>`;
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
