# comment das visualizacoes como text (2026-11-15): o campo comment de vis_viewed_resume e da gemea
# vis_inactive_viewed_resume (por que a visualizacao foi para a gemea, texto livre de 10 a 500 letras) foi criado como
# keyword. Regra do usuario: campo string sem allowedValues e text, nao keyword. O ES nao troca o tipo de um campo no
# lugar, entao cada indice e reindexado:
#   1. confere que ha no repositorio de snapshots um snapshot SUCCESS das ultimas 36 h com o indice (sem ele, nao mexe);
#   2. cria <indice>_reindexacao_82 com o mapeamento do proprio indice e comment = text, e copia os documentos para ele;
#   3. apaga o indice, cria-o de novo com o mapeamento novo (mesmos shards e replicas) e copia os documentos de volta;
#   4. confere as contagens e o tipo do campo, e apaga o indice temporario.
# Um indice cujo comment ja e text e pulado (idempotente). Se falhar entre os passos 3 e 4, os documentos estao no
# temporario: rodar de novo nao apaga o temporario se o indice estiver vazio (sai com 1 e mostra o que fazer).
# Roda com os consumidores PARADOS (pm2 stop all na VM): as escritas de vis_viewed_resume vao pela fila
# (@CcpEntityAsyncWriter) e ficam no Pub/Sub ate eles voltarem; a leitura da API vis acha o indice vazio por alguns
# segundos. Pode rodar antes ou depois do deploy (o codigo nao depende do tipo do campo). Depois, pm2 start all.
# Uso: powershell -File com-tunel-de-producao.ps1 -Script 82-comment-das-visualizacoes-como-text.py
#      ou: ES_DESTINO_AUTH=<valor> python 82-comment-das-visualizacoes-como-text.py [destino] [repositorio] [--sem-snapshot]
#      --sem-snapshot so para o ES local (descartavel): pula o passo 1.
# Imprime so contagens.
import datetime
import json
import os
import sys
import urllib.error
import urllib.request

INDEXES = ("vis_viewed_resume", "vis_inactive_viewed_resume")
FIELD = "comment"
SUFFIX = "_reindexacao_82"

arguments = [argument for argument in sys.argv[1:] if not argument.startswith("--")]
skip_snapshot = "--sem-snapshot" in sys.argv[1:]
target_url = arguments[0].rstrip("/") if arguments else "http://127.0.0.1:9210"
repository = arguments[1] if len(arguments) > 1 else "jobsnow-backup"
auth = os.environ.get("ES_DESTINO_AUTH", "")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def call(method, path, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(target_url + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if auth:
        request.add_header("Authorization", auth)
    try:
        with opener.open(request) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"{}")


def count(index):
    call("POST", "/" + index + "/_refresh")
    status, answer = call("GET", "/" + index + "/_count")
    return answer.get("count", -1) if status == 200 else -1


def mapping_of(index):
    status, answer = call("GET", "/" + index + "/_mapping")
    if status != 200:
        return None
    return answer[index]["mappings"]


def field_type(index):
    mapping = mapping_of(index) or {}
    return mapping.get("properties", {}).get(FIELD, {}).get("type", "")


def shards_and_replicas(index):
    status, answer = call("GET", "/" + index + "/_settings")
    settings = answer[index]["settings"]["index"]
    return {"number_of_shards": settings["number_of_shards"], "number_of_replicas": settings["number_of_replicas"]}


def has_recent_snapshot(index):
    status, answer = call("GET", "/_snapshot/" + repository + "/_all")
    snapshots = answer.get("snapshots", []) if status == 200 else []
    limit = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=36)).timestamp() * 1000
    recent = [s for s in snapshots if s.get("state") == "SUCCESS" and index in s.get("indices", [])
              and s.get("start_time_in_millis", 0) >= limit]
    return recent[-1]["snapshot"] if recent else ""


def copy(source, destination):
    status, answer = call("POST", "/_reindex?refresh=true&wait_for_completion=true",
                          {"source": {"index": source}, "dest": {"index": destination}})
    failures = answer.get("failures", [])
    return status == 200 and not failures, answer.get("total", 0)


def create(index, mapping, settings):
    status, answer = call("PUT", "/" + index, {"settings": settings, "mappings": mapping})
    return status == 200, answer.get("error", {}).get("type")


def reindex(index):
    temporary = index + SUFFIX
    current_type = field_type(index)
    if current_type == "text":
        print(f"{index}\t{FIELD} ja e text\tpulado")
        return True
    if count(temporary) >= 0:
        if count(index) <= 0:
            print(f"{index}\to temporario {temporary} existe e o indice esta vazio ou sumiu: copie de volta a mao "
                  f"(POST /_reindex de {temporary} para {index}) e rode de novo")
            return False
        call("DELETE", "/" + temporary)
    if not skip_snapshot:
        snapshot = has_recent_snapshot(index)
        if not snapshot:
            print(f"{index}\tsem snapshot SUCCESS das ultimas 36 h em {repository}: nada feito")
            return False
        print(f"{index}\tsnapshot {snapshot}")
    before = count(index)
    mapping = mapping_of(index)
    mapping["properties"][FIELD] = {"type": "text"}
    settings = shards_and_replicas(index)
    created, error = create(temporary, mapping, settings)
    if not created:
        print(f"{index}\tfalha ao criar o temporario: {error}")
        return False
    copied, total = copy(index, temporary)
    if not copied or count(temporary) != before:
        print(f"{index}\tfalha ao copiar para o temporario ({total} de {before}): indice mantido")
        call("DELETE", "/" + temporary)
        return False
    status, answer = call("DELETE", "/" + index)
    if status != 200:
        print(f"{index}\tfalha ao apagar o indice: {answer.get('error', {}).get('type')}")
        return False
    created, error = create(index, mapping, settings)
    if not created:
        print(f"{index}\tfalha ao recriar o indice ({error}): os documentos estao em {temporary}")
        return False
    copied, total = copy(temporary, index)
    after = count(index)
    if not copied or after != before:
        print(f"{index}\tfalha ao copiar de volta ({after} de {before}): os documentos estao em {temporary}")
        return False
    call("DELETE", "/" + temporary)
    print(f"{index}\tdocumentos {before} -> {after}\t{FIELD}: {current_type} -> {field_type(index)}")
    return True


results = [reindex(index) for index in INDEXES]
print("cache das entidades: 1 h; publique nova revisao da vis e reinicie os consumidores (pm2 start all), ou espere a hora passar")
sys.exit(0 if all(results) else 1)
