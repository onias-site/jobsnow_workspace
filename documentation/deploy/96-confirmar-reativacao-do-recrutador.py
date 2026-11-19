# /saveRecruiter <email> do bot de suporte (/salvarRecrutador), 2026-11-19: um recrutador inativo nao volta mais de
# imediato. O operador recebe a pergunta "Quer mesmo reativar este recrutador?" (Sim/Nao); no Sim ele volta aos
# recrutadores com a origem "support"; no Nao nada e gravado; outra resposta repete a pergunta.
# Este script leva a producao as 15 sementes novas ou alteradas de 96-sementes-confirmar-reativacao-do-recrutador.jsonl
# (mesmo id do local, regra "igual"), semeadas por VisEntityRecruiterSignUpReturn: o primeiro passo (stepFlow com o
# desvio 300 para o passo novo), o passo novo saveRecruiterConfirmReactivation (VisSupportSaveRecruiterConfirmReactivation),
# as 3 mensagens de fim do passo novo e os textos novos ou alterados de jn_system_message (confirmReactivation, options,
# notUnderstood, reactivationCancelled e reactivated, que agora cita a origem support).
# Nenhuma fila nova: o passo novo roda na fila do comando, JbBusinessRunBotCommand~support~saveRecruiter.
# Ordem: este script e depois o deploy dos consumidores (o bot le os comandos quando inicia; o cache dura 1 hora).
# Idempotente.
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python 96-confirmar-reativacao-do-recrutador.py [destino]
#      ou: powershell -File com-tunel-de-producao.ps1 -Script 96-confirmar-reativacao-do-recrutador.py
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

with open(os.path.join(here, "96-sementes-confirmar-reativacao-do-recrutador.jsonl"), encoding="utf-8") as seeds_file:
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
