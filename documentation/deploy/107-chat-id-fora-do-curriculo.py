# chatId fora de vis_resume (2026-11-21): por ordem do usuario, o campo chatId sai de VisEntityResume. Ele guardou o chat
# do dono no bot do usuario de 2026-11-12 a 2026-11-13; desde entao o chat de cada e-mail fica em jn_instant_messenger_user
# e ninguem le nem grava o campo. Em producao, em 2026-11-21, so 1 documento de vis_inactive_resume ainda o tinha: sem
# este script, a reativacao dele gravaria um campo que o mapeamento strict de vis_resume nao tem mais.
# O ES nao retira um campo do mapeamento no lugar, entao vis_resume e a gemea vis_inactive_resume sao reindexados (mesmo
# roteiro dos scripts 82, 84 e 91):
#   1. confere que ha no repositorio de snapshots um snapshot SUCCESS das ultimas 36 h com o indice (sem ele, nao mexe);
#   2. cria <indice>_reindexacao_107 com o mapeamento do proprio indice sem chatId e copia os documentos sem o campo;
#   3. apaga o indice, cria-o de novo com o mapeamento novo (mesmos shards, replicas e aliases) e copia de volta;
#   4. confere as contagens, que o campo sumiu do mapeamento e de todo documento, e apaga o indice temporario.
# Idempotente: indice sem chatId no mapeamento e sem documento com o campo e pulado.
# Roda com os consumidores PARADOS (pm2 stop all na VM) e fora do horario do processo diario. Depois, pm2 start all.
# Uso: powershell -File com-tunel-de-producao.ps1 -Script 107-chat-id-fora-do-curriculo.py
#      ou: ES_DESTINO_AUTH=<valor> python 107-chat-id-fora-do-curriculo.py [destino] [repositorio] [--sem-snapshot]
#      --sem-snapshot so para o ES local (descartavel): pula o passo 1.
# Imprime so contagens.
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.request

INDEXES = ["vis_resume", "vis_inactive_resume"]
FIELD = "chatId"
SUFFIX = "_reindexacao_107"
COPIED_SETTINGS = ("number_of_shards", "number_of_replicas", "max_result_window", "refresh_interval")
PAINLESS = "ctx._source.remove('" + FIELD + "')"

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


def types_of(index, fields):
    properties = (mapping_of(index) or {}).get("properties", {})
    return {field: properties.get(field, {}).get("type", "") for field in fields}


def settings_of(index):
    status, answer = call("GET", "/" + index + "/_settings")
    settings = answer[index]["settings"]["index"]
    return {name: settings[name] for name in COPIED_SETTINGS if name in settings}


def aliases_of(index):
    status, answer = call("GET", "/" + index + "/_alias")
    return answer.get(index, {}).get("aliases", {}) if status == 200 else {}


def has_recent_snapshot(index):
    status, answer = call("GET", "/_snapshot/" + repository + "/_all")
    snapshots = answer.get("snapshots", []) if status == 200 else []
    limit = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=36)).timestamp() * 1000
    recent = [s for s in snapshots if s.get("state") == "SUCCESS" and index in s.get("indices", [])
              and s.get("start_time_in_millis", 0) >= limit]
    return recent[-1]["snapshot"] if recent else ""


def copy(source, destination, painless=None):
    request = {"source": {"index": source}, "dest": {"index": destination}}
    if painless:
        request["script"] = {"lang": "painless", "source": painless}
    status, answer = call("POST", "/_reindex?refresh=true&wait_for_completion=false", request)
    task = answer.get("task")
    if status != 200 or not task:
        return False, 0
    while True:
        status, answer = call("GET", "/_tasks/" + task)
        if answer.get("completed"):
            break
        time.sleep(2)
    response = answer.get("response", {})
    failures = response.get("failures", [])
    call("DELETE", "/.tasks/_doc/" + task)
    return not failures and "error" not in answer, response.get("total", 0)


def create(index, mapping, settings, aliases):
    status, answer = call("PUT", "/" + index, {"settings": settings, "mappings": mapping, "aliases": aliases})
    return status == 200, answer.get("error", {}).get("type")


def with_field(index):
    call("POST", "/" + index + "/_refresh")
    status, answer = call("POST", "/" + index + "/_count", {"query": {"exists": {"field": FIELD}}})
    return answer.get("count", -1) if status == 200 else -1


def reindex(index):
    temporary = index + SUFFIX
    mapping = mapping_of(index)
    if mapping is None:
        print(f"{index}	nao existe no destino	pulado")
        return True
    in_mapping = FIELD in mapping.get("properties", {})
    documents_with_field = with_field(index)
    if not in_mapping and documents_with_field <= 0:
        print(f"{index}	{FIELD} ja fora do mapeamento e dos documentos	pulado")
        return True
    if count(temporary) >= 0:
        if count(index) <= 0:
            print(f"{index}	o temporario {temporary} existe e o indice esta vazio ou sumiu: copie de volta a mao "
                  f"(POST /_reindex de {temporary} para {index}) e rode de novo")
            return False
        call("DELETE", "/" + temporary)
    if not skip_snapshot:
        snapshot = has_recent_snapshot(index)
        if not snapshot:
            print(f"{index}	sem snapshot SUCCESS das ultimas 36 h em {repository}: nada feito")
            return False
        print(f"{index}	snapshot {snapshot}")
    before = count(index)
    mapping["properties"].pop(FIELD, None)
    settings = settings_of(index)
    aliases = aliases_of(index)
    created, error = create(temporary, mapping, settings, {})
    if not created:
        print(f"{index}	falha ao criar o temporario: {error}")
        return False
    copied, total = copy(index, temporary, PAINLESS)
    if not copied or count(temporary) != before or with_field(temporary) != 0:
        print(f"{index}	falha ao copiar para o temporario ({total} de {before}): indice mantido")
        call("DELETE", "/" + temporary)
        return False
    status, answer = call("DELETE", "/" + index)
    if status != 200:
        print(f"{index}	falha ao apagar o indice: {answer.get('error', {}).get('type')}")
        return False
    created, error = create(index, mapping, settings, aliases)
    if not created:
        print(f"{index}	falha ao recriar o indice ({error}): os documentos estao em {temporary}")
        return False
    copied, total = copy(temporary, index)
    after = count(index)
    if not copied or after != before:
        print(f"{index}	falha ao copiar de volta ({after} de {before}): os documentos estao em {temporary}")
        return False
    if FIELD in (mapping_of(index) or {}).get("properties", {}) or with_field(index) != 0:
        print(f"{index}	{FIELD} continua no indice: os documentos estao em {temporary}")
        return False
    call("DELETE", "/" + temporary)
    print(f"{index}	documentos {before} -> {after}	{documents_with_field} com {FIELD} antes, 0 depois; "
          f"{FIELD} {'retirado do' if in_mapping else 'ja fora do'} mapeamento")
    return True


results = [reindex(index) for index in INDEXES]
print("cache das entidades: 1 h; publique nova revisao de vis e js e reinicie os consumidores (pm2 start all), "
      "ou espere a hora passar")
sys.exit(0 if all(results) else 1)
