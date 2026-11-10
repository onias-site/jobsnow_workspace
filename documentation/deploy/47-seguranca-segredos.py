# Seguranca, item 2: nenhuma chave ou senha versionada nos repositorios nem no historico.
#
# Os 29 repositorios do GitHub (onias-site) sao PUBLICOS e a tela /nosso-backend aponta para todos eles: qualquer segredo
# que ja tenha passado por um commit esta exposto, mesmo que o arquivo tenha sido apagado depois.
#
# Duas varreduras, em todos os repositorios locais (a raiz do workspace e cada pasta com .git):
#   1. gitleaks no historico inteiro (regras genericas: chaves do Google, SendGrid, Telegram, tokens em curl...).
#   2. Valores exatos: cada segredo de C:\segredos\producao.json e da variavel application_properties (local) e
#      procurado em TODOS os objetos de cada repositorio (git cat-file --batch-all-objects), inclusive os inalcancaveis.
#      Nenhum valor e impresso: so o nome da propriedade, o repositorio e o objeto.
#
# Achados ja conhecidos ficam em seguranca/segredos-conhecidos.tsv (impressao digital do gitleaks + situacao). Um achado
# novo faz o script sair com codigo 1. O resultado vai para c:/logs/seguranca/segredos.json (lido pela pagina
# Backend > Seguranca do portal 37).
#
# Uso: python 47-seguranca-segredos.py [--instalar-hooks]
#   --instalar-hooks grava .git/hooks/pre-commit em cada repositorio: gitleaks nos arquivos do commit (protect --staged).
#
# Exige o gitleaks em %USERPROFILE%\tools\gitleaks\gitleaks.exe (8.21.2, baixado de github.com/gitleaks/gitleaks com o
# sha256 conferido).

import datetime
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WORKSPACE = os.path.abspath(os.path.join(HERE, "..", ".."))
GITLEAKS = os.path.join(os.path.expanduser("~"), "tools", "gitleaks", "gitleaks.exe")
CONFIG = os.path.join(HERE, "seguranca", "gitleaks.toml")
KNOWN = os.path.join(HERE, "seguranca", "segredos-conhecidos.tsv")
PRODUCTION_PROPERTIES = r"C:\segredos\producao.json"
OUT_DIR = r"c:\logs\seguranca"
MIN_SECRET_LENGTH = 12

# propriedades que nao sao segredo (enderecos, portas, nomes)
NOT_SECRET = ("elasticsearch.address", "memorystore.host", "memorystore.port", "localEnvironment", "supportLanguage",
              "systems", "elasticsearch.snapshot.repository", "urlEmailKey", "urlEmailSuppressionKey",
              "urlInstantMessengerKey")

HOOK = """#!/bin/sh
# gravado por documentation/deploy/47-seguranca-segredos.py --instalar-hooks
GL="$USERPROFILE/tools/gitleaks/gitleaks.exe"
[ -x "$GL" ] || GL="$(cygpath -u "$USERPROFILE" 2>/dev/null)/tools/gitleaks/gitleaks.exe"
if [ ! -x "$GL" ]; then echo "pre-commit: gitleaks nao encontrado, commit sem varredura de segredos"; exit 0; fi
"$GL" protect --staged --redact --no-banner -c "%s" || {
  echo "pre-commit: gitleaks achou um segredo nos arquivos do commit. Tire o segredo e tente de novo."; exit 1; }
"""


def repositories():
    found = [("jobsnow_workspace", WORKSPACE)]
    for name in sorted(os.listdir(WORKSPACE)):
        path = os.path.join(WORKSPACE, name)
        if os.path.isdir(os.path.join(path, ".git")):
            found.append((name, path))
    return found


def flatten(value, prefix=""):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from flatten(item, prefix + "." + key if prefix else key)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            yield from flatten(item, "%s[%d]" % (prefix, index))
        return
    yield prefix, value


def secrets():
    sources = []
    if os.path.exists(PRODUCTION_PROPERTIES):
        with open(PRODUCTION_PROPERTIES, encoding="utf-8-sig") as handle:
            sources.append(("producao", json.load(handle)))
    local = os.environ.get("application_properties", "")
    if local:
        sources.append(("local", json.loads(local)))
    values = {}
    for origin, properties in sources:
        for name, value in flatten(properties):
            if name.split(".")[0].split("[")[0] in NOT_SECRET or name in NOT_SECRET:
                continue
            text = str(value)
            if len(text) < MIN_SECRET_LENGTH:
                continue
            values.setdefault(text, origin + ":" + name)
            # o token de bot do Telegram e "<id>:<segredo>": a parte secreta sozinha tambem conta
            if ":" in text and name.startswith("bots"):
                values.setdefault(text.split(":", 1)[1], origin + ":" + name + " (parte secreta)")
    return values


def search_exact_values(name, path, values):
    found = []
    listing = subprocess.run(["git", "-C", path, "cat-file", "--batch-all-objects", "--batch-check"],
                             capture_output=True, text=True, check=True).stdout.split("\n")
    blobs = [line.split()[0] for line in listing if line.endswith(tuple("0123456789")) and " blob " in line]
    if not blobs:
        return found
    process = subprocess.run(["git", "-C", path, "cat-file", "--batch"], input="\n".join(blobs).encode() + b"\n",
                             capture_output=True, check=True)
    data = process.stdout
    encoded = {secret.encode("utf-8"): label for secret, label in values.items()}
    position = 0
    while position < len(data):
        header_end = data.index(b"\n", position)
        object_id, _, size = data[position:header_end].split(b" ")
        start = header_end + 1
        end = start + int(size)
        content = data[start:end]
        for secret, label in encoded.items():
            if secret in content:
                found.append({"repository": name, "rule": "valor-exato", "property": label,
                              "object": object_id.decode()[:12]})
        position = end + 1
    return found


def run_gitleaks(name, path):
    report = os.path.join(OUT_DIR, "gitleaks-%s.json" % name)
    subprocess.run([GITLEAKS, "git", path, "--redact", "--no-banner", "-l", "error", "-c", CONFIG,
                    "-f", "json", "-r", report], capture_output=True)
    with open(report, encoding="utf-8") as handle:
        items = json.load(handle)
    os.remove(report)
    return [{"repository": name, "rule": item["RuleID"], "file": item["File"], "line": item["StartLine"],
             "commit": item["Commit"][:8], "date": item["Date"][:10], "fingerprint": item["Fingerprint"]}
            for item in items]


def known_findings():
    known = {}
    if not os.path.exists(KNOWN):
        return known
    with open(KNOWN, encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("#") or not line.strip():
                continue
            columns = line.rstrip("\n").split("\t")
            known[columns[0]] = columns[1] if len(columns) > 1 else ""
    return known


def install_hooks():
    config = CONFIG.replace("\\", "/")
    for name, path in repositories():
        hook = os.path.join(path, ".git", "hooks", "pre-commit")
        if os.path.exists(hook):
            with open(hook, encoding="utf-8", errors="replace") as handle:
                if "47-seguranca-segredos" not in handle.read():
                    print("%-60s ja tem um pre-commit proprio: mantido" % name)
                    continue
        with open(hook, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(HOOK % config)
        print("%-60s hook instalado" % name)


def main():
    if not os.path.exists(GITLEAKS):
        sys.exit("gitleaks nao encontrado em " + GITLEAKS)
    os.makedirs(OUT_DIR, exist_ok=True)
    if "--instalar-hooks" in sys.argv:
        install_hooks()
        return 0
    values = secrets()
    known = known_findings()
    findings = []
    rows = []
    for name, path in repositories():
        leaks = run_gitleaks(name, path)
        exact = search_exact_values(name, path, values)
        for leak in leaks:
            leak["status"] = known.get(leak["fingerprint"], "NOVO")
        for item in exact:
            item["status"] = known.get("%s:%s:%s" % (name, item["property"], item["object"]), "NOVO")
        findings.extend(leaks + exact)
        rows.append({"repository": name, "gitleaks": len(leaks), "exactValues": len(exact)})
    new = [item for item in findings if item["status"] == "NOVO"]
    result = {"when": datetime.datetime.now().isoformat(timespec="seconds"), "repositories": rows,
              "secretsChecked": len(values), "findings": findings, "new": len(new), "ok": not new}
    with open(os.path.join(OUT_DIR, "segredos.json"), "w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=1)
    print("repositorios: %d | segredos conferidos por valor exato: %d | achados: %d | novos: %d"
          % (len(rows), len(values), len(findings), len(new)))
    for item in findings:
        where = item.get("file", item.get("property")) + ":" + str(item.get("line", item.get("object")))
        print("  [%s] %s %s %s" % (item["status"], item["repository"], item["rule"], where))
    return 1 if new else 0


if __name__ == "__main__":
    sys.exit(main())
