#!/usr/bin/env bash
# Lista os repositórios do workspace (raiz + cada módulo) com push pendente: commits locais que o remoto ainda não tem.
# Compara HEAD com a referência remota local da branch (@{u}), atualizada pelo último push/pull/fetch: não faz git
# fetch, então é rápido e responde "o que eu ainda não enviei". Ao lado, os arquivos ainda sem commit do repositório.
# Uso: pendentes.sh
# Saída (TAB): repo <nome> <commits a enviar> <arquivos sem commit> <branch>
#              semUpstream <nome> <branch>          (branch sem remoto configurado: tudo nela é push pendente)
#              resumo <com push pendente> <sem upstream> <total>
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"

repos=("$ROOT")
for d in "$ROOT"/*/; do [ -d "$d/.git" ] && repos+=("${d%/}"); done

pending=0; noUpstream=0
for r in "${repos[@]}"; do
  name="$(basename "$r")"; [ "$r" = "$ROOT" ] && name="(raiz) $name"
  branch="$(git -C "$r" rev-parse --abbrev-ref HEAD 2>/dev/null)"
  if ! git -C "$r" rev-parse --abbrev-ref '@{u}' >/dev/null 2>&1; then
    noUpstream=$((noUpstream+1))
    printf 'semUpstream\t%s\t%s\n' "$name" "$branch"
    continue
  fi
  ahead="$(git -C "$r" rev-list --count '@{u}..HEAD' 2>/dev/null)"
  [ "${ahead:-0}" -eq 0 ] && continue
  pending=$((pending+1))
  uncommitted="$(git -C "$r" status --porcelain 2>/dev/null | grep -c .)"
  printf 'repo\t%s\t%s\t%s\t%s\n' "$name" "$ahead" "$uncommitted" "$branch"
done
printf 'resumo\t%s\t%s\t%s\n' "$pending" "$noUpstream" "${#repos[@]}"
