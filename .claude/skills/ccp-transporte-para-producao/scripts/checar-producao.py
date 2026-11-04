# Checagem do transporte para producao (skill ccp-transporte-para-producao). So le: nao grava nada em nenhum ES.
# 1. Indices: os do codigo (configuradores de entidade e suas gemeas) contra os do destino e os da origem.
# 2. Campos: o mapeamento de cada indice na origem contra o do destino (dynamic strict: campo novo sem mapeamento
#    em producao faz a escrita falhar la).
# 3. Nomes de classe: toda string com cara de classe do projeto (com.ccp|jn|vis|jb|js...) gravada nos indices
#    marcados com varrer_classes=sim no entidades.tsv precisa existir no codigo; senao houve renomeio sem script.
# 4. Registros: as entidades de regra igual/adaptar/merge/carga do entidades.tsv, origem contra destino.
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python -X utf8 checar-producao.py [url do destino] [url da origem]
#      destino padrao: o tunel de producao (http://127.0.0.1:9210); origem padrao: o ES local (http://127.0.0.1:9200)
# Sai com 1 quando ha pendencia, 0 quando producao esta em dia com o codigo e com o local.
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

target_url = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:9210"
source_url = sys.argv[2].rstrip("/") if len(sys.argv) > 2 else "http://127.0.0.1:9200"
target_auth = os.environ.get("ES_DESTINO_AUTH", "")
skill_folder = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
workspace = os.path.dirname(os.path.dirname(os.path.dirname(skill_folder)))
prefixes = ("jn_", "jb_", "js_", "vis_")
business_modules = ("jn_business_jobsnow", "js_business_jobsnow", "vis_business_jobsnow", "jb_business_jobsnow")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
pending = []


def call(url, method, path, body=None, authorization=""):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if authorization:
        request.add_header("Authorization", authorization)
    with opener.open(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def report(text):
    pending.append(text)
    print("  PENDENTE: " + text)


def scan(url, authorization, index):
    first = call(url, "POST", "/%s/_search?scroll=2m" % index, {"size": 1000, "sort": ["_doc"]}, authorization)
    hits = first["hits"]["hits"]
    scroll_id = first.get("_scroll_id")
    documents = {}
    while hits:
        for hit in hits:
            documents[hit["_id"]] = hit["_source"]
        page = call(url, "POST", "/_search/scroll", {"scroll": "2m", "scroll_id": scroll_id}, authorization)
        hits = page["hits"]["hits"]
        scroll_id = page.get("_scroll_id", scroll_id)
    if scroll_id:
        try:
            call(url, "DELETE", "/_search/scroll", {"scroll_id": scroll_id}, authorization)
        except urllib.error.HTTPError:
            pass
    return documents


def es_indices(url, authorization):
    rows = call(url, "GET", "/_cat/indices?format=json&h=index", None, authorization)
    return {row["index"] for row in rows if row["index"].startswith(prefixes)}


def java_files():
    for module in os.listdir(workspace):
        source_root = os.path.join(workspace, module, "src", "main", "java")
        if not os.path.isdir(source_root):
            continue
        for folder, _, files in os.walk(source_root):
            for name in files:
                if name.endswith(".java"):
                    path = os.path.join(folder, name)
                    relative = os.path.relpath(path, source_root)[:-5]
                    yield module, relative.replace(os.sep, "."), path


def read(path):
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read()


def code_indices(classes):
    indices = {}
    for module, fqn, _ in java_files():
        if module not in business_modules:
            continue
        simple = fqn.rsplit(".", 1)[-1]
        match = re.match(r"^(Jn|Vis|Jb|Js)Entity([A-Z]\w*)$", simple)
        if not match:
            continue
        text = classes[fqn]
        if "implements CcpEntityConfigurator" not in text:
            continue
        rest = re.sub(r"(?<!^)(?=[A-Z])", "_", match.group(2)).lower()
        indices[match.group(1).lower() + "_" + rest] = simple
        for twin in re.findall(r'twinEntityName\s*=\s*"([a-z_]+)"', text):
            indices[twin] = simple + " (gemea)"
    return indices


def flatten_mapping(properties, prefix=""):
    fields = {}
    for name, definition in properties.items():
        path = prefix + name
        if "properties" in definition:
            fields.update(flatten_mapping(definition["properties"], path + "."))
            continue
        fields[path] = definition.get("type", "object")
    return fields


def mapping_fields(url, authorization, index):
    answer = call(url, "GET", "/%s/_mapping" % index, None, authorization)
    mapping = next(iter(answer.values()))["mappings"]
    return flatten_mapping(mapping.get("properties", {}))


def resolves(name, classes):
    tokens = name.split(".")
    for size in range(len(tokens), 1, -1):
        pieces = tokens[size - 1].split("$")
        fqn = ".".join(tokens[:size - 1] + [pieces[0]])
        text = classes.get(fqn)
        if text is None:
            continue
        for member in pieces[1:] + tokens[size:]:
            declared = re.search(r"\b(class|enum|interface|record)\s+%s\b" % re.escape(member), text)
            constant = re.search(r"^\s*%s\s*[,;({]" % re.escape(member), text, re.MULTILINE)
            if not declared and not constant:
                return False
        return True
    return False


def strings_of(value, path=""):
    if isinstance(value, str):
        yield path, value
        return
    if isinstance(value, dict):
        for key, item in value.items():
            yield from strings_of(item, path + "." + key if path else key)
        return
    if isinstance(value, list):
        for item in value:
            yield from strings_of(item, path + "[]")


def fingerprint(document, ignored):
    kept = {key: value for key, value in document.items() if key not in ignored}
    return hashlib.sha1(json.dumps(kept, sort_keys=True).encode("utf-8")).hexdigest()


def load_rules():
    rules = {}
    with open(os.path.join(skill_folder, "entidades.tsv"), encoding="utf-8") as handle:
        lines = handle.read().splitlines()
    for line in lines[1:]:
        if not line.strip():
            continue
        index, entity, rule, environment_fields, scan_classes = (line.split("\t") + ["", "", "", "", ""])[:5]
        fields = {field for field in environment_fields.split(",") if field}
        rules[index] = {"entity": entity, "rule": rule, "fields": fields, "scan": scan_classes == "sim"}
    return rules


classes = {fqn: read(path) for _, fqn, path in java_files()}
code = code_indices(classes)
rules = load_rules()
print("codigo: %d indices (configuradores e gemeas), %d classes" % (len(code), len(classes)))
print("origem:", call(source_url, "GET", "/")["cluster_name"], source_url)
print("destino:", call(target_url, "GET", "/", None, target_auth)["cluster_name"], target_url)
target_indices = es_indices(target_url, target_auth)
source_indices = es_indices(source_url, "")

print("\n[0] entidades.tsv contra o codigo")
for index in sorted(set(code) - set(rules)):
    report("%s (%s) nao esta no entidades.tsv: classifique a regra de transporte" % (index, code[index]))
for index in sorted(set(rules) - set(code)):
    report("%s esta no entidades.tsv mas nao existe no codigo: retire a linha" % index)

print("\n[1] indices: codigo contra destino e origem")
for index in sorted(set(code) - target_indices):
    report("%s (%s) existe no codigo e nao no destino: falta script que crie o indice" % (index, code[index]))
for index in sorted(target_indices - set(code)):
    report("%s existe no destino e nao no codigo: falta script que apague o indice (depois do backup)" % index)
for index in sorted(set(code) - source_indices):
    print("  aviso: %s nao existe na origem: recrie as entidades locais (CcpCreateEntities)" % index)
for index in sorted(source_indices - set(code)):
    print("  aviso: %s existe so na origem, sem entidade no codigo (sobra local)" % index)

print("\n[2] campos: mapeamento da origem contra o do destino")
for index in sorted(set(code) & target_indices & source_indices):
    source_fields = mapping_fields(source_url, "", index)
    target_fields = mapping_fields(target_url, target_auth, index)
    for field in sorted(set(source_fields) - set(target_fields)):
        report("%s.%s (%s) falta no destino: falta script que acrescente o campo" % (index, field, source_fields[field]))
    for field in sorted(set(target_fields) - set(source_fields)):
        print("  aviso: %s.%s existe so no destino (campo retirado do codigo?)" % (index, field))
    for field in sorted(set(source_fields) & set(target_fields)):
        if source_fields[field] != target_fields[field]:
            report("%s.%s e %s na origem e %s no destino: tipo nao muda no lugar, exige reindexar" % (index, field, source_fields[field], target_fields[field]))

print("\n[3] nomes de classe gravados no destino")
class_pattern = re.compile(r"\bcom\.(?:ccp|jn|vis|jb|js)(?:\.[A-Za-z_$][\w$]*)+")
checked = 0
for index in sorted(name for name, rule in rules.items() if rule["scan"] and name in target_indices):
    for document_id, document in scan(target_url, target_auth, index).items():
        for path, text in strings_of(document):
            for name in class_pattern.findall(text):
                checked += 1
                if not resolves(name, classes):
                    report("%s/%s campo %s: %s nao existe no codigo (renomeio sem script)" % (index, document_id, path, name))
print("  %d nomes de classe conferidos" % checked)

print("\n[4] registros das entidades levadas para producao")
for index, rule in sorted(rules.items()):
    kind = rule["rule"]
    if kind == "nao-levar" or index not in target_indices or index not in source_indices:
        continue
    if kind == "carga":
        source_count = call(source_url, "GET", "/%s/_count" % index)["count"]
        target_count = call(target_url, "GET", "/%s/_count" % index, None, target_auth)["count"]
        if source_count != target_count:
            report("%s: %d na origem e %d no destino: a carga das vagas vai em bloco (10, 11 e 21)" % (index, source_count, target_count))
        continue
    source_documents = scan(source_url, "", index)
    target_documents = scan(target_url, target_auth, index)
    missing = sorted(set(source_documents) - set(target_documents))
    if missing:
        report("%s: %d registro(s) da origem faltam no destino (ex.: %s)" % (index, len(missing), ", ".join(missing[:3])))
    if kind == "merge":
        extra = len(set(target_documents) - set(source_documents))
        if extra:
            print("  aviso: %s tem %d registro(s) so no destino, nascidos em producao: o transporte e merge" % (index, extra))
        continue
    for document_id in sorted(set(source_documents) & set(target_documents)):
        source_document = source_documents[document_id]
        target_document = target_documents[document_id]
        if fingerprint(source_document, rule["fields"]) == fingerprint(target_document, rule["fields"]):
            continue
        keys = set(source_document) | set(target_document)
        different = sorted(key for key in keys - rule["fields"] if source_document.get(key) != target_document.get(key))
        report("%s/%s difere nos campos %s" % (index, document_id, ", ".join(different)))
    extra = sorted(set(target_documents) - set(source_documents))
    if extra:
        report("%s: %d registro(s) so no destino (ex.: %s): apagados ou com chave trocada no codigo?" % (index, len(extra), ", ".join(extra[:3])))

print("\n%d pendencia(s)" % len(pending))
sys.exit(1 if pending else 0)
