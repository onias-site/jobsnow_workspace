#!/usr/bin/env python
"""Regrava swaggerCatalog.ts a partir do /api-docs das APIs locais e imprime o que mudou em relacao ao arquivo anterior.

Uma linha por dado, separada por TAB: ADICIONADO, RETIRADO, ALTERADO, SEM_RESUMO e TOTAL. Se uma API nao responder,
nada e gravado. As chaves e as listas saem ordenadas porque o springdoc muda a ordem a cada subida: sem isso, o arquivo
mudaria sem o Swagger ter mudado.
"""
import json
import pathlib
import re
import sys
import urllib.request

CATALOG = pathlib.Path("C:/eclipse-workspaces/ccp/jn_frontend_calistrato-react/presentation/pages/nosso-backend/swaggerCatalog.ts")

APIS = [
    {"title": "Swagger do JS", "url": "http://localhost:8082", "swaggerPage": "/swagger-ui-custom.html"},
    {"title": "Swagger do VIS", "url": "http://localhost:8081", "swaggerPage": "/swagger-ui.html"},
]

METHODS = ["get", "head", "post", "put", "patch", "delete"]

# parametros que o springdoc inventa para os mapas injetados nos controllers: nao existem para quem chama a API
GENERATED_PARAMETER = re.compile(r"^arg\d+$")

HEADER = """// GERADO pela skill /ccp-atualizar-tela-nosso-backend a partir do /api-docs das APIs locais: nao edite a mao, rode a skill.
// E o documento OpenAPI de cada API, porque o /api-docs nao libera CORS para o front. Os textos ficam em ingles, como no Swagger.

export interface BackendSwaggerSection {
    title: string;
    swaggerUrl: string;
    endpoints: number;
    spec: Record<string, any>;
}

export const swaggerSections: BackendSwaggerSection[] = """


def read_api_docs(api):
    with urllib.request.urlopen(api["url"] + "/api-docs", timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def clean_operation(operation):
    # o parametro obrigatorio que ninguem informa impediria o Execute da tela
    parameters = [item for item in operation.get("parameters", []) if not GENERATED_PARAMETER.match(item["name"])]
    return {**operation, "parameters": sorted(parameters, key=lambda item: (item.get("in", ""), item["name"]))}


def to_spec(docs):
    paths = {path: {method: clean_operation(operations[method]) for method in METHODS if method in operations} for path, operations in docs["paths"].items()}
    return {**docs, "paths": paths, "tags": sorted(docs.get("tags", []), key=lambda item: item["name"])}


def to_section(api, docs):
    spec = to_spec(docs)
    endpoints = sum(len(operations) for operations in spec["paths"].values())
    return {"title": api["title"], "swaggerUrl": api["url"] + api["swaggerPage"], "endpoints": endpoints, "spec": spec}


def read_previous_sections():
    if not CATALOG.exists():
        return []
    text = CATALOG.read_text(encoding="utf-8")
    start = text.index("BackendSwaggerSection[] = ") + len("BackendSwaggerSection[] = ")
    return json.loads(text[start:].rstrip().rstrip(";"))


def index_endpoints(sections):
    return {
        (section["title"], method.upper(), path): operation
        for section in sections
        for path, operations in section["spec"]["paths"].items()
        for method, operation in operations.items()
    }


def report(previous, sections):
    old = index_endpoints(previous)
    new = index_endpoints(sections)
    for key in sorted(new.keys() - old.keys()):
        print("ADICIONADO", *key, sep="\t")
    for key in sorted(old.keys() - new.keys()):
        print("RETIRADO", *key, sep="\t")
    for key in sorted(new.keys() & old.keys()):
        if new[key] != old[key]:
            print("ALTERADO", *key, sep="\t")
    for key, item in sorted(new.items()):
        if not item.get("summary"):
            print("SEM_RESUMO", *key, sep="\t")
    for section in sections:
        print("TOTAL", section["title"], section["endpoints"], sep="\t")


def main():
    sections = []
    for api in APIS:
        try:
            sections.append(to_section(api, read_api_docs(api)))
        except OSError as error:
            print("API_FORA_DO_AR", api["title"], api["url"], error, sep="\t")
            print("Nada foi gravado.")
            return 1
    previous = read_previous_sections()
    content = HEADER + json.dumps(sections, ensure_ascii=False, indent=4, sort_keys=True) + ";\n"
    with open(CATALOG, "w", encoding="utf-8", newline="\n") as catalog:
        catalog.write(content)
    report(previous, sections)
    return 0


if __name__ == "__main__":
    sys.exit(main())
