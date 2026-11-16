"""So leitura: le do Elasticsearch 7.4 do legado (porta 9201) todos os candidatos do indice profissionais2, so com os
campos que o convite usa (VisBusinessBuildLegacyCandidateTable.Legacy; do arquivo do curriculo, so o texto curriculo.t),
e grava num arquivo JSON {"candidates": [...]} para o ReinviteLegacyCandidates.java.

Uso: python -I ler-candidatos-do-legado.py <arquivo de saida> [url do legado, padrao http://127.0.0.1:9201]
Nenhum e-mail ou valor de registro e impresso, so a contagem.
"""
import json
import sys
import urllib.request

FIELDS = ["id", "tipoVaga", "ddd", "homeoffice", "experiencia", "disponibilidade", "pretensaoClt", "pretensaoPj",
          "pretensaoNegociavel", "pcd", "profissaoDesejada", "ultimaProfissao", "curriculo.t"]

output = sys.argv[1]
legacy = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:9201"
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def call(method, path, body):
    request = urllib.request.Request(legacy + path, data=json.dumps(body).encode(), method=method)
    request.add_header("Content-Type", "application/json")
    with opener.open(request, timeout=300) as response:
        return json.loads(response.read())


candidates = []
page = call("POST", "/profissionais2/_search?scroll=5m", {"size": 200, "_source": FIELDS, "query": {"match_all": {}}})
while page["hits"]["hits"]:
    candidates.extend(hit["_source"] for hit in page["hits"]["hits"])
    page = call("POST", "/_search/scroll", {"scroll": "5m", "scroll_id": page["_scroll_id"]})

with open(output, "w", encoding="utf-8") as file:
    json.dump({"candidates": candidates}, file, ensure_ascii=False)
print("candidatos do legado lidos:", len(candidates))
