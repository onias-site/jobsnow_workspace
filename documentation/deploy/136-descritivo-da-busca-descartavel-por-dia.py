# Descritivo da busca de curriculos descartavel por dia (2026-11-28): vis_resume_filter_description ganha
# @CcpEntityDisposable(daily). O texto dura 24 horas depois do ultimo save (pela copia em jn_disposable_record) e sai no
# expurgo de hora em hora; no dia seguinte os mesmos filtros podem receber texto de novo (o /salvarVaga e as vagas dos
# grupos so sao recusados enquanto o texto dos filtros dura).
#
# O que faz, para cada documento de vis_resume_filter_description ainda com o id antigo (SHA-1 de "email, filterId"):
#   1. grava o mesmo _source com o id do periodo: SHA-1 de "27112026, <id antigo>" (JnDisposableEntity.calculateId);
#   2. grava a copia em jn_disposable_record (id = SHA-1 de "vis_resume_filter_description, {email, filterId}"), como se
#      o texto tivesse sido gravado em 27/11/2026 as 22:00 (America/Sao_Paulo): trueTimestamp = 22:00 de 27/11,
#      timestamp = 22:00 de 28/11 (um dia depois), format ddMMyyyy;
#   3. poe o documento do periodo no grupo de expurgo do jn_grouper (parent jn_virtual_disposable_record_to_purge, child
#      jn_disposable_record), com timestamp = fim do periodo (00:00 de 28/11);
#   4. apaga o documento do id antigo.
# A hora da gravacao nao e conhecida (a entidade nao guarda data), por isso 22:00 de 27/11, por decisao do usuario.
# Consequencia: os textos migrados deixam de valer as 22:00 de 28/11/2026 e saem no expurgo seguinte.
# Idempotente: rodar de novo nao acha mais id antigo e so confere.
#
# Ordem: rodar JUNTO com o deploy da vis, dos consumidores e do cron (o codigo novo procura pelo id do periodo; o antigo,
# pelo id sem periodo). Depois, publicar nova revisao das APIs e reiniciar o PM2, ou esperar 1 hora (cache).
#
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python 136-descritivo-da-busca-descartavel-por-dia.py [url do destino]
#      (sem url: o tunel de producao, http://127.0.0.1:9210; para o ES local, http://localhost:9200)
import datetime
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request

target = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:9210"
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

INDEX = "vis_resume_filter_description"
PERIOD = "27112026"
BRT = datetime.timezone(datetime.timedelta(hours=-3))
WRITTEN_AT = datetime.datetime(2026, 11, 27, 22, 0, 0, tzinfo=BRT)
EXPIRATION = WRITTEN_AT + datetime.timedelta(days=1)
END_OF_THE_PERIOD = datetime.datetime(2026, 11, 28, 0, 0, 0, tzinfo=BRT)
PARENT_NAME = "jn_virtual_disposable_record_to_purge"
COPY_NAME = "jn_disposable_record"


def millis(moment):
    return int(moment.timestamp() * 1000)


def java_hash(text):
    # CcpHashDecorator.asString: BigInteger com sinal em base 16, nunca hexdigest
    return format(int.from_bytes(hashlib.sha1(text.encode("utf-8")).digest(), "big", signed=True), "x")


def ugly(value):
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def call(method, path, body=None, ndjson=None):
    data = None
    headers = {"Content-Type": "application/json"}
    if body is not None:
        data = json.dumps(body).encode()
    if ndjson is not None:
        data = ("\n".join(ugly(line) for line in ndjson) + "\n").encode("utf-8")
        headers["Content-Type"] = "application/x-ndjson"
    request = urllib.request.Request(target + path, data=data, method=method, headers=headers)
    auth = os.environ.get("ES_DESTINO_AUTH", "")
    if auth:
        request.add_header("Authorization", auth)
    try:
        with opener.open(request) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"{}")


def read_all():
    status, answer = call("POST", "/" + INDEX + "/_search?scroll=1m", {"size": 1000, "query": {"match_all": {}}})
    if status != 200:
        print("leitura falhou", status, answer)
        sys.exit(1)
    hits = []
    while answer["hits"]["hits"]:
        hits += answer["hits"]["hits"]
        status, answer = call("POST", "/_search/scroll", {"scroll": "1m", "scroll_id": answer["_scroll_id"]})
    return hits


written_at = millis(WRITTEN_AT)
expiration = millis(EXPIRATION)
end_of_the_period = millis(END_OF_THE_PERIOD)
expiration_date = EXPIRATION.strftime("%d/%m/%Y %H:%M:%S.000")

documents = read_all()
print(INDEX, "documentos:", len(documents))
lines = []
moved = 0
for document in documents:
    source = document["_source"]
    old_id = java_hash(source["email"] + ", " + source["filterId"])
    if document["_id"] != old_id:
        continue
    new_id = java_hash(PERIOD + ", " + old_id)
    primary_key = ugly({"email": source["email"], "filterId": source["filterId"]})
    copy_id = java_hash(INDEX + ", " + primary_key)
    copy = {"entity": INDEX, "id": primary_key, "format": "ddMMyyyy", "timestamp": expiration,
            "trueTimestamp": written_at, "json": source, "date": expiration_date}
    child = ugly({"entity": INDEX, "id": new_id, "timestamp": end_of_the_period})
    group_id = java_hash(COPY_NAME + ", " + copy_id + ", " + PARENT_NAME)
    group = {"parentId": copy_id, "parentName": PARENT_NAME, "childName": COPY_NAME,
             "parentJson": {"entity": INDEX, "id": primary_key}, "child": [child], "childCount": 1}
    lines += [{"index": {"_index": INDEX, "_id": new_id}}, source,
              {"index": {"_index": COPY_NAME, "_id": copy_id}}, copy,
              {"update": {"_index": "jn_grouper", "_id": group_id}},
              {"script": {"lang": "painless",
                          "source": "if (!ctx._source.child.contains(params.c)) { ctx._source.child.add(params.c); ctx._source.childCount = ctx._source.child.size(); } else { ctx.op = 'noop'; }",
                          "params": {"c": child}}, "upsert": group},
              {"delete": {"_index": INDEX, "_id": old_id}}]
    moved += 1

if lines:
    for start in range(0, len(lines), 1000):
        status, answer = call("POST", "/_bulk?refresh=true", ndjson=lines[start:start + 1000])
        errors = [item for item in answer.get("items", []) if list(item.values())[0].get("error")]
        if status != 200 or errors:
            print("bulk falhou", status, errors[:5])
            sys.exit(1)
print("movidos para o periodo", PERIOD + ":", moved)

remaining = [d for d in read_all() if d["_id"] == java_hash(d["_source"]["email"] + ", " + d["_source"]["filterId"])]
status, copies = call("POST", "/" + COPY_NAME + "/_count", {"query": {"term": {"entity": INDEX}}})
print("restam com id antigo:", len(remaining), "| copias em", COPY_NAME + ":", copies.get("count"))
if remaining:
    sys.exit(1)
