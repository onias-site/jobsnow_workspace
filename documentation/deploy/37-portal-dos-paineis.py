# Portal unico dos paineis locais: um so servidor, um menu, e cada painel (27 a 36) aberto dentro dele.
#
# Os scripts 27, 28, 29, 30, 31, 34, 35 e 36 seguem funcionando sozinhos; aqui eles sao carregados como modulos
# e cada um responde sob o prefixo /p/<numero>/ (a pagina dele recebe um fetch que acrescenta o prefixo).
# Menu:
#   Monitoria > Cloud > GCP: Memorystore, Cloud Run, mensagens das filas, Pub/Sub, Compute Engine
#   Monitoria > Dados > Elasticsearch: APIs, Entidades
#   Monitoria > Email: SendGrid
#   Cadastros: system_message, instant_message, email, bot (telas ainda vazias)
#
# Uso: python 37-portal-dos-paineis.py [porta]   (abre http://127.0.0.1:8773; atalho na area de trabalho)

import importlib.util
import json
import os
import sys
import threading
import traceback
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8773

PANELS = {
    "27": "27-requisicoes-do-cloud-run.py",
    "28": "28-maquina-do-compute-engine.py",
    "29": "29-filas-do-pubsub.py",
    "30": "30-cache-do-memorystore.py",
    "31": "31-mensagens-das-filas.py",
    "34": "34-chamadas-ao-elasticsearch.py",
    "35": "35-gravacoes-das-entidades-das-telas.py",
    "36": "36-indicadores-do-sendgrid.py",
}

modules = {}
load_errors = {}
for number, file_name in PANELS.items():
    try:
        spec = importlib.util.spec_from_file_location("painel%s" % number, os.path.join(HERE, file_name))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        modules[number] = module
    except Exception:
        load_errors[number] = traceback.format_exc()

# o painel dentro do portal: as chamadas absolutas ('/api/...') ganham o prefixo e o cabecalho repetido some
INJECTION = ("<script>(function(){var p='/p/%s',f=window.fetch.bind(window);"
             "window.fetch=function(u,o){if(typeof u==='string'&&u.charAt(0)==='/'&&u.indexOf(p+'/')!==0)u=p+u;return f(u,o);};})();</script>"
             "<style>body>header{display:none}</style>")


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
        if parsed.path == "/":
            return self.send(200, "text/html; charset=utf-8", PAGE)
        parts = parsed.path.split("/", 3)
        if len(parts) < 3 or parts[1] != "p" or parts[2] not in PANELS:
            return self.send(404, "application/json; charset=utf-8", json.dumps({"error": "not found"}))
        number = parts[2]
        if number in load_errors:
            return self.send(500, "text/plain; charset=utf-8", "O painel %s nao carregou:\n\n%s" % (number, load_errors[number]))
        if len(parts) == 3:
            self.send_response(301)
            self.send_header("Location", "/p/%s/%s" % (number, ("?" + parsed.query) if parsed.query else ""))
            self.send_header("Content-Length", "0")
            return self.end_headers()
        rest = "/" + parts[3]
        self.path = rest + (("?" + parsed.query) if parsed.query else "")
        if rest == "/":
            return self.serve_panel_page(number)
        return self.delegate(number)

    def delegate(self, number):
        # o handler do painel atende esta mesma conexao (HTTP/1.0: uma requisicao por conexao)
        own_class = self.__class__
        self.__class__ = modules[number].Handler
        try:
            modules[number].Handler.do_GET(self)
        finally:
            self.__class__ = own_class

    def serve_panel_page(self, number):
        # captura a pagina que o painel devolveria e injeta o prefixo antes do primeiro script
        captured = {}
        own_send = modules[number].Handler.send

        def capture(handler, status, content_type, payload):
            captured.update(status=status, content_type=content_type, payload=payload)

        own_class = self.__class__
        panel_class = type("Captura%s" % number, (modules[number].Handler,), {"send": capture})
        self.__class__ = panel_class
        try:
            panel_class.do_GET(self)
        finally:
            self.__class__ = own_class
        payload = captured.get("payload", "")
        page = payload.decode() if isinstance(payload, bytes) else payload
        page = page.replace("<head>", "<head>" + INJECTION % number, 1)
        return own_send(self, captured.get("status", 500), captured.get("content_type", "text/html; charset=utf-8"), page)

    def log_message(self, format, *args):
        if sys.stderr:
            sys.stderr.write("%s %s\n" % (self.log_date_time_string(), format % args))


PAGE = r"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Painéis do JobsNow</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--fg:#1d2330;--muted:#667085;--line:#e3e6eb;--accent:#2563eb;--hover:#eef2f8;--sel:#e1e9fb}
@media (prefers-color-scheme:dark){:root{--bg:#12151b;--card:#1b1f27;--fg:#e6e8ec;--muted:#98a2b3;--line:#2c323d;--accent:#5b8def;--hover:#232934;--sel:#26324a}}
*{box-sizing:border-box}html,body{height:100%}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,Segoe UI,sans-serif;display:grid;grid-template-columns:270px 1fr;grid-template-rows:52px 1fr}
#top{grid-column:1/3;display:flex;align-items:center;gap:12px;padding:0 16px;background:var(--card);border-bottom:1px solid var(--line)}
#top h1{margin:0;font-size:16px;white-space:nowrap}#crumb{color:var(--muted);font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#crumb b{color:var(--fg);font-weight:600}
#toggle{display:none;border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:6px;padding:4px 9px;font-size:16px;cursor:pointer}
nav{background:var(--card);border-right:1px solid var(--line);overflow:auto;padding:10px 8px}
nav details{margin:0}nav summary{list-style:none;cursor:pointer;padding:6px 8px;border-radius:6px;user-select:none;display:flex;align-items:center;gap:6px}
nav summary::-webkit-details-marker{display:none}
nav summary::before{content:'▸';color:var(--muted);font-size:11px;width:10px;transition:transform .15s}
nav details[open]>summary::before{transform:rotate(90deg)}
nav summary:hover,nav a:hover{background:var(--hover)}
nav .l1>summary{font-weight:700;text-transform:uppercase;font-size:12px;letter-spacing:.04em;color:var(--muted)}
nav .sub{padding-left:14px}
nav a{display:block;padding:6px 8px 6px 24px;border-radius:6px;color:var(--fg);text-decoration:none}
nav a.on{background:var(--sel);color:var(--accent);font-weight:600}
nav a small{color:var(--muted);font-weight:400}
#content{position:relative;overflow:hidden}
#content iframe{position:absolute;inset:0;width:100%;height:100%;border:0;background:var(--bg);display:none}
#content iframe.on{display:block}
.empty{display:none;padding:40px 24px;max-width:640px}.empty.on{display:block}
.empty h2{margin:0 0 6px;font-size:20px}.empty p{color:var(--muted);margin:0}
.empty code{background:var(--hover);padding:1px 6px;border-radius:4px}
@media (max-width:760px){
 body{grid-template-columns:1fr}
 #toggle{display:block}
 nav{position:fixed;top:52px;left:0;bottom:0;width:min(290px,85vw);z-index:5;transform:translateX(-100%);transition:transform .2s;box-shadow:0 8px 24px rgba(0,0,0,.25)}
 body.menu nav{transform:none}
 #content{grid-column:1}
}
</style></head>
<body>
<div id="top"><button id="toggle" aria-label="Menu">☰</button><h1>Painéis do JobsNow</h1><div id="crumb"></div></div>
<nav id="nav"></nav>
<div id="content"><div class="empty" id="empty"><h2></h2><p></p></div></div>
<script>
const MENU=[
 {name:'Monitoria',children:[
  {name:'Cloud',children:[{name:'GCP',children:[
   {id:'memorystore',name:'Memorystore',panel:'30'},
   {id:'cloud-run',name:'Cloud Run',panel:'27'},
   {id:'mensagens-das-filas',name:'Mensagens das filas',panel:'31'},
   {id:'pub-sub',name:'Pub/Sub',panel:'29'},
   {id:'compute-engine',name:'Compute Engine',panel:'28'}]}]},
  {name:'Dados',children:[{name:'Elasticsearch',children:[
   {id:'es-apis',name:'APIs',panel:'34'},
   {id:'es-entidades',name:'Entidades',panel:'35'}]}]},
  {name:'Email',children:[{id:'sendgrid',name:'SendGrid',panel:'36'}]}]},
 {name:'Cadastros',children:[
  {id:'system_message',name:'system_message',tables:['jn_system_message']},
  {id:'instant_message',name:'instant_message',tables:['jn_instant_messenger_template_message','jn_instant_messenger_parameters_to_send']},
  {id:'email',name:'email',tables:['jn_email_template_message','jn_email_parameters_to_send']},
  {id:'bot',name:'bot',tables:['jb_bot','jb_bot_allowed_user','jb_bot_explanation','jn_bot_update_handler','jn_bot_command','jn_bot_command_name','jn_bot_command_explanation','jn_bot_command_step','jn_bot_command_step_end_message','jn_command_not_allowed_to_user']}]}];
const $=id=>document.getElementById(id);
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const leaves={};const frames={};
function walk(items,path){return items.map(it=>{const p=path.concat(it.name);
  if(it.children){const level=path.length===0?'l1':'sub';return `<details class="${level}" open data-path="${esc(p.join('/'))}"><summary>${esc(it.name)}</summary><div class="sub">${walk(it.children,p)}</div></details>`;}
  leaves[it.id]={...it,path:p};return `<a href="#${it.id}" data-id="${it.id}">${esc(it.name)}${it.panel?` <small>· ${it.panel}</small>`:''}</a>`;}).join('');}
$('nav').innerHTML=walk(MENU,[]);
let closed=[];try{closed=JSON.parse(localStorage.getItem('portal.fechados')||'[]');}catch(e){}
document.querySelectorAll('nav details').forEach(d=>{if(closed.includes(d.dataset.path))d.open=false;
  d.addEventListener('toggle',()=>{const all=[...document.querySelectorAll('nav details')].filter(x=>!x.open).map(x=>x.dataset.path);try{localStorage.setItem('portal.fechados',JSON.stringify(all));}catch(e){}});});
function show(){const id=location.hash.slice(1);const leaf=leaves[id]||leaves['cloud-run'];
  document.querySelectorAll('nav a').forEach(a=>a.classList.toggle('on',a.dataset.id===leaf.id));
  $('crumb').innerHTML=leaf.path.map((n,i)=>i===leaf.path.length-1?`<b>${esc(n)}</b>`:esc(n)).join(' › ');
  document.title=leaf.name+' · Painéis do JobsNow';
  Object.values(frames).forEach(f=>f.classList.remove('on'));$('empty').classList.remove('on');
  if(leaf.panel){let f=frames[leaf.panel];
    if(!f){f=document.createElement('iframe');f.title=leaf.name;f.src='/p/'+leaf.panel+'/';frames[leaf.panel]=f;$('content').appendChild(f);}
    f.classList.add('on');}
  else{$('empty').querySelector('h2').textContent=leaf.name;
    $('empty').querySelector('p').innerHTML='Tela ainda vazia. Tabelas deste cadastro: '+leaf.tables.map(t=>`<code>${esc(t)}</code>`).join(', ')+'.';
    $('empty').classList.add('on');}
  document.body.classList.remove('menu');}
window.addEventListener('hashchange',show);
$('toggle').onclick=()=>document.body.classList.toggle('menu');
show();
</script>
</body></html>
"""

if __name__ == "__main__":
    address = "http://127.0.0.1:%d/" % PORT
    # no Windows o SO_REUSEADDR (ligado por padrao no HTTPServer) deixa dois processos ouvirem a mesma porta
    ThreadingHTTPServer.allow_reuse_address = False
    try:
        server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError:
        # o portal ja esta no ar (atalho clicado de novo): so abre a pagina
        webbrowser.open(address)
        sys.exit(0)
    if sys.stdout:
        print("Portal em %s (Ctrl+C para parar)" % address)
        for number, error in load_errors.items():
            print("Painel %s nao carregou:\n%s" % (number, error))
    threading.Timer(1.0, webbrowser.open, [address]).start()
    try:
        server.serve_forever()
    finally:
        tunnel_module = modules.get("35")
        if tunnel_module:
            tunnel_module.close_tunnel()
