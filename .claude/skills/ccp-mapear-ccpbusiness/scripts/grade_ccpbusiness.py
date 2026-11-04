"""Grade dos subtipos de um tipo Java (padrao CcpBusiness), diretos e indiretos, ordenada por bytes.

Uma linha por classe ou interface do fecho transitivo e uma por item de enum (Enum.Item): cada item de enum e uma
implementacao propria, entao o enum em si nao vira linha. Colunas # | Tipo | Bytes | Linhas, desenhada com caracteres
de caixa. Mesma base do map-subtypes.ps1: o projeto de testes fica de fora, a menos que se passe --incluir-testes.

Tamanho: tipo de topo = o arquivo inteiro (bytes no disco e linhas); tipo aninhado = o trecho da propria declaracao;
item de enum = o trecho do item, do nome ate a virgula ou o ponto e virgula, com o corpo. Item de enum sem corpo
(so o nome, ou o nome com argumentos do construtor) fica fora da lista. Ao final, media e mediana de bytes e linhas.

Uso: python -X utf8 grade_ccpbusiness.py [--tipo CcpBusiness] [--incluir-testes] [--saida arquivo.txt]
"""
import argparse
import collections
import os
import re
import statistics
import sys

ROOT = r"C:\eclipse-workspaces\ccp"
SKIP_DIRS = {"documentation", "target", ".metadata", "node_modules", ".git", "bin", ".claude", ".settings"}
TESTS = "ccp_rest-api-tests_jobsnow"

parser = argparse.ArgumentParser()
parser.add_argument("--tipo", default="CcpBusiness")
parser.add_argument("--incluir-testes", action="store_true")
parser.add_argument("--saida", default="")
args = parser.parse_args()


def java_files():
    for top in sorted(os.listdir(ROOT)):
        path = os.path.join(ROOT, top)
        if top in SKIP_DIRS or not os.path.isdir(path):
            continue
        if top == TESTS and not args.incluir_testes:
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

types = {}
supertypes = collections.defaultdict(set)
for path in java_files():
    raw = open(path, "rb").read()
    text = raw.decode("utf-8", errors="replace")
    masked = mask(text)
    package_match = re.search(r"^\s*package\s+([\w.]+)\s*;", masked, re.M)
    package = package_match.group(1) if package_match else ""
    spans = []
    for m in DECL.finditer(masked):
        brace = masked.find("{", m.end())
        if brace < 0:
            continue
        header = strip_generics(masked[m.end():brace])
        header = re.sub(r"\(.*\)", " ", header, flags=re.S)
        ext = re.search(r"\bextends\s+(.*?)(?=\bimplements\b|$)", header, re.S)
        imp = re.search(r"\bimplements\s+(.*)$", header, re.S)
        parents = (simple_names(ext.group(1)) if ext else []) + (simple_names(imp.group(1)) if imp else [])
        name = m.group(2)
        decl = {"name": name, "kind": m.group(1), "start": masked.rfind("\n", 0, m.start()) + 1, "brace": brace,
                "end": matching_brace(masked, brace), "parents": set(parents), "package": package, "text": text,
                "masked": masked, "raw_size": len(raw)}
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
        if child not in closure and child != args.tipo:
            closure.add(child)
            queue.append(child)

collisions = {n for n in closure if len(types.get(n, [])) > 1}

def has_body(chunk):
    """Item de enum com corpo: uma chave aberta fora dos parenteses dos argumentos do construtor."""
    depth = 0
    for ch in chunk:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "{" and depth == 0:
            return True
    return False


def enum_items(decl):
    """Itens de um enum: (nome, inicio, fim), do nome do item ate a virgula ou o ponto e virgula, com o corpo."""
    masked = decl["masked"]
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
        without_annotations = re.sub(r"@\w+(\([^)]*\))?", lambda a: " " * len(a.group(0)), chunk)
        found = re.search(r"([A-Za-z_]\w*)", without_annotations)
        if not found:
            continue
        if not has_body(chunk):
            continue
        first = s + len(chunk) - len(chunk.lstrip())
        last = s + len(chunk.rstrip()) - 1
        result.append((found.group(1), first, last))
    return result


def size_of(text, start, end):
    piece = text[start:end + 1]
    return len(piece.encode("utf-8")), piece.count("\n") + 1


rows = []
enums = 0
for name in closure:
    for decl in types.get(name, []):
        # com nome simples repetido, so entra a declaracao cujos pais estao no fecho
        if not decl["parents"] & (closure | {args.tipo}):
            continue
        suffix = " (" + decl["package"] + ")" if name in collisions else ""
        if decl["kind"] == "enum":
            # cada item do enum e uma implementacao: uma linha por item, o enum em si nao vira linha
            enums += 1
            for item, s, e in enum_items(decl):
                size, lines = size_of(decl["text"], s, e)
                rows.append((name + "." + item + suffix, size, lines))
            continue
        if decl["nested"]:
            piece = decl["text"][decl["start"]:decl["end"] + 1]
            size, lines = len(piece.encode("utf-8")), piece.count("\n") + 1
        else:
            size = decl["raw_size"]
            lines = decl["text"].count("\n") + (0 if decl["text"].endswith("\n") else 1)
        rows.append((name + suffix, size, lines))

if not rows:
    sys.exit("nenhum subtipo de " + args.tipo)

rows.sort(key=lambda r: (-r[1], r[0]))


def br(n):
    return f"{n:,}".replace(",", ".")


headers = ["#", "Tipo", "Bytes", "Linhas"]
cells = [[str(i), label, br(size), br(lines)] for i, (label, size, lines) in enumerate(rows, 1)]
widths = [max(len(h), *(len(c[k]) for c in cells)) for k, h in enumerate(headers)]
right = [False, False, True, True]
H, V = "\u2500", "\u2502"


def border(left, middle, end):
    return left + middle.join(H * (w + 2) for w in widths) + end


def line(values, header=False):
    parts = []
    for value, width, align_right in zip(values, widths, right):
        text = value.rjust(width) if align_right and not header else value.ljust(width)
        parts.append(" " + text + " ")
    return V + V.join(parts) + V


out = [border("\u250c", "\u252c", "\u2510"), line(headers, True), border("\u251c", "\u253c", "\u2524")]
out += [line(c) for c in cells]
out.append(border("\u2514", "\u2534", "\u2518"))
total_bytes = sum(r[1] for r in rows)
total_lines = sum(r[2] for r in rows)
enum_rows = sum(1 for r in rows if "." in r[0].split(" ")[0])


def br_dec(x):
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


summary = (f"{len(rows)} linhas de {args.tipo} ({len(rows) - enum_rows} tipos sem enum + {enum_rows} itens com corpo "
           f"de {enums} enums; itens sem corpo ficam de fora) · {br(total_bytes)} bytes · {br(total_lines)} linhas")
stats = (f"Bytes: média {br_dec(statistics.mean(r[1] for r in rows))} · mediana {br_dec(statistics.median(r[1] for r in rows))}\n"
         f"Linhas: média {br_dec(statistics.mean(r[2] for r in rows))} · mediana {br_dec(statistics.median(r[2] for r in rows))}")
report = summary + "\n\n" + "\n".join(out) + "\n\n" + stats + "\n"

if args.saida:
    os.makedirs(os.path.dirname(os.path.abspath(args.saida)), exist_ok=True)
    open(args.saida, "w", encoding="utf-8").write(report)
    print("grade gravada em", args.saida)
    print(summary)
    print(stats)
else:
    sys.stdout.reconfigure(encoding="utf-8")
    print(report)
