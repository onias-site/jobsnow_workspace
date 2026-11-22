# Campos novos da vaga (2026-11-21): por ordem do usuario, VisEntityPosition passa a ter so os campos clt, disponibility,
# ddd, recruiter e title (chave primaria; recruiter = sha1 do e-mail do recrutador), resumeType, seniority, hash, skill, spokenLanguage, negotiableClaim,
# pcd, pj, temporallyJobTime, travel, title, expiration, description, sort, mustSendInGroups, mustSendToResumes,
# frequencyType e contact. clt, pj e expiration viram objetos {min, max}; sort e contact, listas de objetos. Tipo de campo
# nao muda no lugar, e o mapeamento strict de producao recusaria toda escrita da vaga nova.
# Como nenhuma vaga foi gravada (o front nao publica vagas), vis_position e a gemea vis_inactive_position sao apagadas e
# criadas de novo com o mapeamento de
# ccp_rest-api-tests_jobsnow/documentation/vis/database/elasticsearch/scripts/entities/create/vis_position
# (mesmos shards, replicas e aliases). Indice com documento NAO e tocado: o script para e diz quantos ha (as vagas
# antigas nao cabem no formato novo; decidir com o usuario antes).
# Idempotente: indice que ja tem o mapeamento novo e pulado; indice que nao existe e criado.
# Roda antes do deploy de vis, js e dos consumidores.
# Uso: powershell -File com-tunel-de-producao.ps1 -Script 109-campos-novos-da-vaga.py
#      ou: ES_DESTINO_AUTH=<valor> python 109-campos-novos-da-vaga.py [destino]
# Imprime so contagens.
import json
import os
import sys
import urllib.error
import urllib.request

INDEXES = ["vis_position", "vis_inactive_position"]
COPIED_SETTINGS = ("number_of_shards", "number_of_replicas", "max_result_window", "refresh_interval")
HERE = os.path.dirname(os.path.abspath(__file__))
MAPPING_FILE = os.path.join(HERE, "..", "..", "ccp_rest-api-tests_jobsnow", "documentation", "vis", "database",
                            "elasticsearch", "scripts", "entities", "create", "vis_position")

arguments = [argument for argument in sys.argv[1:] if not argument.startswith("--")]
target_url = arguments[0].rstrip("/") if arguments else "http://127.0.0.1:9210"
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
    return answer[index]["mappings"] if status == 200 else None


def settings_of(index):
    status, answer = call("GET", "/" + index + "/_settings")
    settings = answer[index]["settings"]["index"]
    return {name: settings[name] for name in COPIED_SETTINGS if name in settings}


def aliases_of(index):
    status, answer = call("GET", "/" + index + "/_alias")
    return answer.get(index, {}).get("aliases", {}) if status == 200 else {}


def create(index, mapping, settings, aliases):
    status, answer = call("PUT", "/" + index, {"settings": settings, "mappings": mapping, "aliases": aliases})
    return status == 200, answer.get("error", {}).get("type")


def recreate(index, new_mapping):
    current = mapping_of(index)
    if current is None:
        created, error = create(index, new_mapping, {}, {})
        print(f"{index}	nao existia	{'criado' if created else 'falha ao criar: ' + str(error)}")
        return created
    if current == new_mapping:
        print(f"{index}	ja tem o mapeamento novo	pulado")
        return True
    documents = count(index)
    if documents != 0:
        print(f"{index}	{documents} documentos	NADA FEITO: as vagas gravadas nao cabem no formato novo, decidir com o usuario")
        return False
    settings = settings_of(index)
    aliases = aliases_of(index)
    status, answer = call("DELETE", "/" + index)
    if status != 200:
        print(f"{index}	falha ao apagar: {answer.get('error', {}).get('type')}")
        return False
    created, error = create(index, new_mapping, settings, aliases)
    if not created:
        print(f"{index}	APAGADO E NAO RECRIADO ({error}): rode de novo")
        return False
    same = mapping_of(index) == new_mapping
    print(f"{index}	0 documentos	recriado com o mapeamento novo	{'conferido' if same else 'MAPEAMENTO DIFERENTE DO ARQUIVO'}")
    return same


with open(MAPPING_FILE, encoding="utf-8") as mapping_file:
    mapping = json.load(mapping_file)["mappings"]

results = [recreate(index, mapping) for index in INDEXES]
print("cache das entidades: 1 h; publique nova revisao de vis e js e reinicie os consumidores (pm2 restart all), "
      "ou espere a hora passar")
sys.exit(0 if all(results) else 1)
