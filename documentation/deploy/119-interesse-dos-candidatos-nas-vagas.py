# Interesse dos candidatos nas vagas (2026-11-24): o candidato logado, em "Meus dados -> Minhas vagas", confirma "Enviar
# meu curriculo" numa vaga aberta aos candidatos (byTheCandidates) e o curriculo vai ao recrutador na proxima hora cheia,
# na lista de curriculos da vaga, junto com os dos outros interessados (VisBusinessSendTheResumesOfTheInterestedCandidates,
# primeiro topico do job jobsnow-reenvio-token-login).
#
# O que faz:
#   1. cria em producao o indice vis_position_interest (o interesse de cada candidato em cada vaga) com o mapeamento do
#      local (ccp_rest-api-tests_jobsnow/documentation/vis/.../create/vis_position_interest);
#   2. acrescenta o campo recruiterDomain (keyword) em vis_position e vis_inactive_position: o dominio do e-mail do
#      recrutador dono da vaga, que o save passa a calcular (VisJsonTransformerPositionRecruiterDomain), porque o
#      recruiter guarda so o SHA-1 do e-mail e o notAllowedCompany do curriculo precisa ser comparado com a empresa do dono;
#   3. com --gravar, preenche recruiterDomain nas vagas ja gravadas, quando da para saber o dominio: o resumesEmail
#      (legivel) e o proprio e-mail do dono (o SHA-1 dele, no formato do Java, e igual ao recruiter). Dominio nao
#      profissional (NONPROFESSIONALDOMAINS de jn_system_parameter) fica sem o campo, como no save. As demais vagas so
#      ganham o campo quando o recrutador salvar a vaga de novo; ate la, so o dominio do resumesEmail e comparado.
# Imprime so contagens. Idempotente.
#
# Ordem: rodar sem --gravar ANTES do deploy da vis, dos consumidores e do cron (sem o campo no mapeamento strict, o save da
# vaga falha; sem o indice, o interesse falha); com --gravar a qualquer momento depois. Depois: o cache das entidades dura
# 1 hora. Rodar tambem 03-criar-filas.ps1 (fila da entidade assincrona com.vis.entities.VisEntityPositionInterest).
#
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python 119-interesse-dos-candidatos-nas-vagas.py [--gravar] [url do destino]
#      (sem url: o tunel de producao, http://127.0.0.1:9210; para o ES local, http://localhost:9200)
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request

arguments = [argument for argument in sys.argv[1:] if argument != "--gravar"]
write = "--gravar" in sys.argv[1:]
target = arguments[0].rstrip("/") if arguments else "http://127.0.0.1:9210"
here = os.path.dirname(os.path.abspath(__file__))
create_folder = os.path.join(here, "..", "..", "ccp_rest-api-tests_jobsnow", "documentation", "vis", "database",
                             "elasticsearch", "scripts", "entities", "create")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def call(method, path, body=None):
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(target + path, data=data, method=method, headers={"Content-Type": "application/json"})
    auth = os.environ.get("ES_DESTINO_AUTH", "")
    if auth:
        request.add_header("Authorization", auth)
    try:
        with opener.open(request) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"{}")


def java_sha1(text):
    # CcpHashDecorator.asString: new BigInteger(digest).toString(16), com sinal e sem zeros a esquerda
    digest = hashlib.sha1(text.encode("utf-8")).digest()
    return format(int.from_bytes(digest, "big", signed=True), "x")


def scroll(index, query):
    status, page = call("POST", "/" + index + "/_search?scroll=2m", {"size": 500, "query": query})
    if status != 200:
        raise SystemExit(index + ": falha na leitura " + str(status))
    while page["hits"]["hits"]:
        for hit in page["hits"]["hits"]:
            yield hit
        status, page = call("POST", "/_search/scroll", {"scroll": "2m", "scroll_id": page["_scroll_id"]})
        if status != 200:
            raise SystemExit(index + ": falha no scroll " + str(status))


# 1. o indice do interesse
INTEREST = "vis_position_interest"
definition = json.load(open(os.path.join(create_folder, INTEREST), encoding="utf-8"))
status, _ = call("HEAD", "/" + INTEREST)
if status == 404:
    status, answer = call("PUT", "/" + INTEREST, definition)
    print(INTEREST, "criado:", status, answer.get("acknowledged"))
status, mapping = call("GET", "/" + INTEREST + "/_mapping")
same = mapping[INTEREST]["mappings"]["properties"] == definition["mappings"]["properties"]
print(INTEREST, "mapeamento igual ao do local:", same)
if not same:
    raise SystemExit(1)

# 2. o campo novo da vaga, nos dois lados
POSITIONS = ("vis_position", "vis_inactive_position")
for index in POSITIONS:
    status, answer = call("PUT", "/" + index + "/_mapping", {"properties": {"recruiterDomain": {"type": "keyword"}}})
    print(index, "recruiterDomain no mapeamento:", status, answer.get("acknowledged"))
    if status != 200:
        raise SystemExit(1)

# 3. o dominio do dono nas vagas ja gravadas
status, found = call("POST", "/jn_system_parameter/_search",
                     {"size": 1, "query": {"term": {"systemMessageName": "NONPROFESSIONALDOMAINS"}}})
hits = found.get("hits", {}).get("hits", [])
if not hits:
    raise SystemExit("jn_system_parameter sem NONPROFESSIONALDOMAINS")
non_professional = {domain.lower() for domain in hits[0]["_source"].get("message", [])}

for index in POSITIONS:
    counters = {"sem o campo": 0, "dono = resumesEmail": 0, "dominio nao profissional": 0,
                "sem como saber": 0, "gravadas": 0}
    missing_domain = {"bool": {"must_not": [{"exists": {"field": "recruiterDomain"}}]}}
    for hit in scroll(index, missing_domain):
        counters["sem o campo"] += 1
        source = hit["_source"]
        resumes_email = (source.get("resumesEmail") or "").strip()
        recruiter = source.get("recruiter") or ""
        owner = resumes_email and recruiter in (java_sha1(resumes_email), java_sha1(resumes_email.lower()))
        if not owner:
            counters["sem como saber"] += 1
            continue
        counters["dono = resumesEmail"] += 1
        domain = resumes_email.split("@")[-1].lower()
        if domain in non_professional:
            counters["dominio nao profissional"] += 1
            continue
        if not write:
            continue
        status, _ = call("POST", "/" + index + "/_update/" + hit["_id"], {"doc": {"recruiterDomain": domain}})
        if status != 200:
            raise SystemExit(index + ": falha ao gravar " + str(status))
        counters["gravadas"] += 1
    print(index, json.dumps(counters, ensure_ascii=False))
print("modo:", "gravar" if write else "so contar (use --gravar para preencher)")
