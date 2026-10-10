#!/bin/bash
# Conta os testes JUnit (@Test) de todo o workspace, sem compilar nem rodar nada.
# Saída: linhas "chave<TAB>valor" para a skill montar as tabelas.
cd /c/eclipse-workspaces/ccp || exit 1

# todos os .java de teste de todos os módulos (cada módulo é um diretório da raiz). Fica de fora o que está em
# documentation/: são módulos aposentados guardados como fonte (ex.: text-extractor_apache-tika), que não compilam nem rodam
mapfile -t ARQUIVOS < <(find . -path ./.metadata -prune -o -path '*/node_modules' -prune -o -path '*/documentation' -prune -o -path '*/src/test/java/*' -name '*.java' -print 2>/dev/null)

total=0; classes=0; ignorados=0
declare -A porModulo porPacote classesPorPacote
listaIgnorados=""

for arquivo in "${ARQUIVOS[@]}"; do
    # @Test no início da linha: sozinho, com parâmetros (@Test(timeout = ...)) ou com o método na mesma linha
    # (@Test public void x() {...}); \b descarta @TestXxx, e o início de linha descarta menções em comentários
    n=$(grep -cE '^\s*@Test\b' "$arquivo")
    [ "$n" -eq 0 ] && continue
    total=$((total + n)); classes=$((classes + 1))

    modulo=${arquivo#./}; modulo=${modulo%%/*}
    porModulo[$modulo]=$(( ${porModulo[$modulo]:-0} + n ))

    caminho=${arquivo#*src/test/java/}
    pacote=$(echo "$caminho" | cut -d/ -f1-2 | tr / .)
    porPacote[$pacote]=$(( ${porPacote[$pacote]:-0} + n ))
    classesPorPacote[$pacote]=$(( ${classesPorPacote[$pacote]:-0} + 1 ))

    i=$(grep -cE '^\s*@Ignore\b' "$arquivo")
    if [ "$i" -gt 0 ]; then
        ignorados=$((ignorados + i))
        listaIgnorados+="$(basename "$arquivo" .java) ($i)  "
    fi
done

printf 'total\t%s\n' "$total"
printf 'classes\t%s\n' "$classes"
printf 'ignorados\t%s\n' "$ignorados"
printf 'classesComIgnore\t%s\n' "${listaIgnorados:-nenhuma}"
for p in "${!porPacote[@]}"; do printf 'pacote\t%s\t%s\t%s\n' "$p" "${porPacote[$p]}" "${classesPorPacote[$p]}"; done | sort -t$'\t' -k3 -nr
for m in "${!porModulo[@]}"; do printf 'modulo\t%s\t%s\n' "$m" "${porModulo[$m]}"; done | sort -t$'\t' -k3 -nr

# front end (fora da suíte Java): casos it(...) / test(...) nos *.spec.* e *.test.*
frontTestes=0; frontArquivos=0
while IFS= read -r spec; do
    n=$(grep -cE '^\s*(it|test)(\.only|\.skip)?\s*\(' "$spec")
    frontTestes=$((frontTestes + n)); frontArquivos=$((frontArquivos + 1))
done < <(find ./jn_frontend_calistrato-react -path '*/node_modules' -prune -o -path '*/.next' -prune -o \( -name '*.spec.ts' -o -name '*.spec.tsx' -o -name '*.test.ts' -o -name '*.test.tsx' -o -name '*.spec.js' -o -name '*.test.js' \) -print 2>/dev/null)
printf 'frontend\t%s\t%s\n' "$frontTestes" "$frontArquivos"
