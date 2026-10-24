"""Relatorio das implementacoes de um tipo Java (padrao CcpBusiness), diretas ou indiretas.

Uma linha por classe concreta ou abstrata e uma por item de enum (o enum em si nao vira linha: cada item e uma
implementacao). Interfaces intermediarias entram no grafo mas nao no relatorio. Lambdas e classes anonimas nao tem nome
e ficam de fora.

Tamanho: classe de topo = o arquivo inteiro; classe aninhada e item de enum = o trecho da propria declaracao.

Uso: python relatorio_ccpbusiness.py [--tipo CcpBusiness] [--saida arquivo.md]
"""
import argparse
import collections
import os
import re
import sys

ROOT = r"C:\eclipse-workspaces\ccp"
SKIP_DIRS = {"documentation", "target", ".metadata", "node_modules", ".git", "bin", ".claude", ".settings"}

parser = argparse.ArgumentParser()
parser.add_argument("--tipo", default="CcpBusiness")
parser.add_argument("--saida", default="")
args = parser.parse_args()


def java_files():
    for top in sorted(os.listdir(ROOT)):
        path = os.path.join(ROOT, top)
        if top in SKIP_DIRS or not os.path.isdir(path):
            continue
        for dirpath, dirnames, files in os.walk(path):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for f in files:
                if f.endswith(".java"):
                    yield os.path.join(dirpath, f)


def mask(text):
    """Troca comentarios e literais por espacos, mantendo as posicoes."""
    out = list(text)
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if text.startswith("//", i):
            j = text.find("\n", i)
            j = n if j < 0 else j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
        elif text.startswith('"""', i):
            j = text.find('"""', i + 3)
            j = n if j < 0 else j + 3
        elif c == '"' or c == "'":
            j = i + 1
            while j < n and text[j] != c:
                j += 2 if text[j] == "\\" else 1
            j += 1
        else:
            i += 1
            continue
        for k in range(i, min(j, n)):
            if out[k] != "\n":
                out[k] = " "
        i = j
    return "".join(out)


def matching_brace(masked, open_index):
    depth = 0
    for k in range(open_index, len(masked)):
        ch = masked[k]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return k
    return len(masked) - 1


def strip_generics(s):
    previous = None
    while previous != s:
        previous = s
        s = re.sub(r"<[^<>]*>", "", s)
    return s


def simple_names(clause):
    return [p.strip().split(".")[-1] for p in clause.split(",") if p.strip()]


DECL = re.compile(r"(?<![@\w.])\b(class|interface|enum|record)\s+([A-Z]\w*)")

types = {}            # nome simples -> lista de declaracoes
supertypes = collections.defaultdict(set)
for path in java_files():
    raw = open(path, "rb").read()
    text = raw.decode("utf-8", errors="replace")
    masked = mask(text)
    module = os.path.relpath(path, ROOT).split(os.sep)[0]
    package_match = re.search(r"^\s*package\s+([\w.]+)\s*;", masked, re.M)
    package = package_match.group(1) if package_match else ""
    spans = []
    for m in DECL.finditer(masked):
        kind, name = m.group(1), m.group(2)
        brace = masked.find("{", m.end())
        if brace < 0:
            continue
        header = strip_generics(masked[m.end():brace])
        header = re.sub(r"\(.*\)", " ", header, flags=re.S)  # componentes de record
        ext = re.search(r"\bextends\s+(.*?)(?=\bimplements\b|$)", header, re.S)
        imp = re.search(r"\bimplements\s+(.*)$", header, re.S)
        parents = (simple_names(ext.group(1)) if ext else []) + (simple_names(imp.group(1)) if imp else [])
        end = matching_brace(masked, brace)
        line_start = masked.rfind("\n", 0, m.start()) + 1
        modifiers = masked[line_start:m.start()]
        decl = {"kind": kind, "name": name, "module": module, "path": path, "start": line_start, "brace": brace,
                "end": end, "parents": set(parents), "package": package, "abstract": "abstract" in modifiers, "text": text, "masked": masked, "raw_size": len(raw)}
        spans.append(decl)
        types.setdefault(name, []).append(decl)
        supertypes[name].update(parents)
    for d in spans:
        d["nested"] = any(o is not d and o["start"] <= d["start"] and d["end"] <= o["end"] for o in spans)

children = collections.defaultdict(set)
for name, parents in supertypes.items():
    for p in parents:
        children[p].add(name)

closure = set()
queue = collections.deque([args.tipo])
while queue:
    current = queue.popleft()
    for child in children[current]:
        if child not in closure:
            closure.add(child)
            queue.append(child)

collisions = sorted(n for n in closure if len(types.get(n, [])) > 1)


def size_of(text, start, end):
    piece = text[start:end + 1]
    return len(piece.encode("utf-8")), piece.count("\n") + 1


def enum_items(decl):
    masked, text = decl["masked"], decl["text"]
    i, end = decl["brace"] + 1, decl["end"]
    depth, item_start, items = 0, i, []
    while i < end:
        ch = masked[i]
        if ch in "({":
            depth += 1
        elif ch in ")}":
            depth -= 1
        elif depth == 0 and ch in ",;":
            items.append((item_start, i))
            item_start = i + 1
            if ch == ";":
                break
        i += 1
    else:
        items.append((item_start, end))
    result = []
    for s, e in items:
        chunk = masked[s:e]
        found = re.search(r"([A-Za-z_]\w*)", re.sub(r"@\w+(\([^)]*\))?", lambda m: " " * len(m.group(0)), chunk))
        if not found:
            continue
        first = s + len(chunk) - len(chunk.lstrip())
        last = s + len(chunk.rstrip()) - 1
        result.append((found.group(1), first, last))
    return result


rows = []
for name in closure:
    for decl in types.get(name, []):
        # com nome simples repetido, so entra a declaracao cujos pais estao no fecho
        if not decl["parents"] & (closure | {args.tipo}):
            continue
        kind = decl["kind"]
        # nome simples repetido: o pacote identifica a classe
        suffix = " (" + decl["package"] + ")" if name in collisions else ""
        if kind in ("interface",):
            continue
        if kind == "enum":
            items = enum_items(decl)
            for item, s, e in items:
                b, l = size_of(decl["text"], s, e)
                rows.append({"nome": name + "." + item + suffix, "tipo": "item de enum", "projeto": decl["module"], "bytes": b, "linhas": l})
            continue
        if decl["nested"]:
            b, l = size_of(decl["text"], decl["start"], decl["end"])
            tipo = "classe aninhada"
        else:
            b, l = decl["raw_size"], decl["text"].count("\n") + (0 if decl["text"].endswith("\n") else 1)
            tipo = "classe"
        if decl["abstract"]:
            tipo += " abstrata"
        rows.append({"nome": name + suffix, "tipo": tipo, "projeto": decl["module"], "bytes": b, "linhas": l})

if not rows:
    sys.exit("nenhuma implementacao de " + args.tipo)

avg_bytes = sum(r["bytes"] for r in rows) / len(rows)
avg_lines = sum(r["linhas"] for r in rows) / len(rows)
rows.sort(key=lambda r: (-r["bytes"], r["nome"]))


def br(n):
    return f"{n:,}".replace(",", ".")


def br_dec(x):
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


out = []
out.append(f"# Implementações de {args.tipo}")
out.append("")
out.append(f"**{len(rows)}** implementações (diretas e indiretas). Média: **{br_dec(avg_bytes)} bytes** e **{br_dec(avg_lines)} linhas**. "
           f"Acima da média: {sum(r['bytes'] > avg_bytes for r in rows)} em bytes e {sum(r['linhas'] > avg_lines for r in rows)} em linhas.")
out.append("")
by_kind = collections.Counter(r["tipo"] for r in rows)
out.append("Por tipo: " + " · ".join(f"{k} {v}" for k, v in by_kind.most_common()) + ".")
by_project = collections.Counter(r["projeto"] for r in rows)
out.append("")
out.append("Por projeto: " + " · ".join(f"{k} {v}" for k, v in by_project.most_common()) + ".")
if collisions:
    out.append("")
    out.append("Nomes simples repetidos em pacotes diferentes, identificados pelo pacote na coluna Nome: " + ", ".join(collisions) + ".")
out.append("")
out.append("`(acima)` = acima da média geral. Uma tabela por projeto, do que tem mais implementações para o que tem menos, "
           "cada uma ordenada por bytes.")

SHORT_KIND = {"classe": "classe", "classe aninhada": "aninhada", "classe abstrata": "abstrata", "item de enum": "enum"}
for project, count in by_project.most_common():
    project_rows = [r for r in rows if r["projeto"] == project]
    project_bytes = sum(r["bytes"] for r in project_rows)
    project_lines = sum(r["linhas"] for r in project_rows)
    out.append("")
    out.append(f"### {project} · {count} implementações · {br(project_bytes)} bytes · {br(project_lines)} linhas")
    out.append("")
    out.append("| # | Nome | Tipo | Bytes | Linhas |")
    out.append("|--:|---|---|--:|--:|")
    for i, r in enumerate(project_rows, 1):
        b = br(r["bytes"]) + (" (acima)" if r["bytes"] > avg_bytes else "")
        l = br(r["linhas"]) + (" (acima)" if r["linhas"] > avg_lines else "")
        out.append(f"| {i} | {r['nome']} | {SHORT_KIND.get(r['tipo'], r['tipo'])} | {b} | {l} |")
out.append("")
out.append(f"**Total geral:** {len(rows)} implementações · {br(sum(r['bytes'] for r in rows))} bytes · {br(sum(r['linhas'] for r in rows))} linhas.")
report = "\n".join(out) + "\n"

if args.saida:
    os.makedirs(os.path.dirname(os.path.abspath(args.saida)), exist_ok=True)
    open(args.saida, "w", encoding="utf-8").write(report)
    print("relatorio gravado em", args.saida)
    print("\n".join(out[:9]))
else:
    sys.stdout.reconfigure(encoding="utf-8")
    print(report)
