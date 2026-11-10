# Painel local da seguranca: o ultimo resultado de cada suite, lido de c:/logs/seguranca (gravado pelos scripts 47 a
# 50) e do relatorio do surefire da suite JUnit SecuritySuite. Nada e executado daqui: so leitura dos arquivos.
#
#   47-seguranca-segredos.py           -> segredos.json            (diario, tarefa agendada)
#   48-seguranca-dependencias.py       -> dependencias.json        (diario, tarefa agendada)
#   49-seguranca-postura-do-gcp.py     -> postura-gcp.json         (diario, tarefa agendada, so leitura em producao)
#   50-seguranca-varredura-dinamica.py -> varredura-dinamica.json  (sob demanda, so contra as APIs locais)
#   SecuritySuite (JUnit)              -> ccp_rest-api-tests_jobsnow/target/surefire-reports
#
# Uso: python 51-painel-de-seguranca.py [porta]   (abre http://127.0.0.1:8774); tambem entra no portal 37 (Backend).

import glob
import json
import os
import sys
import webbrowser
import xml.etree.ElementTree as ElementTree
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
WORKSPACE = os.path.abspath(os.path.join(HERE, "..", ".."))
RESULTS = r"c:\logs\seguranca"
SUREFIRE = os.path.join(WORKSPACE, "ccp_rest-api-tests_jobsnow", "target", "surefire-reports")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 and __name__ == "__main__" else 8774
FILES = {"segredos": "segredos.json", "dependencias": "dependencias.json", "postura": "postura-gcp.json",
         "dinamica": "varredura-dinamica.json"}


def read_json(name):
    try:
        with open(os.path.join(RESULTS, name), encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def junit():
    reports = glob.glob(os.path.join(SUREFIRE, "TEST-com.jn.rest.api.security.SecuritySuite.xml"))
    if not reports:
        return None
    root = ElementTree.parse(reports[0]).getroot()
    cases = []
    for case in root.iter("testcase"):
        failure = case.find("failure")
        error = case.find("error")
        problem = failure if failure is not None else error
        cases.append({"class": case.get("classname", "").rsplit(".", 1)[-1], "name": case.get("name"),
                      "ok": problem is None, "message": (problem.get("message") or "")[:300] if problem is not None else ""})
    when = os.path.getmtime(reports[0])
    import datetime
    return {"when": datetime.datetime.fromtimestamp(when).isoformat(timespec="seconds"), "cases": cases,
            "failures": sum(1 for case in cases if not case["ok"]), "ok": all(case["ok"] for case in cases)}


def data():
    result = {key: read_json(name) for key, name in FILES.items()}
    result["junit"] = junit()
    return result


PAGE = r"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Segurança</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--fg:#1d2330;--muted:#5d6675;--line:#dde1e7;--ok:#1a7f4b;--bad:#b42318;--warn:#a15c07;--info:#3b5bdb}
@media (prefers-color-scheme:dark){:root{--bg:#14171c;--card:#1c2027;--fg:#e6e8ec;--muted:#9aa3b1;--line:#2c323c;--ok:#4cc38a;--bad:#ff6b5e;--warn:#f0b04a;--info:#8ea2ff}}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}
header{padding:16px;border-bottom:1px solid var(--line)}h1{font-size:18px;margin:0}
main{padding:16px;display:grid;gap:16px;max-width:1200px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px}
.card b{display:block;font-size:22px}.ok{color:var(--ok)}.bad{color:var(--bad)}.warn{color:var(--warn)}.info{color:var(--info)}
section{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px;overflow-x:auto}
h2{font-size:15px;margin:0 0 8px}small{color:var(--muted)}
table{border-collapse:collapse;width:100%;font-size:13px}th,td{border-bottom:1px solid var(--line);padding:5px 8px;text-align:left;vertical-align:top}
th{color:var(--muted);font-weight:600}td.wrap{word-break:break-word}
</style></head><body><header><h1>Segurança</h1><small>Último resultado de cada suíte (scripts 47 a 50 e SecuritySuite). Ativo só no local; produção só leitura.</small></header>
<main><div class="cards" id="cards"></div><div id="sections"></div></main>
<script>
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const lvl=l=>({ALTO:'bad',CRITICAL:'bad',HIGH:'bad',MEDIO:'warn',MODERATE:'warn',MEDIUM:'warn',BAIXO:'info',LOW:'info'}[l]||'');
function table(cols,rows){return `<table><tr>${cols.map(c=>`<th>${esc(c[0])}</th>`).join('')}</tr>${rows.map(r=>`<tr>${cols.map(c=>`<td class="${c[2]||''}">${c[1](r)}</td>`).join('')}</tr>`).join('')}</table>`;}
function card(title,d,okText,badText){if(!d)return `<div class="card"><small>${esc(title)}</small><b class="warn">sem resultado</b></div>`;
  return `<div class="card"><small>${esc(title)}</small><b class="${d.ok?'ok':'bad'}">${d.ok?okText:badText(d)}</b><small>${esc(d.when)}</small></div>`;}
fetch('/api/dados').then(r=>r.json()).then(d=>{
  document.getElementById('cards').innerHTML=[
    card('Suíte JUnit (SecuritySuite)',d.junit,'verde',x=>x.failures+' falha(s)'),
    card('Segredos nos repositórios',d.segredos,'nenhum novo',x=>x.new+' novo(s)'),
    card('Dependências vulneráveis',d.dependencias,'sem alta/crítica',x=>x.blocking+' alta/crítica'),
    card('Varredura dinâmica (local)',d.dinamica,'sem achado alto',x=>x.high+' alto(s)'),
    card('Postura do GCP',d.postura,'sem achado alto',x=>x.high+' alto(s)')].join('');
  let h='';
  if(d.junit)h+=`<section><h2>Suíte JUnit</h2>${table([['Classe',r=>esc(r.class)],['Teste',r=>esc(r.name)],['Resultado',r=>r.ok?'<span class="ok">ok</span>':'<span class="bad">falhou</span>'],['Mensagem',r=>esc(r.message),'wrap']],d.junit.cases.slice().sort((a,b)=>a.ok-b.ok))}</section>`;
  if(d.segredos)h+=`<section><h2>Segredos</h2><small>${d.segredos.repositories.length} repositórios, ${d.segredos.secretsChecked} segredos atuais procurados por valor exato em todos os objetos.</small>${table([['Repositório',r=>esc(r.repository)],['Regra',r=>esc(r.rule)],['Onde',r=>esc((r.file||r.property)+':'+(r.line||r.object)),'wrap'],['Situação',r=>r.status==='NOVO'?'<span class="bad">NOVO</span>':esc(r.status),'wrap']],d.segredos.findings)}</section>`;
  if(d.postura)h+=`<section><h2>Postura do GCP (${esc(d.postura.project)})</h2>${table([['Nível',r=>`<span class="${lvl(r.level)}">${esc(r.level)}</span>`],['Área',r=>esc(r.area)],['Achado',r=>esc(r.text),'wrap']],d.postura.findings)}</section>`;
  if(d.dinamica)h+=`<section><h2>Varredura dinâmica</h2><small>${d.dinamica.operations} operações, ${d.dinamica.requests} requisições.</small>${table([['Nível',r=>`<span class="${lvl(r.level)}">${esc(r.level)}</span>`],['API',r=>esc(r.api)],['Onde',r=>esc(r.where),'wrap'],['Achado',r=>esc(r.text),'wrap']],d.dinamica.findings)}</section>`;
  if(d.dependencias){const g={};d.dependencias.findings.forEach(f=>{const k=f.ecosystem+'|'+f.package+'|'+f.version;const e=g[k]||(g[k]={f,n:0,sev:{},mods:new Set()});e.n++;e.sev[f.severity]=(e.sev[f.severity]||0)+1;f.modules.forEach(m=>e.mods.add(m));});
    const rows=Object.values(g).sort((a,b)=>((b.sev.CRITICAL||0)-(a.sev.CRITICAL||0))||((b.sev.HIGH||0)-(a.sev.HIGH||0)));
    h+=`<section><h2>Dependências</h2><small>${d.dependencias.javaLibraries} bibliotecas Java (runtime) e o front.</small>${table([['Ecossistema',r=>esc(r.f.ecosystem)],['Biblioteca',r=>esc(r.f.package),'wrap'],['Versão',r=>esc(r.f.version)],['Severidades',r=>Object.entries(r.sev).map(([k,v])=>`<span class="${lvl(k)}">${esc(k)} ${v}</span>`).join(' ')],['Módulos',r=>esc([...r.mods].join(', ')),'wrap']],rows)}</section>`;}
  document.getElementById('sections').innerHTML=h;});
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def send(self, status, content_type, payload):
        body = payload.encode() if isinstance(payload, str) else payload
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/":
            return self.send(200, "text/html; charset=utf-8", PAGE)
        if path == "/api/dados":
            return self.send(200, "application/json; charset=utf-8", json.dumps(data(), ensure_ascii=False))
        return self.send(404, "application/json; charset=utf-8", "{}")

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer.allow_reuse_address = False
    address = "http://127.0.0.1:%d/" % PORT
    try:
        server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError:
        webbrowser.open(address)
        sys.exit(0)
    webbrowser.open(address)
    server.serve_forever()
