# Desfaz em producao (2026-11-20, pedido do usuario) as decisoes de dois pedidos de ajuste de hierarquia de habilidades:
#   - associacao ao parent ORMJAVA: JDBC e ORACLE aprovados, MYSQL e SPRING rejeitados;
#   - desassociacao do parent NOSQLDATABASE: DATASTORE aprovado.
# Apaga os 5 registros dos itens (vis_skill_fix_hierarchy_item_approved e a gemea vis_skill_fix_hierarchy_item_rejected),
# conferindo antes que cada _id ainda guarda o parent, o type e a skill esperados. Assim um novo pedido desses itens volta
# a ser avaliado pelo operador, em vez de ser recusado como ja decidido.
# O vis_skill nao muda: na leitura de 2026-11-20, JDBC e ORACLE ja nao tinham ORMJAVA entre os pais e DATASTORE ainda tinha
# NOSQLDATABASE, ou seja, as aprovacoes nao estavam aplicadas. Os pedidos atendidos (vis_skill_fix_hierarchy_fulfiled)
# ficam: sao o historico dos chamados do usuario.
# Depois de gravar, rode o 101 de novo para recalcular as pizzas da tela Curiosidades. Idempotente.
# Uso: powershell -File com-tunel-de-producao.ps1 -Script 102-desfaz-itens-de-hierarquia.py [-Argumentos --gravar]
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

target_url = "http://127.0.0.1:9210"
auth = os.environ.get("ES_DESTINO_AUTH", "")
write = "--gravar" in sys.argv
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

ITEMS = [
    ("vis_skill_fix_hierarchy_item_approved", "59038fd0231abc2a0b1607f563b6d6f840210647", "ORMJAVA", "add", "JDBC"),
    ("vis_skill_fix_hierarchy_item_approved", "-5bcb8b598d5471c865667e1f23e3f615b3b147b", "ORMJAVA", "add", "ORACLE"),
    ("vis_skill_fix_hierarchy_item_rejected", "-5955d06855162c7d2ff0a9431a417b3b0e922dd2", "ORMJAVA", "add", "MYSQL"),
    ("vis_skill_fix_hierarchy_item_rejected", "-7311eecff2f2064fdbaebc3c633c0a55660911e4", "ORMJAVA", "add", "SPRING"),
    ("vis_skill_fix_hierarchy_item_approved", "37422c90df1f27e503e6caa3f94b8d3affffc91c", "NOSQLDATABASE", "remove", "DATASTORE"),
]


def call(method, path):
    request = urllib.request.Request(target_url + path, method=method)
    if auth:
        request.add_header("Authorization", auth)
    try:
        with opener.open(request) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"{}")


failures = 0
for index, doc_id, parent, item_type, skill in ITEMS:
    path = "/" + index + "/_doc/" + urllib.parse.quote(doc_id, safe="")
    status, doc = call("GET", path)
    if status == 404:
        print(index, parent, item_type, skill, "ja nao existe")
        continue
    source = doc.get("_source", {})
    expected = {"parent": parent, "type": item_type, "skill": skill}
    if any(source.get(key) != value for key, value in expected.items()):
        print(index, doc_id, "NAO CONFERE:", source)
        failures += 1
        continue
    if not write:
        print(index, parent, item_type, skill, "seria apagado")
        continue
    status, answer = call("DELETE", path + "?refresh=true")
    print(index, parent, item_type, skill, "apagado" if status == 200 else f"falha {status}")
    failures += 0 if status == 200 else 1
print("OK" if failures == 0 else "FALHAS: " + str(failures))
print("cache das entidades: 1 h; rode o 101 em seguida para recalcular as pizzas")
sys.exit(1 if failures else 0)
