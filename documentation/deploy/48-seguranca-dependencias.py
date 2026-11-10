# Seguranca, item 3: vulnerabilidades conhecidas (CVE/GHSA) nas bibliotecas Java e do front end.
#
# Java: o proprio Maven resolve a arvore de runtime de cada modulo (dependency:list, offline), e cada biblioteca e
#       consultada na base publica OSV (api.osv.dev, que junta NVD, GitHub Advisory e outras). So vao para la as
#       coordenadas das bibliotecas (grupo:artefato:versao), nada do JobsNow.
# Front: npm audit no jn_frontend_calistrato-react, separando o que vai para producao (--omit=dev) do que so roda no
#        desenvolvimento.
#
# Achados aceitos (sem correcao possivel ou sem caminho de ataque no JobsNow) ficam em seguranca/dependencias-aceitas.tsv.
# Sai com codigo 1 quando ha vulnerabilidade ALTA ou CRITICA nao aceita num artefato que vai para producao (DEPLOYED). Resultado em c:/logs/seguranca/dependencias.json.
#
# Uso: python 48-seguranca-dependencias.py

import datetime
import glob
import json
import os
import re
import subprocess
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
WORKSPACE = os.path.abspath(os.path.join(HERE, "..", ".."))
FRONTEND = os.path.join(WORKSPACE, "jn_frontend_calistrato-react")
ACCEPTED = os.path.join(HERE, "seguranca", "dependencias-aceitas.tsv")
OUT_DIR = r"c:\logs\seguranca"
OSV_BATCH = "https://api.osv.dev/v1/querybatch"
OSV_VULN = "https://api.osv.dev/v1/vulns/"
DEPENDENCY_LINE = re.compile(r"^\s+([\w.\-]+):([\w.\-]+):(?:jar|pom|war)(?::[\w.\-]+)?:([\w.\-]+):(compile|runtime)")
# o que vai para producao: as duas APIs, o consumidor pull, o processo diario e o front (jn_frontend)
DEPLOYED = {"js_rest-api_spring_jobsnow_dependency-chooser", "vis_rest-api_spring_jobsnow_dependency-chooser",
            "ccp_mensageria-consumer_gcp-pubsub-pull_dependency-chooser", "ccp_cron-tasks_jobsnow", "jn_frontend"}
SEVERITY_ORDER = ["CRITICAL", "HIGH", "MODERATE", "MEDIUM", "LOW", "UNKNOWN"]


def post(url, payload):
    request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def get(url):
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.load(response)


def maven_dependencies():
    for old in glob.glob(os.path.join(WORKSPACE, "*", "target", "seguranca-deps.txt")):
        os.remove(old)
    subprocess.run("mvn -q -o dependency:list -DoutputFile=target/seguranca-deps.txt -DincludeScope=runtime",
                   cwd=WORKSPACE, shell=True, capture_output=True)
    libraries = {}
    for path in glob.glob(os.path.join(WORKSPACE, "*", "target", "seguranca-deps.txt")):
        module = os.path.basename(os.path.dirname(os.path.dirname(path)))
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                match = DEPENDENCY_LINE.match(line)
                if not match or match.group(1).startswith("com.ccp"):
                    continue
                key = (match.group(1) + ":" + match.group(2), match.group(3))
                libraries.setdefault(key, set()).add(module)
    return libraries


def severity_of(vulnerability):
    level = (vulnerability.get("database_specific") or {}).get("severity")
    if level:
        return level.upper()
    for affected in vulnerability.get("affected", []):
        level = (affected.get("database_specific") or {}).get("severity")
        if level:
            return level.upper()
    return "UNKNOWN"


def fixed_versions(vulnerability, package):
    versions = []
    for affected in vulnerability.get("affected", []):
        if affected.get("package", {}).get("name") != package:
            continue
        for interval in affected.get("ranges", []):
            versions += [event["fixed"] for event in interval.get("events", []) if "fixed" in event]
    return sorted(set(versions))


def java_findings(libraries):
    keys = sorted(libraries)
    findings = []
    details = {}
    for start in range(0, len(keys), 500):
        chunk = keys[start:start + 500]
        queries = [{"package": {"ecosystem": "Maven", "name": name}, "version": version} for name, version in chunk]
        answer = post(OSV_BATCH, {"queries": queries})
        for (name, version), result in zip(chunk, answer["results"]):
            for vulnerability in result.get("vulns", []):
                identifier = vulnerability["id"]
                if identifier not in details:
                    details[identifier] = get(OSV_VULN + identifier)
                full = details[identifier]
                aliases = [alias for alias in full.get("aliases", []) if alias.startswith("CVE-")]
                findings.append({"ecosystem": "maven", "package": name, "version": version, "id": identifier,
                                 "cve": ",".join(aliases), "severity": severity_of(full),
                                 "summary": (full.get("summary") or full.get("details", ""))[:160],
                                 "fixed": ",".join(fixed_versions(full, name)),
                                 "modules": sorted(libraries[(name, version)])})
    return findings


def npm_findings(scope):
    command = "npm audit --json" + (" --omit=dev" if scope == "producao" else "")
    output = subprocess.run(command, cwd=FRONTEND, shell=True, capture_output=True, text=True, encoding="utf-8").stdout
    report = json.loads(output or "{}")
    findings = []
    for name, item in report.get("vulnerabilities", {}).items():
        for via in item.get("via", []):
            if not isinstance(via, dict):
                continue
            advisory = via.get("url", "").rsplit("/", 1)[-1]
            findings.append({"ecosystem": "npm-" + scope, "package": name, "version": item.get("range", ""),
                             "id": advisory, "cve": "", "severity": via.get("severity", "unknown").upper(),
                             "summary": via.get("title", "")[:160],
                             "fixed": "sim" if item.get("fixAvailable") else "nao", "modules": ["jn_frontend"]})
    return findings


def accepted():
    items = {}
    if os.path.exists(ACCEPTED):
        with open(ACCEPTED, encoding="utf-8") as handle:
            for line in handle:
                if line.strip() and not line.startswith("#"):
                    columns = line.rstrip("\n").split("\t")
                    items[columns[0]] = columns[1] if len(columns) > 1 else ""
    return items


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    libraries = maven_dependencies()
    findings = java_findings(libraries) + npm_findings("producao") + npm_findings("desenvolvimento")
    production_npm = {(item["package"], item["id"]) for item in findings if item["ecosystem"] == "npm-producao"}
    findings = [item for item in findings
                if item["ecosystem"] != "npm-desenvolvimento" or (item["package"], item["id"]) not in production_npm]
    acceptance = accepted()
    for item in findings:
        item["accepted"] = acceptance.get(item["package"] + "@" + item["id"]) or acceptance.get(item["id"], "")
        item["deployed"] = sorted(DEPLOYED.intersection(item["modules"]))
    findings.sort(key=lambda item: (SEVERITY_ORDER.index(item["severity"]) if item["severity"] in SEVERITY_ORDER else 9,
                                    item["package"]))
    blocking = [item for item in findings if item["severity"] in ("CRITICAL", "HIGH") and not item["accepted"]
                and item["ecosystem"] != "npm-desenvolvimento" and item["deployed"]]
    result = {"when": datetime.datetime.now().isoformat(timespec="seconds"), "javaLibraries": len(libraries),
              "findings": findings, "blocking": len(blocking), "ok": not blocking}
    with open(os.path.join(OUT_DIR, "dependencias.json"), "w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=1)
    print("bibliotecas Java: %d | achados: %d | altas/criticas sem aceite nos artefatos de producao: %d"
          % (len(libraries), len(findings), len(blocking)))
    for item in findings:
        print("  %-9s %-20s %-45s %-14s %-22s corrigida em: %s%s" % (
            item["severity"], item["ecosystem"], item["package"], item["version"][:14], item["cve"] or item["id"],
            item["fixed"][:30], "  [aceito]" if item["accepted"] else ""))
    return 1 if blocking else 0


if __name__ == "__main__":
    sys.exit(main())
