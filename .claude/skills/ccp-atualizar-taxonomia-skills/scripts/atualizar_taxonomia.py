import json
import re
from collections import defaultdict

folder = "C:/eclipse-workspaces/ccp/ccp_rest-api-tests_jobsnow/documentation/jn/database/elasticsearch/"

# 1. Parse ajustes_synonyms.txt
with open(folder + "ajustes_synonyms.txt", "r", encoding="utf-8") as f:
    lines = f.readlines()

parent_map = {}
children_count = defaultdict(int)

for line in lines:
    line = line.strip()
    if not line.startswith("adicionarParent="):
        continue
    content = line[len("adicionarParent="):]
    parts = [p.strip().upper() for p in content.split(",") if p.strip()]
    if not parts:
        continue
    skill = parts[0]
    parents = parts[1:] if len(parts) > 1 else []
    parent_map[skill] = parents
    for p in parents:
        children_count[p] += 1

all_skills = set(parent_map.keys())
for parents in parent_map.values():
    all_skills.update(parents)
for skill in all_skills:
    if skill not in parent_map:
        parent_map[skill] = []

# 2. Ancestor computation
def get_all_ancestors(skill, visiting=None):
    if visiting is None:
        visiting = set()
    if skill in visiting:
        return []
    visiting = visiting | {skill}
    result = []
    for p in parent_map.get(skill, []):
        result.append(p)
        result.extend(get_all_ancestors(p, visiting))
    return result

def get_unique_ancestors(skill):
    seen = set()
    result = []
    for a in get_all_ancestors(skill):
        if a not in seen:
            seen.add(a)
            result.append(a)
    return result

def has_repeated_parent(skill):
    anc = get_all_ancestors(skill)
    return len(set(anc)) != len(anc)

# 3. Load synonyms
with open(folder + "synonyms3.txt", "r", encoding="utf-8") as f:
    synonyms3_lines = f.readlines()

def find_synonyms(skill):
    for line in synonyms3_lines:
        parts = [p.strip().upper() for p in line.split(",")
                 if p.strip() and 1 < len(p.strip()) < 50]
        if skill.upper() in parts:
            return [{"skill": s} for s in parts if s != skill.upper()]
    return []

# 4. Load existing JSON
with open(folder + "report_skills_modified.json", "r", encoding="utf-8") as f:
    existing_report = json.load(f)
existing_by_skill = {e["skill"]: e for e in existing_report}

# 5. Build all entries
def build_entry(skill):
    direct_parents = parent_map.get(skill, [])
    unique_ancestors = get_unique_ancestors(skill)
    repeated = has_repeated_parent(skill)
    c_count = children_count.get(skill, 0)
    has_no_parent = len(direct_parents) == 0

    mirror = ""
    if len(direct_parents) == 1:
        p = direct_parents[0]
        if children_count.get(p, 0) == 1:
            mirror = p

    skills_with_common = sorted([
        other for other in all_skills
        if other != skill and len(set(direct_parents) & set(parent_map.get(other, []))) > 1
    ])

    existing = existing_by_skill.get(skill, {})
    return {
        "childrenCount": c_count,
        "directParent": direct_parents,
        "hasMirror": mirror != "",
        "hasNoParent": has_no_parent,
        "hasRepeatedParent": repeated,
        "hasSkillsWithCommonParentsSize": len(skills_with_common) > 0,
        "mirror": mirror,
        "parent": unique_ancestors,
        "skill": skill,
        "skillsWithCommonParents": skills_with_common,
        "synonym": existing.get("synonym", find_synonyms(skill)),
        "description": existing.get("description", "")
    }

new_report = sorted([build_entry(s) for s in all_skills], key=lambda x: x["skill"])

# 6. Update skills_synonyms_missing_descricoes.md
md_path = "C:/eclipse-workspaces/ccp/skills_synonyms_missing_descricoes.md"
with open(md_path, "r", encoding="utf-8") as f:
    md_content = f.read()

described_skills = set()
for match in re.finditer(r"^\|\s*([A-Z0-9][A-Z0-9 .\-/#@_&'+]*?)\s*\|", md_content, re.MULTILINE):
    name = match.group(1).strip()
    if name.lower() not in ('skill', '-', '---') and not set(name) <= set('-') and len(name) >= 2:
        described_skills.add(name)

report_by_skill = {e["skill"]: e for e in new_report}
missing_from_md = sorted(all_skills - described_skills)
skills_to_add = [(s, report_by_skill[s].get("description", "")) for s in missing_from_md if s in report_by_skill]

if skills_to_add:
    new_section = "\n---\n\n## Categorias e Skills Adicionais\n\n| Skill | Descrição |\n|-------|-----------|\n"
    for s, desc in skills_to_add:
        new_section += f"| {s} | {desc} |\n"
    with open(md_path, "a", encoding="utf-8") as f:
        f.write(new_section)

# 7. Save JSON
with open(folder + "report_skills_modified.json", "w", encoding="utf-8") as f:
    json.dump(new_report, f, ensure_ascii=False, indent=2)

# 8. Report
incestos = [e for e in new_report if e["hasRepeatedParent"]]
added = sorted(all_skills - set(existing_by_skill))
removed = sorted(set(existing_by_skill) - all_skills)
no_desc = [e["skill"] for e in new_report if not e.get("description")]

print(f"Total: {len(new_report)} | Incestos: {len(incestos)} | Adicionadas: {added} | Removidas: {removed}")
print(f"Sem description: {no_desc if no_desc else 'nenhuma'}")
print(f"Adicionadas ao MD: {[s for s, _ in skills_to_add] if skills_to_add else 'nenhuma'}")
print()
print("=== INCESTOS ===")
print(f"{'Skill':<40} {'Pais diretos (ancestrais do pai)':<80} {'Repetidos'}")
print("-" * 160)
for e in sorted(incestos, key=lambda x: x["skill"]):
    skill = e["skill"]

    all_anc = get_all_ancestors(skill)
    seen_anc = set()
    repeated = set()
    for a in all_anc:
        if a in seen_anc:
            repeated.add(a)
        seen_anc.add(a)

    parts = []
    for dp in e["directParent"]:
        dp_ancestors = report_by_skill.get(dp, {}).get("parent", [])
        if dp_ancestors:
            anc_str = ", ".join(f'"{a}"' for a in dp_ancestors)
            parts.append(f'{dp}({anc_str})')
        else:
            parts.append(dp)
    parents_col = ", ".join(parts)

    repeated_col = ", ".join(sorted(repeated))
    print(f"{skill:<40} {parents_col:<80} {repeated_col}")
