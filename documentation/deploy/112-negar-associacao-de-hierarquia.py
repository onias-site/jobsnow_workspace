# /fixSkillHierarchy do bot de suporte (/ajustarHierarquiaDeHabilidades), 2026-11-23: opcao nova "negar" (deny), so em
# pedido de associacao. Faz o mesmo que "rejeitar", sem o operador digitar justificativa: a justificativa que vai ao
# usuario no e-mail e "Nao podemos aprovar essa sugestao, pois, isso implicaria que para saber {skills} teria que ser
# necessario saber primeiro {parent}" (todas as habilidades pendentes na escolha geral; so a do item no um a um).
# Este script leva a producao as 6 sementes novas ou alteradas de 112-sementes-negar-associacao-de-hierarquia.jsonl
# (mesmo id do local, regra "igual"), semeadas por VisEntitySkillFixHierarchyPending: em jn_system_message, os textos
# options e itemPrompt (que passam a citar o negar) e o texto novo denialJustification, em portugues e ingles.
# Nenhum passo nem fila nova: a opcao e lida pelos passos que ja existem.
# Ordem: deploy dos consumidores (o codigo novo) e este script, em qualquer ordem; o cache dura 1 hora.
# Idempotente.
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python 112-negar-associacao-de-hierarquia.py [destino]
#      ou: powershell -File com-tunel-de-producao.ps1 -Script 112-negar-associacao-de-hierarquia.py
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

with open(os.path.join(here, "112-sementes-negar-associacao-de-hierarquia.jsonl"), encoding="utf-8") as seeds_file:
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
