# Dicionario de skills em memoria: cria no destino o indice vis_skill_dictionary (se faltar) e grava o seu unico registro
# (dictionaryName = skills) com a versao de agora e os ids de todos os documentos de vis_skill do proprio destino.
# Cada processo da API vis le esse registro por id a cada leitura de skills de um texto (/skills/fromText) e rele as
# skills por id quando a versao muda; cada save de skill grava uma versao nova (VisBusinessUpdateSkillDictionary).
# Rodar antes de publicar a API vis que usa o dicionario: sem o registro, /skills/fromText responde 404.
# Rodar de novo e seguro: regrava o registro com os ids atuais e uma versao nova. As APIs releem as skills quando o cache
# da entidade (1 hora, no Memorystore) soltar o registro antigo, ou antes, ao fim da hora de vida da copia em memoria.
# O id do registro e o SHA-1 da chave primaria, como em CcpEntity.calculateId (hexadecimal com sinal).
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python 24-dicionario-de-skills.py [url do destino]
#      (sem url: o tunel de producao, http://127.0.0.1:9210; para o ES local, http://localhost:9200)
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
MAPPING = os.path.join(HERE, "..", "..", "ccp_rest-api-tests_jobsnow", "documentation", "vis", "database",
                       "elasticsearch", "scripts", "entities", "create", "vis_skill_dictionary")
INDEX = "vis_skill_dictionary"
DICTIONARY_NAME = "skills"

target_url = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:9210"
auth = os.environ.get("ES_DESTINO_AUTH", "")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def call(method, path, body=None, missing_ok=False):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(target_url + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if auth:
        request.add_header("Authorization", auth)
    try:
        with opener.open(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8") or "null")
    except urllib.error.HTTPError as error:
        if missing_ok and error.code == 404:
            return None
        raise SystemExit("%s %s %s: %s" % (method, path, error.code, error.read().decode("utf-8", "replace")[:600]))


print("destino:", call("GET", "/")["cluster_name"])

if call("GET", "/" + INDEX, missing_ok=True) is None:
    with open(MAPPING, encoding="utf-8") as mapping_file:
        mapping = json.load(mapping_file)
    call("PUT", "/" + INDEX, mapping)
    print("indice criado:", INDEX)

skill_ids = []
page = call("POST", "/vis_skill/_search?scroll=2m", {"size": 1000, "_source": False, "query": {"match_all": {}}})
while page["hits"]["hits"]:
    skill_ids.extend(hit["_id"] for hit in page["hits"]["hits"])
    page = call("POST", "/_search/scroll", {"scroll": "2m", "scroll_id": page["_scroll_id"]})
if not skill_ids:
    raise SystemExit("vis_skill vazio no destino: nada gravado")

digest = hashlib.sha1(DICTIONARY_NAME.encode("utf-8")).digest()
# CcpHashDecorator: new BigInteger(digest).toString(16), com sinal e sem zeros a esquerda
record_id = format(int.from_bytes(digest, "big", signed=True), "x")
record = {"dictionaryName": DICTIONARY_NAME, "version": int(time.time() * 1000), "skillIds": sorted(skill_ids)}
result = call("PUT", "/%s/_doc/%s?refresh=true" % (INDEX, record_id), record)
print("registro %s: %s, %d skills, versao %d" % (record_id, result["result"], len(skill_ids), record["version"]))
