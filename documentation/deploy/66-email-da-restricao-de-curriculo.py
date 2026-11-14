# Avisa por e-mail cada dono de curriculo restrito pelo script 65 (2026-11-12).
# A restricao (vis_resume_restriction) so guarda o hash do e-mail. O e-mail real vem dos logs do Cloud Run: cada
# POST /resume/{email}/language/... com status 200 no servico jobsnow-vis (um curriculo salvo com sucesso). O script
# calcula o hash de cada e-mail dos logs, do mesmo jeito que o Java (CcpHashDecorator SHA1 assinado, duas vezes: o
# hash do campo email e o id da entidade), e fica com os que batem com uma restricao AINDA presente no indice (quem ja
# corrigiu o curriculo nao recebe).
# O e-mail sai pelo SendGrid com a chave tokenEmailKey de C:\segredos\producao.json (nunca impressa), de
# curriculos@onias.site, com a mensagem da restricao e o link do formulario.
# Roda DEPOIS do deploy da API vis e do front (o formulario precisa mostrar a mensagem em vermelho) e depois do
# script 65 com --gravar.
# Sem --enviar, so simula: mostra os destinatarios mascarados e a previa do e-mail. Com --enviar, manda uma vez por
# restricao: o _id de cada envio aceito vai para 66-email-da-restricao-enviados.txt e nunca e reenviado.
# Uso: powershell -File com-tunel-de-producao.ps1 -Script 66-email-da-restricao-de-curriculo.py [-Argumentos --enviar]
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

INDEX = "vis_resume_restriction"
SECRETS = r"C:\segredos\producao.json"
SENDER = "curriculos@onias.site"
SENDER_NAME = "Onias.Site"
SUBJECT = "Corrija o seu cadastro de currículo para que possamos enviá-lo a partir de quarta feira."
FORM_LINK = "https://onias.site/meus-dados/sobre-mim"
PRIVACY_LINK = "https://onias.site/privacidade"
LOG_FILTER = ('resource.type="cloud_run_revision" AND resource.labels.service_name="jobsnow-vis" '
              'AND httpRequest.requestMethod="POST" AND httpRequest.requestUrl:"/resume/" '
              'AND httpRequest.requestUrl:"/language/" AND httpRequest.status=200')

args = [arg for arg in sys.argv[1:] if not arg.startswith("--")]
send = "--enviar" in sys.argv
target_url = args[0].rstrip("/") if args else "http://127.0.0.1:9210"
auth = os.environ.get("ES_DESTINO_AUTH", "")
here = os.path.dirname(os.path.abspath(__file__))
sent_file = os.path.join(here, "66-email-da-restricao-enviados.txt")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def jhash(text):
    number = int.from_bytes(hashlib.sha1(text.encode("utf-8")).digest(), "big", signed=True)
    return ("-" if number < 0 else "") + format(abs(number), "x")


def mask(email):
    user, domain = email.split("@", 1)
    return user[:2] + "***@" + domain


def es(method, path, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(target_url + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if auth:
        request.add_header("Authorization", auth)
    with opener.open(request) as response:
        return json.loads(response.read() or b"{}")


# 1. restricoes ainda presentes
answer = es("POST", "/" + INDEX + "/_search", {"size": 10000, "query": {"match_all": {}}})
restrictions = {hit["_id"]: hit["_source"]["message"] for hit in answer["hits"]["hits"]}
print("restricoes no indice:", len(restrictions))

# 2. e-mails dos curriculos salvos com sucesso (logs do Cloud Run)
gcloud = shutil.which("gcloud")
logs = subprocess.run([gcloud, "logging", "read", LOG_FILTER, "--project", "jobsnow-prd", "--freshness", "60d",
                       "--format", "json"], capture_output=True, text=True, encoding="utf-8", check=True).stdout
candidates = set()
for entry in json.loads(logs or "[]"):
    url = entry.get("httpRequest", {}).get("requestUrl", "")
    for raw in re.findall(r"/resume/([^/?]+)/language/", url):
        email = urllib.parse.unquote(raw).strip()
        candidates.update({email, email.lower()})
recipients = {}
for email in sorted(candidates):
    restriction_id = jhash(jhash(email))
    if restriction_id in restrictions:
        recipients[restriction_id] = email
print("e-mails nos logs:", len(candidates), "| restricoes com e-mail identificado:", len(recipients))
unknown = sorted(set(restrictions) - set(recipients))
if unknown:
    print("restricoes sem e-mail nos logs (nao recebem):", unknown)

# 3. envio, uma vez por restricao
already_sent = set()
if os.path.exists(sent_file):
    with open(sent_file, encoding="utf-8") as source:
        already_sent = {line.strip() for line in source if line.strip()}


def bodies(messages):
    text = "\n\n".join(messages) + "\n\nCorrija aqui: " + FORM_LINK + "\n\n--\nOnias.Site - Política de privacidade: " + PRIVACY_LINK
    paragraphs = "".join("<p>" + html.escape(message) + "</p>" for message in messages)
    page = (paragraphs + '<p><a href="' + FORM_LINK + '">Corrija o seu cadastro aqui</a></p>'
            + '<hr><p style="font-size:12px;color:#666">Onias.Site - <a href="' + PRIVACY_LINK
            + '">Política de privacidade</a></p>')
    return text, page


pending = {key: value for key, value in recipients.items() if key not in already_sent}
print("ja enviados antes:", len(recipients) - len(pending), "| a enviar:", len(pending))
for number, (restriction_id, email) in enumerate(sorted(pending.items(), key=lambda item: item[1]), 1):
    print("%3d  %s  %s" % (number, restriction_id, mask(email)))

if pending:
    sample_text, _ = bodies(restrictions[next(iter(pending))])
    print("\n--- previa ---\nAssunto:", SUBJECT, "\nDe:", SENDER_NAME, "<" + SENDER + ">\n\n" + sample_text + "\n--------------")

if not send:
    print("simulacao: nenhum e-mail enviado (use --enviar)")
    sys.exit(0)

with open(SECRETS, encoding="utf-8") as source:
    secrets = json.load(source)
api_key = secrets["tokenEmailKey"]
send_url = secrets["urlEmailKey"]
failures = 0
for restriction_id, email in pending.items():
    text, page = bodies(restrictions[restriction_id])
    payload = {"personalizations": [{"to": [{"email": email}]}], "from": {"email": SENDER, "name": SENDER_NAME},
               "subject": SUBJECT, "content": [{"type": "text/plain", "value": text}, {"type": "text/html", "value": page}]}
    request = urllib.request.Request(send_url, data=json.dumps(payload).encode("utf-8"), method="POST")
    request.add_header("Content-Type", "application/json")
    request.add_header("Authorization", "Bearer " + api_key)
    try:
        with opener.open(request) as response:
            status = response.status
    except urllib.error.HTTPError as error:
        status = error.code
        print("falha", restriction_id, mask(email), status, error.read()[:300])
    if status != 202:
        failures += 1
        continue
    with open(sent_file, "a", encoding="utf-8") as target:
        target.write(restriction_id + "\n")
    print("enviado", restriction_id, mask(email))
print("enviados:", len(pending) - failures, "| falhas:", failures)
sys.exit(1 if failures else 0)
