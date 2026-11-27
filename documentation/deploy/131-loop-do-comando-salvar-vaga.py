# Comando /salvarVaga do bot de suporte em loop (2026-11-27): depois de gravar uma vaga, o passo saveJobPostingText passa
# a ser o proprio proximo passo, e a resposta "saved" pede a proxima vaga ("Envie a proxima vaga ou digite /sair para
# encerrar"). O operador manda quantas vagas quiser na mesma sessao, ate digitar /sair (/exit).
#
# O que faz: regrava, com o mesmo id do local (regra "igual"), os 3 registros que mudaram nas sementes de
# VisEntityJobPosting (131-sementes-loop-do-salvar-vaga.jsonl): o passo saveJobPostingText em jn_bot_command_step (agora
# com nextStep) e os 2 textos de VisSupportSaveJobPostingMessages.saved em jn_system_message (portugues e ingles).
#
# Ordem: depois do script 130. Nao depende de deploy (o motor do bot ja segue o nextStep do registro), mas o cache das
# entidades do bot dura 1 h: reiniciar os consumidores do PM2 ou esperar a hora passar. Idempotente.
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python 131-loop-do-comando-salvar-vaga.py [destino]
#      ou: & .\com-tunel-de-producao.ps1 -Script .\131-loop-do-comando-salvar-vaga.py
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
here = os.path.dirname(os.path.abspath(__file__))
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

SEEDS_FILE = os.path.join(here, "131-sementes-loop-do-salvar-vaga.jsonl")


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

with open(SEEDS_FILE, encoding="utf-8") as seeds_file:
    seeds = [json.loads(line) for line in seeds_file if line.strip()]
for seed in seeds:
    index = seed["index"]
    path = "/%s/_doc/%s" % (index, urllib.parse.quote(seed["id"], safe=""))
    source = seed["source"]
    call("PUT", path + "?refresh=true", source)
    status, written = call("GET", path)
    ok = status == 200 and written.get("_source") == source
    failures += 0 if ok else 1
    print("%-22s %s %s" % (index, seed["id"], "ok" if ok else "FALHOU"))
print("registros: %d" % len(seeds))
print("OK" if failures == 0 else "FALHAS: %d" % failures)
sys.exit(1 if failures else 0)
