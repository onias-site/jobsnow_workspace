# Campos de texto como text (2026-11-15): por ordem do usuario, os campos message, description, contact, comment,
# explanation, supportResponse, alias, lastPosition, statisSkillLineChart, notAllowedCompany, ip, source, title, date,
# insertionDate e yearMonth sao text em toda entidade. Nos mapeamentos locais (ccp_rest-api-tests_jobsnow/documentation/
# <centro>/database/elasticsearch/scripts/entities/create) 22 deles, em 16 entidades, estavam como keyword. Na mesma
# data o usuario acrescentou os campos largos que restavam como keyword: skill de vis_telegram_position (ate 5.000
# letras), url das tres jn_http_api_* (ate 500) e emails de vis_resume_linkedin (stackTrace e subject ja eram text).
# As gemeas usam o mapeamento da principal, entao sao 26 indices em producao (INDEXES abaixo). Nenhuma consulta do
# codigo ordena, agrega ou filtra por valor exato nesses campos (conferido em 2026-11-15), entao o codigo nao depende
# do tipo.
# O ES nao troca o tipo de um campo no lugar, entao cada indice e reindexado (mesmo roteiro do script 82):
#   1. confere que ha no repositorio de snapshots um snapshot SUCCESS das ultimas 36 h com o indice (sem ele, nao mexe);
#   2. cria <indice>_reindexacao_84 com o mapeamento do proprio indice e os campos = text, e copia os documentos para ele;
#   3. apaga o indice, cria-o de novo com o mapeamento novo (mesmos shards, replicas e aliases) e copia os documentos de
#      volta;
#   4. confere as contagens e os tipos, e apaga o indice temporario.
# Um indice cujos campos ja sao text e pulado (idempotente); um indice que nao existe no destino e so avisado. Se falhar
# entre os passos 3 e 4, os documentos estao no temporario: rodar de novo nao apaga o temporario se o indice estiver
# vazio (sai com 1 e mostra o que fazer). As copias rodam como tarefa do ES (wait_for_completion=false) e o script
# acompanha a tarefa, para os indices grandes (vis_resume, vis_telegram_position) nao esbarrarem em timeout de HTTP.
# Roda com os consumidores PARADOS (pm2 stop all na VM) e fora do horario do processo diario (22h): as escritas
# assincronas ficam no Pub/Sub ate eles voltarem; a leitura das APIs acha cada indice vazio por alguns segundos.
# Pode rodar antes ou depois do deploy. Depois, pm2 start all.
# Uso: powershell -File com-tunel-de-producao.ps1 -Script 84-campos-largos-como-text.py
#      ou: ES_DESTINO_AUTH=<valor> python 84-campos-largos-como-text.py [destino] [repositorio] [--sem-snapshot]
#      --sem-snapshot so para o ES local (descartavel): pula o passo 1.
# Imprime so contagens e tipos.
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.request

INDEXES = {
    "jn_email_suppressed": ["ip"],
    "js_contact_us": ["date"],
    "js_contact_us_solved": ["date"],
    "js_login_answers": ["insertionDate"],
    "vis_invalid_linkedin_report": ["date"],
    "vis_invalid_linkedin_report_solved": ["date"],
    "vis_position": ["title", "date"],
    "vis_inactive_position": ["title", "date"],
    "vis_recruiter": ["source"],
    "vis_inactive_recruiter": ["source"],
    "vis_recruiter_queue_cursor": ["lastPosition"],
    "vis_resume": ["notAllowedCompany", "insertionDate"],
    "vis_inactive_resume": ["notAllowedCompany", "insertionDate"],
    "vis_resume_message": ["message"],
    "vis_resume_restriction": ["message"],
    "vis_skill_fix_hierarchy_pending": ["date"],
    "vis_skill_pending": ["date"],
    "vis_statis_skill_line_chart": ["yearMonth"],
    "vis_statis_skill_pie_chart": ["yearMonth"],
    "vis_telegram_position": ["contact", "statisSkillLineChart", "yearMonth", "skill"],
    "jn_http_api_error_client": ["url"],
    "jn_http_api_error_server": ["url"],
    "jn_http_api_retry_send_request": ["url"],
    "vis_resume_linkedin": ["emails"],
    "vis_viewed_resume": ["alias", "date", "insertionDate"],
    "vis_inactive_viewed_resume": ["alias", "date", "insertionDate"],
}
SUFFIX = "_reindexacao_84"
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
    current = types_of(index, fields)
    missing = [field for field, kind in current.items() if not kind]
    if missing:
        print(f"{index}\tcampos sem mapeamento no destino: {', '.join(missing)}\tnada feito")
        return False
    pending = [field for field, kind in current.items() if kind != "text"]
    if not pending:
        print(f"{index}\t{', '.join(fields)} ja sao text\tpulado")
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
        mapping["properties"][field] = {"type": "text"}
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
    final = types_of(index, fields)
    if any(kind != "text" for kind in final.values()):
        print(f"{index}\ttipos depois da copia nao conferem: {final}: os documentos estao em {temporary}")
        return False
    call("DELETE", "/" + temporary)
    changes = ", ".join(f"{field}: {current[field]} -> {final[field]}" for field in pending)
    print(f"{index}\tdocumentos {before} -> {after}\t{changes}")
    return True


results = [reindex(index, fields) for index, fields in INDEXES.items()]
print("cache das entidades: 1 h; publique nova revisao de vis e js e reinicie os consumidores (pm2 start all), "
      "ou espere a hora passar")
sys.exit(0 if all(results) else 1)
