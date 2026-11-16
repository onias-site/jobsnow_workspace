# Visualizacoes de curriculos por dia, so leitura de producao (pelo com-tunel-de-producao.ps1, porta 9210).
# Le o contador diario do jn_grouper (parent vis_virtual_insertion_day_counter, child vis_viewed_resume: historico, nao
# desconta exclusoes), as visualizacoes de vis_viewed_resume e vis_inactive_viewed_resume (insertionDate dd/MM/yyyy, hora
# de Sao Paulo) e os recrutadores de vis_recruiter (e-mail aberto, domain, professional) para achar o dominio de cada
# visualizacao (o email da visualizacao e o SHA-1 no formato do Java). Nenhum e-mail e impresso.
# Uso: -Argumentos [dias] (padrao 7). Saida: uma linha TSV por dia, do mais antigo ao mais recente, e as horas do ultimo dia.
import hashlib, json, os, sys, collections, urllib.request, urllib.error

days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
url = "http://127.0.0.1:9210"
auth = os.environ.get("ES_DESTINO_AUTH", "")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
EXCLUDED = {"freelancer", "onias.site"}


def call(method, path, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if auth:
        request.add_header("Authorization", auth)
    try:
        with opener.open(request) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"{}")


def search_all(index, source):
    status, answer = call("POST", "/" + index + "/_pit?keep_alive=2m")
    if status == 404:
        return []
    if status != 200:
        sys.exit("falha ao abrir " + index + " " + str(status))
    pit, hits, after = answer["id"], [], None
    while True:
        body = {"size": 5000, "_source": source, "sort": [{"_shard_doc": "asc"}], "pit": {"id": pit, "keep_alive": "2m"}}
        if after is not None:
            body["search_after"] = after
        status, answer = call("POST", "/_search", body)
        page = answer["hits"]["hits"]
        if not page:
            break
        hits.extend(page)
        after = page[-1]["sort"]
        pit = answer.get("pit_id", pit)
    call("DELETE", "/_pit", {"id": pit})
    return [hit["_source"] for hit in hits]


def sha1(text):
    digest = hashlib.sha1(text.encode("utf-8")).digest()
    return format(int.from_bytes(digest, "big", signed=True), "x")


status, answer = call("POST", "/jn_grouper/_search", {"size": 1, "query": {"bool": {"filter": [
    {"term": {"parentName": "vis_virtual_insertion_day_counter"}}, {"term": {"childName": "vis_viewed_resume"}}]}}})
counter = {}
for hit in answer.get("hits", {}).get("hits", []):
    child = hit["_source"].get("child") or ["{}"]
    counter = json.loads(child[0])

domain_by_hash = {}
for recruiter in search_all("vis_recruiter", ["email", "domain", "professional"]):
    email = recruiter.get("email", "")
    domain = (recruiter.get("domain") or email.split("@")[-1]).lower()
    if recruiter.get("professional") is False:
        domain = "freelancer"
    domain_by_hash[sha1(email)] = domain
    domain_by_hash.setdefault(sha1(email.lower()), domain)

views = search_all("vis_viewed_resume", ["email", "insertionDate"]) + search_all("vis_inactive_viewed_resume", ["email", "insertionDate"])
per_day = collections.defaultdict(list)
for view in views:
    date = str(view.get("insertionDate", ""))
    if len(date) < 16:
        continue
    per_day[date[6:10] + date[3:5] + date[0:2]].append((date[11:16], view.get("email", "")))

all_days = sorted(set(counter) | set(per_day))[-days:]
print("dia\tcontador\tregistros\trecrutadores\tconsultorias\tfreelancer\tonias.site\tsem_recrutador")
for day in all_days:
    items = per_day.get(day, [])
    domains = collections.Counter(domain_by_hash.get(email, "?") for _, email in items)
    ranked = sorted(domains.items(), key=lambda pair: (-pair[1], pair[0]))
    companies = ", ".join("%s (%d)" % (name, count) for name, count in ranked if name not in EXCLUDED and name != "?")
    print("\t".join([day[6:8] + "/" + day[4:6] + "/" + day[0:4], str(counter.get(day, 0)), str(len(items)),
                     str(len({email for _, email in items})), companies or "-", str(domains.get("freelancer", 0)),
                     str(domains.get("onias.site", 0)), str(domains.get("?", 0))]))
if all_days:
    print("horas do ultimo dia:", " ".join(sorted(hour for hour, _ in per_day.get(all_days[-1], []))))
