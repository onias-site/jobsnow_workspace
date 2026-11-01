#!/usr/bin/env bash
# Compara os repositorios git reais do workspace (raiz + cada modulo) com o catalogo da tela "Nosso backend".
# O nome de cada repositorio vem do remote origin, que nem sempre e igual ao da pasta local.
# Somente leitura. Saida, uma linha por dado, separada por TAB:
#   ADICIONAR <repositorio> <pasta> <proposito no CLAUDE.md>     existe no git e falta no catalogo
#   RETIRAR <repositorio>                                        esta no catalogo e nao existe mais no git
#   SEM_PROPOSITO <pasta>                                        modulo que falta na tabela do CLAUDE.md
#   DESCRICAO <repositorio> <descricao da tela> <proposito no CLAUDE.md>   para comparar o sentido dos dois
#   TOTAL <repositorios no git> <repositorios no catalogo>
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
CATALOG="$ROOT/jn_frontend_calistrato-react/presentation/pages/nosso-backend/repositoriesCatalog.ts"
CLAUDE_MD="$ROOT/CLAUDE.md"

remoteName() { git -C "$1" remote get-url origin 2>/dev/null | sed -E 's#.*/##; s#\.git$##'; }
purposeOf() { awk -F'|' -v m="\`$1\`" '{ gsub(/^ +| +$/, "", $3); if ($3 == m) { gsub(/^ +| +$/, "", $4); print $4; exit } }' "$CLAUDE_MD"; }

declare -A folderByRepo
folderByRepo["$(remoteName "$ROOT")"]="(raiz)"
for d in "$ROOT"/*/; do
  [ -d "$d/.git" ] || continue
  folder="$(basename "$d")"
  folderByRepo["$(remoteName "$d")"]="$folder"
done

declare -A catalog
while IFS=$'\t' read -r name description; do
  catalog["$name"]="$description"
done < <(sed -nE "s/^ *\{ name: '([^']+)', description: '(.*)' \},?\r?$/\1\t\2/p" "$CATALOG")

for repo in $(printf '%s\n' "${!folderByRepo[@]}" | sort); do
  folder="${folderByRepo[$repo]}"
  purpose=""
  [ "$folder" != "(raiz)" ] && purpose="$(purposeOf "$folder")"
  if [ "$folder" != "(raiz)" ] && [ "$folder" != "jn_frontend_calistrato-react" ] && [ -z "$purpose" ]; then
    printf 'SEM_PROPOSITO\t%s\n' "$folder"
  fi
  if [ -z "${catalog[$repo]+x}" ]; then
    printf 'ADICIONAR\t%s\t%s\t%s\n' "$repo" "$folder" "$purpose"
    continue
  fi
  printf 'DESCRICAO\t%s\t%s\t%s\n' "$repo" "${catalog[$repo]}" "$purpose"
done

for repo in $(printf '%s\n' "${!catalog[@]}" | sort); do
  [ -z "${folderByRepo[$repo]+x}" ] && printf 'RETIRAR\t%s\n' "$repo"
done

printf 'TOTAL\t%s\t%s\n' "${#folderByRepo[@]}" "${#catalog[@]}"
