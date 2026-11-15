# Comando /saveRecruiter <email> do bot de suporte (/salvarRecrutador, 2026-11-14): o operador cadastra um e-mail como
# recrutador em vis_recruiter (origem "support"), validando o endereco; um recrutador ja ativo so e avisado e um inativo
# volta aos recrutadores (como no cadastro, com vis_recruiter_sign_up_return).
# Este script leva a producao as sementes de 79-sementes-comando-salvar-recrutador.jsonl (mesmo id do local, regra
# "igual"), semeadas por VisEntityRecruiterSignUpReturn: o comando, o passo (VisSupportSaveRecruiter), o nome em
# portugues, as explicacoes, as mensagens de fim e os textos (jn_system_message).
# A fila nova JbBusinessRunBotCommand~support~saveRecruiter esta em topicos.tsv: rodar o 03-criar-filas.ps1 antes do
# deploy dos consumidores.
# Ordem: 03-criar-filas.ps1, este script e depois o deploy da API vis, da API js e dos consumidores (o bot le os
# comandos quando inicia). Idempotente.
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python 79-comando-salvar-recrutador.py [destino]
#      ou: powershell -File com-tunel-de-producao.ps1 -Script 79-comando-salvar-recrutador.py
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

arguments = [argument for argument in sys.argv[1:] if not argument.startswith("--")]
target_url = arguments[0].rstrip("/") if arguments else "http://127.0.0.1:9210"
auth = os.environ.get("ES_DESTINO_AUTH", "")
here = os.path.dirname(os.path.abspath(__file__))
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


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

with open(os.path.join(here, "79-sementes-comando-salvar-recrutador.jsonl"), encoding="utf-8") as seeds_file:
    seeds = [json.loads(line) for line in seeds_file if line.strip()]
for seed in seeds:
    index = seed["index"]
    path = "/%s/_doc/%s" % (index, urllib.parse.quote(seed["id"], safe=""))
    source = seed["source"]
    status, answer = call("PUT", path + "?refresh=true", source)
    status, written = call("GET", path)
    ok = status == 200 and written.get("_source") == source
    failures += 0 if ok else 1
    print("%-34s %s %s" % (index, seed["id"][:42], "ok" if ok else "FALHOU"))
print("sementes: %d" % len(seeds))
sys.exit(1 if failures else 0)
