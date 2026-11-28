# Cabecalho das vagas do /salvarVaga (2026-11-27): a frase aos candidatos que abre cada vaga publicada nos grupos de
# tecnologia pelo user bot (VisJobPostingPublishingTexts.candidates, jn_system_message) passa de
# "Envie seu curriculo a 2.000 recrutadores, receba vagas aderentes ao teu perfil, basta clicar aqui" para
# "Enviamos gratuitamente e todos os dias o seu curriculo a 2 mil e-mails de recrutadores e entregamos vagas aderentes
# ao teu perfil, basta clicar aqui" (e o equivalente em ingles); o link continua {frontendUrl}/meus-dados/sobre-mim.
#
# Regra "igual": grava os 2 registros (portugues e ingles) com o mesmo _id do codigo (o do script 130).
# Idempotente. Confere o que gravou. Nao depende de deploy: vale para a proxima publicacao depois do cache das
# entidades (1 h; reiniciar os consumidores e o job resolve antes).
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python -I 135-cabecalho-das-vagas-do-salvar-vaga.py [destino]
#      ou: & .\com-tunel-de-producao.ps1 -Script .\135-cabecalho-das-vagas-do-salvar-vaga.py
#      (sem destino: o tunel de producao, http://127.0.0.1:9210; para o ES local, http://127.0.0.1:9200)
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

arguments = [argument for argument in sys.argv[1:] if not argument.startswith("--")]
target_url = arguments[0].rstrip("/") if arguments else "http://127.0.0.1:9210"
auth = os.environ.get("ES_DESTINO_AUTH", "")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

NAME = "com.vis.business.job.posting.VisJobPostingPublishingTexts.candidates"
LINK = "<a href=\"{frontendUrl}/meus-dados/sobre-mim\">"
RECORDS = [
    ("-10db59809765d123e6d1ac741285513d1688307", "portuguese",
     "<b>Enviamos gratuitamente e todos os dias o seu currículo a 2 mil e-mails de recrutadores e entregamos "
     "vagas aderentes ao teu perfil, basta " + LINK + "clicar aqui</a></b>"),
    ("-68d5b5adc44d7902296d0768417c2c4ca8ef76ea", "english",
     "<b>We send your resume for free, every day, to 2 thousand recruiter e-mails and deliver job postings that fit "
     "your profile, just " + LINK + "click here</a></b>"),
]


def call(method, path, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(target_url + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if auth:
        request.add_header("Authorization", auth)
    try:
        with opener.open(request, timeout=60) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"{}")


status, cluster = call("GET", "/")
print("cluster:", cluster.get("cluster_name"))
failures = 0
for record_id, language, message in RECORDS:
    source = {"systemMessageName": NAME, "language": language, "message": [message]}
    path = "/jn_system_message/_doc/" + urllib.parse.quote(record_id, safe="")
    status, answer = call("PUT", path + "?refresh=true", source)
    reread_status, reread = call("GET", path)
    ok = status in (200, 201) and reread_status == 200 and reread.get("_source") == source
    print("candidates", language, ": gravado e conferido" if ok else ": FALHA " + json.dumps(answer)[:300])
    failures += 0 if ok else 1

print("falhas:", failures)
sys.exit(1 if failures else 0)
