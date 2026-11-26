# Elimina de producao os recrutadores sem retorno (pedido do usuario em 2026-11-26, para preservar a reputacao do
# remetente no SendGrid: o envio das 10h de 2026-11-26 entregou 56%, com 684 bounces e 413 bloqueios):
#   - de vis_recruiter: o criterio 7 da ordem de VisBusinessSendResumesToRecruiters (fila de quem nunca visualizou,
#     sem nenhum dos criterios 1 a 6), e tambem quem for descadastrado, bounce, spam ou invalido;
#   - de vis_inactive_recruiter: quem for descadastrado (vis_recruiter_unsubscribed), bounce, spam ou invalido (listas
#     de supressao do SendGrid) ou estiver em jn_email_suppressed.
# Apaga de verdade (nao move para a gemea): delete por _id direto no indice, sem os decorators. O contador de origem
# (vis_virtual_recruiter_source_counter) e recalculado depois pelo script 92; o grupo das iniciais de dominio guarda
# o dominio mesmo depois dos deletes (regra do child por campo), entao fica como esta.
# Antes de apagar: exige snapshot SUCCESS do jobsnow-backup das ultimas 36 h com vis_recruiter e grava o _source
# inteiro de cada registro apagado num JSONL local (fora do repositorio: tem e-mails), que permite restaurar.
# Sem "gravar" so conta. Idempotente: rodar de novo so encontra o que sobrou. Imprime so contagens.
# Uso: powershell -File com-tunel-de-producao.ps1 -Script 125-eliminar-recrutadores-sem-retorno.py -Argumentos "<copia.jsonl> [gravar]"
#      depois: o script 92 (contador de origem); o cache das entidades dura 1 h.
import datetime, hashlib, importlib.util, io, contextlib, json, os, sys, urllib.parse, urllib.request

copy_path = sys.argv[1]
write = len(sys.argv) > 2 and sys.argv[2] == "gravar"
here = os.path.dirname(os.path.abspath(__file__))
simulator = os.path.join(here, "..", "..", ".claude", "skills", "ccp-criterios-dos-recrutadores", "scripts", "criterios-dos-recrutadores.py")
spec = importlib.util.spec_from_file_location("criterios", simulator)
sys.argv = [sys.argv[0], copy_path + ".ordem.tsv"]
with contextlib.redirect_stdout(io.StringIO()):
    c = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(c)

key = json.load(open(r"C:\segredos\producao.json", encoding="utf-8"))["tokenEmailKey"]


def sendgrid(kind):
    found, offset = set(), 0
    while True:
        query = urllib.parse.urlencode({"limit": 500, "offset": offset})
        request = urllib.request.Request("https://api.sendgrid.com/v3/suppression/%s?%s" % (kind, query),
                                         headers={"Authorization": "Bearer " + key})
        page = json.load(urllib.request.urlopen(request, timeout=60))
        found |= {item["email"].lower() for item in page}
        if len(page) < 500:
            return found
        offset += 500


def recent_snapshot():
    status, answer = c.call("GET", "/_snapshot/jobsnow-backup/_all")
    snapshots = answer.get("snapshots", []) if status == 200 else []
    limit = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=36)).timestamp() * 1000
    recent = [s for s in snapshots if s.get("state") == "SUCCESS" and "vis_recruiter" in s.get("indices", [])
              and "vis_inactive_recruiter" in s.get("indices", []) and s.get("start_time_in_millis", 0) >= limit]
    return recent[-1]["snapshot"] if recent else ""


suppressed_lists = {"bounce": sendgrid("bounces"), "spam": sendgrid("spam_reports"), "invalido": sendgrid("invalid_emails")}
unsubscribed = {hit["_source"]["email"] for hit in c.search_all("vis_recruiter_unsubscribed", {"match_all": {}})}
suppressed = {hit["_source"]["email"] for hit in c.search_all("jn_email_suppressed", {"match_all": {}})}
criterion7 = {r["email"] for _, r, _ in c.queue}


def reasons(email):
    found = [name for name, emails in suppressed_lists.items() if email.lower() in emails]
    email_hash = c.sha1(email)
    if email in unsubscribed or email_hash in unsubscribed:
        found.append("descadastrado")
    if email in suppressed or email_hash in suppressed:
        found.append("jn_email_suppressed")
    return found


targets = []
for index, with_criterion7 in (("vis_recruiter", True), ("vis_inactive_recruiter", False)):
    for hit in c.search_all(index, {"match_all": {}}):
        email = hit["_source"]["email"]
        why = reasons(email)
        if with_criterion7 and email in criterion7:
            why.append("criterio7")
        if why:
            targets.append((index, hit["_id"], hit["_source"], why))

counts = {}
for index, _, _, why in targets:
    counts[index] = counts.get(index, 0) + 1
print("a eliminar:", counts, "| total:", len(targets))
if not write:
    print("simulacao: nada apagado (passe 'gravar')")
    sys.exit(0)

snapshot = recent_snapshot()
print("snapshot recente:", snapshot or "nenhum")
if not snapshot:
    sys.exit("sem snapshot das ultimas 36 h com vis_recruiter e vis_inactive_recruiter: nada apagado")

with open(copy_path, "a", encoding="utf-8") as copy:
    for index, doc_id, source, why in targets:
        copy.write(json.dumps({"index": index, "_id": doc_id, "reasons": why, "_source": source}, ensure_ascii=False) + "\n")
print("copia gravada antes do delete:", len(targets), "linhas")

deleted, failures = 0, 0
for start in range(0, len(targets), 1000):
    lines = [json.dumps({"delete": {"_index": index, "_id": doc_id}}) for index, doc_id, _, _ in targets[start:start + 1000]]
    body = ("\n".join(lines) + "\n").encode("utf-8")
    request = urllib.request.Request(c.target_url + "/_bulk", data=body, method="POST")
    request.add_header("Content-Type", "application/x-ndjson")
    if c.auth:
        request.add_header("Authorization", c.auth)
    with c.opener.open(request) as response:
        answer = json.loads(response.read())
    for item in answer["items"]:
        result = item["delete"]
        if result.get("result") == "deleted":
            deleted += 1
        elif result.get("status") != 404:
            failures += 1
c.call("POST", "/vis_recruiter,vis_inactive_recruiter/_refresh")
for index in ("vis_recruiter", "vis_inactive_recruiter"):
    status, answer = c.call("GET", "/" + index + "/_count")
    print(index, "restam:", answer.get("count"))
print("apagados:", deleted, "| falhas:", failures)
sys.exit(1 if failures else 0)
