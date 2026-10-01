#!/usr/bin/env bash
# Lista os repositórios do workspace (raiz + cada módulo) com algo a enviar:
# alterações não commitadas, arquivos novos e commits à frente do remoto.
# Uso: pendentes.sh [--sem-fetch]
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
FETCH=1; [ "$1" = "--sem-fetch" ] && FETCH=0

repos=("$ROOT")
for d in "$ROOT"/*/; do [ -d "$d/.git" ] && repos+=("${d%/}"); done

pend=0; limpos=0
printf '%3s %-62s %6s %6s %6s %6s  %s\n' '#' REPO MODIF NOVOS AHEAD BEHIND BRANCH
for r in "${repos[@]}"; do
  name="$(basename "$r")"; [ "$r" = "$ROOT" ] && name="(raiz) $name"
  [ $FETCH = 1 ] && git -C "$r" fetch --quiet 2>/dev/null
  branch="$(git -C "$r" rev-parse --abbrev-ref HEAD 2>/dev/null)"
  st="$(git -C "$r" status --porcelain 2>/dev/null)"
  if [ -z "$st" ]; then modif=0; novos=0
  else
    modif=$(printf '%s\n' "$st" | grep -vc '^??')
    novos=$(printf '%s\n' "$st" | grep -c '^??')
  fi
  if git -C "$r" rev-parse --abbrev-ref '@{u}' >/dev/null 2>&1; then
    read behind ahead < <(git -C "$r" rev-list --left-right --count '@{u}...HEAD')
  else ahead="sem-upstream"; behind="-"; fi
  if [ "$modif" != 0 ] || [ "$novos" != 0 ] || [ "$ahead" != 0 ]; then
    pend=$((pend+1))
    printf '%3s %-62s %6s %6s %6s %6s  %s\n' "$pend" "$name" "$modif" "$novos" "$ahead" "$behind" "$branch"
  else limpos=$((limpos+1)); fi
done
echo "PENDENTES: $pend  LIMPOS: $limpos  TOTAL: ${#repos[@]}"
