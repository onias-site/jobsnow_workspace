# Objetos livres sem "dynamic": "true" (2026-11-20, regra NDM do CLAUDE.md): por ordem do usuario, nenhum mapeamento
# tem mais "dynamic": "true", porque cada chave gravada num objeto assim vira um campo novo e o mapeamento cresce com
# os dados (59 subcampos em jn_disposable_record.json, 34 em jb_bot_command_step_session.json). Os 9 objetos abaixo
# passam a "type": "object", "enabled": false: o objeto inteiro continua no _source (a leitura devolve o mesmo JSON) e
# nenhum campo e criado para ele. Nenhuma consulta do codigo usa um subcampo deles (conferido em 2026-11-20), entao o
# codigo nao depende da indexacao. vis_inactive_position (gemea) usa o mapeamento de vis_position.
# O ES nao troca o mapeamento de um objeto no lugar, entao cada indice e reindexado (mesmo roteiro do script 84):
#   1. confere que ha no repositorio de snapshots um snapshot SUCCESS das ultimas 36 h com o indice (sem ele, nao mexe);
#   2. cria <indice>_reindexacao_99 com o mapeamento do proprio indice e os objetos = enabled false, e copia os
#      documentos para ele;
#   3. apaga o indice, cria-o de novo com o mapeamento novo (mesmos shards, replicas e aliases) e copia de volta;
#   4. confere as contagens e os mapeamentos, e apaga o indice temporario.
# Um indice cujos objetos ja sao enabled false e pulado (idempotente); um indice que nao existe no destino e so avisado.
# Se falhar entre os passos 3 e 4, os documentos estao no temporario: rodar de novo nao apaga o temporario se o indice
# estiver vazio (sai com 1 e mostra o que fazer). As copias rodam como tarefa do ES e o script acompanha a tarefa.
# Roda com os consumidores PARADOS (pm2 stop all na VM) e longe dos jobs (backup 00:10, reenvio do token de hora em hora,
# curriculos 10:00): as escritas assincronas ficam no Pub/Sub ate eles voltarem; a leitura das APIs acha cada indice
# vazio por alguns segundos. Nao depende de deploy. Depois, pm2 start all.
# Uso: powershell -File com-tunel-de-producao.ps1 -Script 99-objetos-livres-sem-dynamic.py
#      ou: ES_DESTINO_AUTH=<valor> python 99-objetos-livres-sem-dynamic.py [destino] [repositorio] [--sem-snapshot]
#      --sem-snapshot so para o ES local (descartavel): pula o passo 1.
# Imprime so contagens e mapeamentos.
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.request

INDEXES = {
    "jb_bot_command_step_session": ["json"],
    "jn_disposable_record": ["json"],
    "jn_email_parameters_to_send": ["moreParameters"],
    "jn_http_api_error_client": ["headers"],
    "jn_http_api_error_server": ["headers"],
    "jn_http_api_retry_send_request": ["headers"],
    "jn_instant_messenger_parameters_to_send": ["moreParameters"],
    "vis_position": ["desiredSkill"],
    "vis_inactive_position": ["desiredSkill"],
}
NEW_DEFINITION = {"type": "object", "enabled": False}
SUFFIX = "_reindexacao_99"
COPIED_SETTINGS = ("number_of_shards", "number_of_replicas", "max_result_window", "refresh_interval")

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


def kind_of(definition):
    if definition is None:
        return ""
    if definition.get("enabled") is False:
        return "enabled false"
    if str(definition.get("dynamic", "")).lower() == "true":
        return "dynamic true (%d subcampos)" % len(definition.get("properties", {}))
    return definition.get("type", "object")


def kinds_of(index, fields):
    properties = (mapping_of(index) or {}).get("properties", {})
    return {field: kind_of(properties.get(field)) for field in fields}


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


def copy(source, destination):
    status, answer = call("POST", "/_reindex?refresh=true&wait_for_completion=false",
                          {"source": {"index": source}, "dest": {"index": destination}})
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


def reindex(index, fields):
    temporary = index + SUFFIX
    if mapping_of(index) is None:
        print(f"{index}\tnao existe no destino\tpulado")
        return True
    current = kinds_of(index, fields)
    missing = [field for field, kind in current.items() if not kind]
    if missing:
        print(f"{index}\tcampos sem mapeamento no destino: {', '.join(missing)}\tnada feito")
        return False
    pending = [field for field, kind in current.items() if kind != "enabled false"]
    if not pending:
        print(f"{index}\t{', '.join(fields)} ja sao enabled false\tpulado")
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
    for field in pending:
        mapping["properties"][field] = dict(NEW_DEFINITION)
    settings = settings_of(index)
    aliases = aliases_of(index)
    created, error = create(temporary, mapping, settings, {})
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
    created, error = create(index, mapping, settings, aliases)
    if not created:
        print(f"{index}\tfalha ao recriar o indice ({error}): os documentos estao em {temporary}")
        return False
    copied, total = copy(temporary, index)
    after = count(index)
    if not copied or after != before:
        print(f"{index}\tfalha ao copiar de volta ({after} de {before}): os documentos estao em {temporary}")
        return False
    final = kinds_of(index, fields)
    if any(kind != "enabled false" for kind in final.values()):
        print(f"{index}\tmapeamento depois da copia nao confere: {final}: os documentos estao em {temporary}")
        return False
    call("DELETE", "/" + temporary)
    changes = ", ".join(f"{field}: {current[field]} -> {final[field]}" for field in pending)
    print(f"{index}\tdocumentos {before} -> {after}\t{changes}")
    return True


results = [reindex(index, fields) for index, fields in INDEXES.items()]
print("cache das entidades: 1 h; reinicie os consumidores (pm2 start all) e, se quiser o efeito ja, publique nova "
      "revisao de vis e js, ou espere a hora passar")
sys.exit(0 if all(results) else 1)
