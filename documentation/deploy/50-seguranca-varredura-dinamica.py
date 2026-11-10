# Seguranca, item 4: varredura dinamica das APIs LOCAIS (vis 8081 e js 8082), guiada pelo OpenAPI de cada uma
# (/api-docs). Nunca roda contra producao: o alvo e sempre localhost, e o script recusa outro host.
#
# Para cada operacao do OpenAPI:
#   - injecao nos parametros de caminho e no corpo (aspas, JSON e query do Elasticsearch, travessia de pasta, script,
#     texto enorme, unicode, CRLF): a API nao pode responder 500 nem devolver detalhes internos (stack trace, nome de
#     classe Java, mensagem do Elasticsearch, caminho de arquivo).
#   - metodos nao previstos (PUT, PATCH, TRACE) nao podem dar 2xx nem 500.
# Para cada API:
#   - cabecalhos de seguranca (nosniff, X-Frame-Options, ausencia de X-Powered-By e de versao do servidor).
#   - CORS: uma origem estranha (https://evil.example) nao pode ser refletida com Allow-Credentials true; uma origem
#     qualquer liberada (*) e registrada como aviso nas rotas com sessao.
#   - rotas que so existem no local (/login/{email}/erro) e o Swagger, que nao podem existir em producao (aviso).
#
# Resultado em c:/logs/seguranca/varredura-dinamica.json (pagina Backend > Seguranca do portal 37); sai com 1 se ha
# achado ALTO. Uso: python 50-seguranca-varredura-dinamica.py

import datetime
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

APIS = {"vis": "http://localhost:8081", "js": "http://localhost:8082"}
OUT_DIR = r"c:\logs\seguranca"
EVIL_ORIGIN = "https://evil.example"
EMAIL = "varredura.seguranca@teste.com"
PAYLOADS = [
    "'\"<>",
    "{\"query\":{\"match_all\":{}}}",
    "*",
    "..%2F..%2F..%2Fetc%2Fpasswd",
    "../../../../windows/win.ini",
    "<script>alert(1)</script>",
    "${jndi:ldap://127.0.0.1/a}",
    "#{7*7}",
    "A" * 5000,
    "\u202e\u0000\uffff",
    "%0d%0aSet-Cookie:%20x=1",
    "-1",
    "99999999999999999999",
]
LEAK_PATTERNS = [
    (re.compile(r"\bat (com|org|java|jdk|sun)\.[\w.$]+\("), "stack trace"),
    (re.compile(r"\b(java|javax|jakarta|org\.springframework|org\.eclipse\.jetty)\.[\w.]+(Exception|Error)\b"), "excecao Java"),
    (re.compile(r"(?i)elasticsearch|\"caused_by\"|search_phase_execution|index_not_found"), "detalhe do Elasticsearch"),
    (re.compile(r"(?i)[a-z]:\\\\(eclipse-workspaces|users|logs)|/opt/jobsnow"), "caminho de arquivo"),
    (re.compile(r"(?i)root:x:0:0|\[fonts\]"), "conteudo de arquivo do sistema"),
]
findings = []
requests_sent = 0


def assert_local(url):
    host = urllib.parse.urlparse(url).hostname
    if host not in ("localhost", "127.0.0.1"):
        sys.exit("alvo recusado (so localhost): " + url)


def request(method, url, body=None, headers=None):
    global requests_sent
    assert_local(url)
    data = body.encode("utf-8") if isinstance(body, str) else body
    all_headers = {"Content-Type": "application/json", "User-Agent": "jobsnow-varredura-local"}
    all_headers.update(headers or {})
    req = urllib.request.Request(url, data=data, method=method, headers=all_headers)
    requests_sent += 1
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.status, dict(response.headers), response.read(200000).decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers), error.read(200000).decode("utf-8", "replace")
    except Exception as error:
        return 0, {}, str(error)


def finding(level, api, where, text):
    key = (level, api, where, text)
    if key not in {(f["level"], f["api"], f["where"], f["text"]) for f in findings}:
        findings.append({"level": level, "api": api, "where": where, "text": text})


def leaks(body):
    return [name for pattern, name in LEAK_PATTERNS if pattern.search(body)]


def fill_path(path, value):
    def replace(match):
        name = match.group(1)
        if name == "email":
            return EMAIL
        return urllib.parse.quote(value, safe="%") if value is not None else "x"
    return re.sub(r"\{(\w+)\}", replace, path)


def check_response(api, method, path, payload, status, body):
    where = "%s %s" % (method, path)
    if status >= 500:
        finding("ALTO", api, where, "respondeu %d com a entrada %r" % (status, payload[:40]))
    found = leaks(body)
    if found:
        finding("ALTO", api, where, "vazou %s (entrada %r): %s" % (",".join(found), payload[:40], body[:160].replace("\n", " ")))
    if "<script>alert(1)</script>" in body and status < 300:
        finding("MEDIO", api, where, "devolveu o script da entrada sem escapar (corpo JSON, risco so se renderizado)")


def scan_operations(api, base, spec):
    for path, operations in spec.get("paths", {}).items():
        for method, operation in operations.items():
            method = method.upper()
            if method not in ("GET", "POST", "DELETE", "PUT", "PATCH", "HEAD"):
                continue
            # o webhook tem suite propria (secreto do bot); /erro existe so no local e responde 500 de proposito
            if "telegram-webhook" in path or path.endswith("/erro"):
                continue
            has_path_parameters = "{" in path.replace("{email}", "")
            for payload in PAYLOADS:
                url_path = fill_path(path, payload if has_path_parameters else None)
                body = json.dumps({"payload": payload, "title": payload, "description": payload, "type": payload,
                                   "search": payload, "skill": payload, "text": payload})
                status, _, response_body = request(method, base + url_path, body)
                check_response(api, method, path, payload, status, response_body)
            status, _, response_body = request(method, base + fill_path(path, "x"), "{\"x\":")
            check_response(api, method, path, "json quebrado", status, response_body)
        for extra in ("PUT", "PATCH", "TRACE"):
            if extra.lower() in operations:
                continue
            status, _, response_body = request(extra, base + fill_path(path, "x"), "{}")
            if 200 <= status < 300 or status >= 500:
                finding("MEDIO" if status < 500 else "ALTO", api, "%s %s" % (extra, path), "metodo nao previsto respondeu %d" % status)


def scan_headers_and_cors(api, base, spec):
    status, headers, _ = request("GET", base + "/rota-inexistente-da-varredura")
    lower = {key.lower(): value for key, value in headers.items()}
    if "x-powered-by" in lower:
        finding("BAIXO", api, "cabecalhos", "X-Powered-By: " + lower["x-powered-by"])
    if re.search(r"\d", lower.get("server", "")):
        finding("BAIXO", api, "cabecalhos", "Server com versao: " + lower["server"])
    for name, level in (("x-content-type-options", "BAIXO"), ("x-frame-options", "BAIXO"), ("cache-control", "BAIXO")):
        if name not in lower:
            finding(level, api, "cabecalhos", "sem " + name)
    session_paths = [path for path in spec.get("paths", {}) if path.startswith(("/resume", "/recruiter", "/grouper", "/login"))]
    for path in session_paths[:3]:
        url = base + fill_path(path, "x")
        _, headers, _ = request("OPTIONS", url, headers={"Origin": EVIL_ORIGIN, "Access-Control-Request-Method": "GET",
                                                          "Access-Control-Request-Headers": "sessionToken"})
        lower = {key.lower(): value for key, value in headers.items()}
        allowed = lower.get("access-control-allow-origin", "")
        credentials = lower.get("access-control-allow-credentials", "").lower() == "true"
        if allowed == EVIL_ORIGIN and credentials:
            finding("ALTO", api, "CORS " + path, "reflete qualquer origem com Allow-Credentials true")
        if allowed in ("*", EVIL_ORIGIN):
            finding("BAIXO", api, "CORS " + path, "aceita qualquer origem (%s); a sessao vai em cabecalho, nao em cookie, "
                    "entao outro site nao a usa sozinho, mas o ideal e liberar so https://onias.site" % allowed)


def scan_local_only_routes(api, base):
    for path in ("/swagger-ui.html", "/swagger-ui-custom.html", "/api-docs", "/login/" + EMAIL + "/erro"):
        status, _, body = request("GET", base + path)
        if status == 200 or (status == 302 and "swagger" in path):
            finding("INFO", api, "GET " + path, "existe no local (%d): conferir que esta fechado em producao" % status)
        found = leaks(body)
        if found:
            finding("MEDIO", api, "GET " + path, "vazou " + ",".join(found))


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    operations = 0
    for api, base in APIS.items():
        status, _, body = request("GET", base + "/api-docs")
        if status != 200:
            sys.exit("API %s fora do ar ou sem /api-docs em %s (status %d)" % (api, base, status))
        spec = json.loads(body)
        operations += sum(len(item) for item in spec.get("paths", {}).values())
        scan_headers_and_cors(api, base, spec)
        scan_local_only_routes(api, base)
        scan_operations(api, base, spec)
    order = ["ALTO", "MEDIO", "BAIXO", "INFO"]
    findings.sort(key=lambda item: (order.index(item["level"]), item["api"], item["where"]))
    high = [item for item in findings if item["level"] == "ALTO"]
    result = {"when": datetime.datetime.now().isoformat(timespec="seconds"), "operations": operations,
              "requests": requests_sent, "findings": findings, "high": len(high), "ok": not high}
    with open(os.path.join(OUT_DIR, "varredura-dinamica.json"), "w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=1)
    print("operacoes: %d | requisicoes: %d | achados: %d (altos: %d)" % (operations, requests_sent, len(findings), len(high)))
    for item in findings:
        print("  %-5s %-3s %-60s %s" % (item["level"], item["api"], item["where"][:60], item["text"][:150]))
    return 1 if high else 0


if __name__ == "__main__":
    sys.exit(main())
