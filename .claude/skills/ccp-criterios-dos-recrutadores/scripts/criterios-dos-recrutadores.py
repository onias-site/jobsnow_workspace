# Simula, so lendo o ES, a ordem de VisBusinessSendResumesToRecruiters.getRecruitersInOrder + o filtro de endereco
# invalido do VisResumesToTheRecruiterSender e grava os primeiros N e-mails (padrao 2000) num TSV.
# Uso (pelo com-tunel-de-producao.ps1): -Script este -Argumentos <saida.tsv>; destino padrao o tunel (9210), N padrao 2000.
# So leitura de producao: vis_recruiter (com legacyActive, lastLegacyView, lastTelegramAppearance), historico no jn_grouper,
# vis_recruiter_sign_up_return, vis_recruiter_first_email e vis_recruiter_queue_cursor. Nenhum e-mail e impresso.
import hashlib, json, os, re, sys, time, urllib.request, urllib.error

out_path = sys.argv[1]
target_url = (sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:9210").rstrip("/")
limit = int(sys.argv[3]) if len(sys.argv) > 3 else 2000
auth = os.environ.get("ES_DESTINO_AUTH", "")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
DAY = 86400000
now = int(time.time() * 1000)
views_since = now - 35 * DAY
telegram_since = now - 183 * DAY
GREATEST = 9_999_999_999_999


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


def search_all(index, query, source=True):
    status, answer = call("POST", "/" + index + "/_pit?keep_alive=2m")
    if status == 404:
        return []
    if status != 200:
        sys.exit("falha ao abrir " + index + " " + str(status))
    pit = answer["id"]
    hits, after = [], None
    while True:
        body = {"size": 1000, "query": query, "_source": source, "sort": [{"_shard_doc": "asc"}],
                "pit": {"id": pit, "keep_alive": "2m"}}
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
    return hits


def sha1(text):
    digest = hashlib.sha1(text.encode("utf-8")).digest()
    number = int.from_bytes(digest, "big", signed=True)
    return format(number, "x")


EMAIL_REGEX = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def is_valid(email):
    split = email.split("@")
    if len(split) != 2 or not split[0].strip():
        return False
    low = email.strip().lower()
    if low.endswith(".digital") or low.endswith("@wayon.global") or low.endswith("@corp.inovation.com.br"):
        return True
    low = email.lower()
    for ending in (".docx", ".digi", ".onli", ".glob", ".soci", ".bren"):
        if low.endswith(ending):
            return False
    if ".coom" in low or not EMAIL_REGEX.search(email):
        return False
    tld = split[1].split(".")[-1].lower()
    if tld.startswith("com") and tld != "com":
        return False
    if tld.startswith("br") and tld != "br":
        return False
    return True


# o historico de cada registro e um grupo do jn_grouper desde 2026-11-20 (antes, linhas do jn_versionable): uma versao
# (texto JSON com json e timestamp) por gravacao
HISTORY_QUERY = {"bool": {"must": [{"term": {"parentName": "jn_virtual_versionable_history"}},
                                   {"term": {"childName": "vis_viewed_resume"}}]}}
last_view = {}
for hit in search_all("jn_grouper", HISTORY_QUERY, ["child"]):
    for child in hit["_source"].get("child", []):
        version = json.loads(child)
        email_hash = version["json"].get("email")
        timestamp = int(float(version["timestamp"]))
        last_view[email_hash] = max(last_view.get(email_hash, 0), timestamp)
for hit in search_all("vis_recruiter_sign_up_return", {"match_all": {}}):
    source = hit["_source"]
    h = source["email"]
    if h in last_view:
        last_view[h] = max(last_view[h], int(float(source["returnedAt"])))
first_email = {hit["_source"]["email"] for hit in search_all("vis_recruiter_first_email", {"match_all": {}})}
cursors = {hit["_source"]["cursorName"]: hit["_source"].get("lastPosition", "")
           for hit in search_all("vis_recruiter_queue_cursor", {"match_all": {}})}
recruiters = [hit["_source"] for hit in search_all("vis_recruiter", {"match_all": {}})]

viewers, first, nonprof, legacy, active, telegram, queue = [], [], [], [], [], [], []
for r in recruiters:
    email = r["email"]
    h = sha1(email)
    lv = last_view.get(h)
    if lv is not None and lv < views_since:
        continue
    if lv is not None:
        viewers.append((-lv, h, r, "1-visualizou nos ultimos 35 dias"))
        continue
    source = r.get("source", "")
    signup = source == "login"
    # desde 2026-11-17 o cadastrado pelo suporte espera o 1o e-mail empatado com o do cadastro (login)
    if (signup or source == "support") and h not in first_email:
        first.append((h, r, "2-cadastro aguardando 1o e-mail"))
        continue
    tg = int(float(r["lastTelegramAppearance"])) if "lastTelegramAppearance" in r else 0
    if "lastTelegramAppearance" in r and tg >= telegram_since:
        telegram.append((-tg, h, r, "3-Telegram (183 dias)"))
        continue
    if "lastLegacyView" in r:
        position = "%013d%s" % (GREATEST - int(float(r["lastLegacyView"])), h)
        legacy.append((position, r, "4-visualizou no legado"))
        continue
    if r.get("legacyActive") is True:
        active.append((h, r, "5-ativo no legado"))
        continue
    if r.get("professional", True) is False:
        nonprof.append((h, r, "6-dominio nao profissional"))
        continue
    queue.append((("0" if signup else "1") + h, r, "7-fila de quem nunca viu"))


def in_turn(items, last):
    items = sorted(items, key=lambda item: item[0])
    return [i for i in items if i[0] > last] + [i for i in items if i[0] <= last]


ordered = [(i[2], i[3]) for i in sorted(viewers, key=lambda i: (i[0], i[1]))]
ordered += [(i[1], i[2]) for i in sorted(first, key=lambda i: i[0])]
ordered += [(i[2], i[3]) for i in sorted(telegram, key=lambda i: (i[0], i[1]))]
ordered += [(i[1], i[2]) for i in in_turn(legacy, cursors.get("legacyViewersOfResumesToRecruiters", ""))]
ordered += [(i[1], i[2]) for i in in_turn(active, cursors.get("legacyActiveRecruitersOfResumesToRecruiters", ""))]
ordered += [(i[1], i[2]) for i in in_turn(nonprof, cursors.get("nonProfessionalRecruitersOfResumesToRecruiters", ""))]
ordered += [(i[1], i[2]) for i in in_turn(queue, cursors.get("resumesToRecruiters", ""))]

sizes = {}
for r, group in ordered:
    sizes[group] = sizes.get(group, 0) + 1
print("tamanho de cada grupo na ordem completa:", dict(sorted(sizes.items())))
la = sum(1 for r in recruiters if r.get("legacyActive") is True)
print("ativos no legado em vis_recruiter:", la)
chosen, invalid = [], 0
for r, group in ordered:
    if len(chosen) >= limit:
        break
    if not is_valid(r["email"]):
        invalid += 1
        continue
    chosen.append((r, group))

with open(out_path, "w", encoding="utf-8", newline="") as out:
    out.write("#\temail\tgrupo\tdominio\tprofissional\torigem\tativo no legado\ttelegram\tvisualizou no legado\n")
    for n, (r, group) in enumerate(chosen, 1):
        tg = time.strftime("%Y-%m-%d", time.gmtime(int(float(r["lastTelegramAppearance"])) / 1000)) if "lastTelegramAppearance" in r else ""
        lg = time.strftime("%Y-%m-%d", time.gmtime(int(float(r["lastLegacyView"])) / 1000)) if "lastLegacyView" in r else ""
        la = "sim" if r.get("legacyActive") is True else ""
        out.write("%d\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" % (n, r["email"], group, r.get("domain", ""), r.get("professional", ""), r.get("source", ""), la, tg, lg))

counts = {}
for r, group in chosen:
    counts[group] = counts.get(group, 0) + 1
print("recrutadores ativos:", len(recruiters), "| na ordem:", len(ordered), "| invalidos pulados:", invalid, "| gravados:", len(chosen))
for group in sorted(counts):
    print(group, counts[group])
tgc = sum(1 for r, g in chosen if "lastTelegramAppearance" in r)
tgr = sum(1 for r, g in chosen if "lastTelegramAppearance" in r and int(float(r["lastTelegramAppearance"])) >= telegram_since)
lac = sum(1 for r, g in chosen if r.get("legacyActive") is True)
print("ativos no legado na lista:", lac)
lgc = sum(1 for r, g in chosen if "lastLegacyView" in r)
both = sum(1 for r, g in chosen if "lastLegacyView" in r and "lastTelegramAppearance" in r)
print("telegram:", tgc, "| telegram 183 dias:", tgr, "| legado:", lgc, "| ambos:", both, "| nenhum:", len(chosen) - tgc - lgc + both)
print("cursores:", {k: (v[:8] + "...") for k, v in cursors.items()})
