#!/usr/bin/env bash
# Lista os repositórios do workspace (raiz + cada módulo) com alterações não commitadas:
# arquivos modificados, novos e removidos. Só lê o disco: não faz git fetch nem compara com o remoto.
# Uso: pendentes.sh
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"

repos=("$ROOT")
for d in "$ROOT"/*/; do [ -d "$d/.git" ] && repos+=("${d%/}"); done

pend=0; limpos=0
printf '%3s %-62s %6s %6s %6s  %s\n' '#' REPO MODIF NOVOS REMOV BRANCH
for r in "${repos[@]}"; do
  name="$(basename "$r")"; [ "$r" = "$ROOT" ] && name="(raiz) $name"
  st="$(git -C "$r" status --porcelain 2>/dev/null)"
  if [ -z "$st" ]; then limpos=$((limpos+1)); continue; fi
  # status XY do porcelain: '??' = não rastreado; 'D' em X (stage) ou Y (árvore) = removido; o resto = modificado
  novos=$(printf '%s\n' "$st" | grep -c '^??')
  remov=$(printf '%s\n' "$st" | grep -v '^??' | grep -cE '^(D.|.D)')
  modif=$(printf '%s\n' "$st" | grep -v '^??' | grep -vcE '^(D.|.D)')
  branch="$(git -C "$r" rev-parse --abbrev-ref HEAD 2>/dev/null)"
  pend=$((pend+1))
  printf '%3s %-62s %6s %6s %6s  %s\n' "$pend" "$name" "$modif" "$novos" "$remov" "$branch"
done
echo "PENDENTES: $pend  LIMPOS: $limpos  TOTAL: ${#repos[@]}"
