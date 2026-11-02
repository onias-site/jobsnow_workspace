#!/usr/bin/env python
"""Compara as regras de arquitetura e os centros de custo do CLAUDE.md com o catalogo de conceitos da tela "Nosso backend".

Somente leitura. Saida, uma linha por dado, separada por TAB:
  ADICIONAR <secao> <sigla> <acronimo> <regra no CLAUDE.md>   esta no CLAUDE.md e falta no catalogo
  RETIRAR <secao> <sigla>                                     esta no catalogo e nao existe mais no CLAUDE.md
  MOVER <sigla> <secao no catalogo> <secao no CLAUDE.md>      a regra mudou de secao
  ACRONIMO <sigla> <na tela> <no CLAUDE.md>                   o nome por extenso mudou
  DESCRICAO <sigla> <explicacao da tela> <regra no CLAUDE.md> para comparar o sentido dos dois
  SEM_SIGLA <acronimo>                                        regra sem sigla entre parenteses
  SIGLA_REPETIDA <sigla>                                      a mesma sigla em duas regras
  SECAO_NOVA <secao>                                          secao do CLAUDE.md sem traducao em SECTIONS
  CENTRO_ADICIONAR <sigla>, CENTRO_RETIRAR <sigla>            centros de custo da regra de dependencia do CLAUDE.md
  TOTAL <regras no CLAUDE.md> <regras no catalogo> <centros no CLAUDE.md> <centros no catalogo>
"""
import collections
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
CLAUDE_MD = ROOT / "CLAUDE.md"
CATALOG = ROOT / "jn_frontend_calistrato-react/presentation/pages/nosso-backend/conceptsCatalog.ts"

SECTIONS = {
    "Data entities": "Entidades",
    "Reading and writing data": "Leitura e escrita de dados",
    "Code shape": "Forma do código",
}
COST_CENTERS_SECTION = "Centros de custo"

RULE = re.compile(r"^- \*\*(.+?)\*\* — (.*)$")
RULE_NAME = re.compile(r"^(.+) \((\w+)\)$")
DEPENDENCY_ORDER = re.compile(r"strict dependency order: \*\*(.+?)\*\*")
CONCEPT = re.compile(r"title: '([^']+)'|acronym: '([^']+)',\s*name: '([^']+)',\s*explanation: '((?:[^'\\]|\\.)*)'")


def show(*values):
    print(*values, sep="\t")


def read_rules(text):
    """Devolve a lista (secao, sigla, acronimo, regra) das linhas da secao Architectural Rules."""
    rules = []
    section = ""
    for line in text.split("## Architectural Rules", 1)[1].splitlines():
        if line.startswith("### "):
            section = line[4:].strip()
            continue
        rule = RULE.match(line)
        if not rule:
            continue
        name = RULE_NAME.match(rule.group(1))
        if not name:
            show("SEM_SIGLA", rule.group(1))
            continue
        rules.append((section, name.group(2), name.group(1), rule.group(2)))
    return rules


def read_catalog(text):
    """Devolve {secao: {sigla: (acronimo, explicacao)}}."""
    sections = collections.OrderedDict()
    section = ""
    for match in CONCEPT.finditer(text):
        if match.group(1):
            section = match.group(1)
            sections[section] = {}
            continue
        sections[section][match.group(2)] = (match.group(3), match.group(4).replace("\\'", "'"))
    return sections


def compare_rules(rules, catalog):
    screen = {acronym: (section, *concept) for section, concepts in catalog.items() if section != COST_CENTERS_SECTION for acronym, concept in concepts.items()}
    for acronym, count in collections.Counter(rule[1] for rule in rules).items():
        if count > 1:
            show("SIGLA_REPETIDA", acronym)
    for section, acronym, name, text in rules:
        translated = SECTIONS.get(section)
        if not translated:
            show("SECAO_NOVA", section)
            translated = section
        if acronym not in screen:
            show("ADICIONAR", translated, acronym, name, text)
            continue
        screen_section, screen_name, explanation = screen[acronym]
        if screen_section != translated:
            show("MOVER", acronym, screen_section, translated)
        if screen_name != name:
            show("ACRONIMO", acronym, screen_name, name)
        show("DESCRICAO", acronym, explanation, text)
    known = {rule[1] for rule in rules}
    for acronym, concept in sorted(screen.items()):
        if acronym not in known:
            show("RETIRAR", concept[0], acronym)
    return len(screen)


def compare_cost_centers(text, catalog):
    screen = {acronym.lower() for acronym in catalog.get(COST_CENTERS_SECTION, {})}
    order = DEPENDENCY_ORDER.search(text)
    centers = set(re.findall(r"[a-z]+", order.group(1))) if order else set()
    for center in sorted(centers - screen):
        show("CENTRO_ADICIONAR", center.upper())
    for center in sorted(screen - centers):
        show("CENTRO_RETIRAR", center.upper())
    return len(centers), len(screen)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    text = CLAUDE_MD.read_text(encoding="utf-8")
    catalog = read_catalog(CATALOG.read_text(encoding="utf-8"))
    rules = read_rules(text)
    rules_on_screen = compare_rules(rules, catalog)
    centers, centers_on_screen = compare_cost_centers(text, catalog)
    show("TOTAL", len(rules), rules_on_screen, centers, centers_on_screen)
    return 0


if __name__ == "__main__":
    sys.exit(main())
