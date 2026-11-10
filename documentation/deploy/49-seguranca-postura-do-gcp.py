# Seguranca, item 5: postura do projeto jobsnow-prd no GCP. SO LEITURA: so comandos list/describe/get-iam-policy do
# gcloud e conexoes TCP de teste a partir desta maquina; nada e criado, alterado ou apagado.
#
# Confere:
#   - IAM do projeto: ninguem de fora com papel basico (owner/editor), nenhuma conta de servico com owner/editor,
#     nenhum allUsers/allAuthenticatedUsers.
#   - Contas de servico: chaves criadas pelo usuario (arquivo de chave e segredo de longa duracao).
#   - Buckets: prevencao de acesso publico ligada e nenhum allUsers no IAM.
#   - Firewall: nenhuma regra aberta para 0.0.0.0/0 nas portas do ES (9200/9300), do Valkey (6379) e do SSH (22, que deve
#     vir so do IAP 35.235.240.0/20).
#   - VM: o ES nao responde no IP externo (conexao TCP de fora, daqui).
#   - Cloud Run: ingress de cada servico (o ideal e so o balanceador: internal-and-cloud-load-balancing) e se a URL
#     *.run.app responde direto, passando por fora do balanceador e da CDN.
#   - Chaves de API do projeto.
#   - Pub/Sub: nenhum topico ou assinatura com allUsers.
#
# Resultado em c:/logs/seguranca/postura-gcp.json (pagina Backend > Seguranca do portal 37). Sai com 1 se ha achado ALTO.
# Uso: python 49-seguranca-postura-do-gcp.py [projeto]

import datetime
import json
import os
import socket
import subprocess
import sys
import urllib.request

PROJECT = sys.argv[1] if len(sys.argv) > 1 else "jobsnow-prd"
OUT_DIR = r"c:\logs\seguranca"
IAP_RANGE = "35.235.240.0/20"
SENSITIVE_PORTS = {"9200": "Elasticsearch", "9300": "Elasticsearch (transporte)", "6379": "Valkey", "22": "SSH",
                   "5601": "Kibana"}
PUBLIC_MEMBERS = ("allUsers", "allAuthenticatedUsers")
findings = []
checks = []


def gcloud(*args):
    command = "gcloud " + " ".join(args) + " --project=" + PROJECT + " --format=json --quiet"
    process = subprocess.run(command, shell=True, capture_output=True, text=True, encoding="utf-8")
    if process.returncode != 0:
        raise RuntimeError(process.stderr.strip().splitlines()[-1] if process.stderr.strip() else command)
    return json.loads(process.stdout or "null")


def finding(level, area, text):
    findings.append({"level": level, "area": area, "text": text})


def check(area, description, function):
    try:
        function()
        checks.append({"area": area, "check": description, "ok": True})
    except Exception as error:
        checks.append({"area": area, "check": description, "ok": False, "error": str(error)[:300]})
        finding("MEDIO", area, "conferencia nao executada: %s (%s)" % (description, str(error)[:200]))


def owner_members():
    # o dono e a conta ativa do gcloud de quem roda o script (nunca escrita aqui: este repositorio e publico)
    process = subprocess.run("gcloud config get-value account", shell=True, capture_output=True, text=True)
    account = process.stdout.strip().lower()
    return {"user:" + account} if account else set()


def project_iam():
    owners = owner_members()
    policy = gcloud("projects get-iam-policy", PROJECT)
    for binding in policy.get("bindings", []):
        role = binding["role"]
        for member in binding.get("members", []):
            if member in PUBLIC_MEMBERS:
                finding("ALTO", "IAM", "%s tem %s no projeto" % (member, role))
                continue
            basic = role in ("roles/owner", "roles/editor")
            if basic and member.startswith("serviceAccount:"):
                finding("ALTO" if role == "roles/owner" else "MEDIO", "IAM",
                        "conta de servico %s com papel basico %s (dar so os papeis que ela usa)" % (member, role))
                continue
            if basic and member.lower() not in owners:
                finding("ALTO", "IAM", "%s com %s" % (member, role))


def service_account_keys():
    accounts = gcloud("iam service-accounts list")
    for account in accounts or []:
        email = account["email"]
        keys = gcloud("iam service-accounts keys list", "--iam-account=" + email, "--managed-by=user")
        for key in keys or []:
            created = key.get("validAfterTime", "")[:10]
            finding("MEDIO", "Contas de servico", "chave de usuario em %s criada em %s (%s): prefira identidade "
                    "anexada/ADC e apague a chave se ninguem usa" % (email, created, key["name"].rsplit("/", 1)[-1][:8]))


def buckets():
    for bucket in gcloud("storage buckets list") or []:
        name = bucket.get("name") or bucket.get("id")
        prevention = bucket.get("public_access_prevention") or (bucket.get("iamConfiguration") or {}).get(
            "publicAccessPrevention", "")
        if prevention != "enforced":
            finding("BAIXO", "Buckets", "gs://%s sem public access prevention 'enforced' (%s)" % (name, prevention or "inherited"))
        policy = gcloud("storage buckets get-iam-policy", "gs://" + name)
        for binding in (policy or {}).get("bindings", []):
            public = [member for member in binding.get("members", []) if member in PUBLIC_MEMBERS]
            if public:
                finding("ALTO", "Buckets", "gs://%s publico: %s com %s" % (name, ",".join(public), binding["role"]))


def firewall():
    for rule in gcloud("compute firewall-rules list") or []:
        if rule.get("disabled") or rule.get("direction") != "INGRESS":
            continue
        ranges = rule.get("sourceRanges", [])
        open_world = "0.0.0.0/0" in ranges or "::/0" in ranges
        for allowed in rule.get("allowed", []):
            ports = allowed.get("ports", ["todas"]) if allowed.get("IPProtocol") in ("tcp", "all") else []
            for port in ports:
                exposed = [name for number, name in SENSITIVE_PORTS.items() if port == "todas" or port == number or (
                    "-" in port and int(port.split("-")[0]) <= int(number) <= int(port.split("-")[1]))]
                if open_world and exposed:
                    finding("ALTO", "Firewall", "regra %s abre %s (%s) para a internet" % (rule["name"], port, ",".join(exposed)))
                ssh_outside_iap = "SSH" in exposed and any(item != IAP_RANGE for item in ranges)
                if ssh_outside_iap and not open_world:
                    finding("BAIXO", "Firewall", "regra %s libera SSH para %s (alem do IAP)" % (rule["name"], ranges))


def tcp_open(address, port):
    try:
        with socket.create_connection((address, int(port)), timeout=4):
            return True
    except OSError:
        return False


def instances():
    for instance in gcloud("compute instances list") or []:
        for interface in instance.get("networkInterfaces", []):
            for access in interface.get("accessConfigs", []):
                address = access.get("natIP")
                if not address:
                    continue
                for port, name in SENSITIVE_PORTS.items():
                    if tcp_open(address, port):
                        finding("ALTO", "VM", "%s responde na porta %s (%s) do IP externo" % (instance["name"], port, name))


def cloud_run():
    for service in gcloud("run services list") or []:
        name = service["metadata"]["name"]
        annotations = service["metadata"].get("annotations", {})
        ingress = annotations.get("run.googleapis.com/ingress", "all")
        url = service.get("status", {}).get("url", "")
        status = 0
        try:
            with urllib.request.urlopen(url + "/rota-inexistente-da-postura", timeout=10) as response:
                status = response.status
        except urllib.error.HTTPError as error:
            status = error.code
        except Exception:
            status = 0
        direct = status not in (0, 403, 404) or (status == 404 and ingress == "all")
        if ingress == "all":
            finding("MEDIO", "Cloud Run", "%s com ingress 'all': a URL %s responde (%s) por fora do balanceador e da CDN; "
                    "use internal-and-cloud-load-balancing" % (name, url, status or "sem resposta"))
        policy = gcloud("run services get-iam-policy", name, "--region=" + service["metadata"]["labels"].get(
            "cloud.googleapis.com/location", "us-central1"))
        public = any(member in PUBLIC_MEMBERS for binding in (policy or {}).get("bindings", [])
                     for member in binding.get("members", []))
        checks.append({"area": "Cloud Run", "check": "%s: ingress=%s, invocacao publica=%s, URL direta=%s"
                       % (name, ingress, public, status if direct else "fechada"), "ok": ingress != "all"})


def api_keys():
    for key in gcloud("services api-keys list") or []:
        restrictions = key.get("restrictions", {})
        if not restrictions:
            finding("MEDIO", "Chaves de API", "chave %s sem restricao de API nem de origem" % key.get("displayName", key["uid"]))


def pubsub():
    for kind in ("topics", "subscriptions"):
        for item in gcloud("pubsub", kind, "list") or []:
            name = item["name"].rsplit("/", 1)[-1]
            policy = gcloud("pubsub", kind, "get-iam-policy", name)
            for binding in (policy or {}).get("bindings", []):
                if any(member in PUBLIC_MEMBERS for member in binding.get("members", [])):
                    finding("ALTO", "Pub/Sub", "%s %s publico (%s)" % (kind[:-1], name, binding["role"]))


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    check("IAM", "papeis do projeto", project_iam)
    check("Contas de servico", "chaves de usuario", service_account_keys)
    check("Buckets", "acesso publico", buckets)
    check("Firewall", "portas sensiveis abertas", firewall)
    check("VM", "portas sensiveis no IP externo", instances)
    check("Cloud Run", "ingress e URL direta", cloud_run)
    check("Chaves de API", "restricoes", api_keys)
    check("Pub/Sub", "acesso publico", pubsub)
    high = [item for item in findings if item["level"] == "ALTO"]
    result = {"when": datetime.datetime.now().isoformat(timespec="seconds"), "project": PROJECT, "checks": checks,
              "findings": findings, "high": len(high), "ok": not high}
    with open(os.path.join(OUT_DIR, "postura-gcp.json"), "w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=1)
    print("projeto %s | conferencias: %d | achados: %d (altos: %d)" % (PROJECT, len(checks), len(findings), len(high)))
    for item in checks:
        print("  [%s] %-18s %s %s" % ("ok" if item["ok"] else "!!", item["area"], item["check"], item.get("error", "")))
    for item in sorted(findings, key=lambda entry: ["ALTO", "MEDIO", "BAIXO"].index(entry["level"])):
        print("  %-5s %-18s %s" % (item["level"], item["area"], item["text"]))
    return 1 if high else 0


if __name__ == "__main__":
    sys.exit(main())
