#!/bin/bash
# Conta, por centro de custo (pacote de 2º nível: com.ccp, com.jn, com.jb, com.vis), as classes e os métodos públicos do
# código de produção e os testes JUnit (@Test) que exercitam cada pacote, sem compilar nem rodar nada.
# Saída: linhas "chave<TAB>valores" para a skill montar a tabela.
cd /c/eclipse-workspaces/ccp || exit 1

TESTES=ccp_rest-api-tests_jobsnow

# declaração de tipo (classe, interface, enum, anotação ou record) no início da linha: um arquivo com ela conta como uma classe
TIPO='^\s*((public|protected|private|abstract|final|static|sealed|non-sealed|strictfp)\s+)*(class|interface|enum|@interface|record)\s+\w'
# declaração de método público (mesma regra da antiga contagem de métodos públicos)
METODO='^\s+(?:(?:@\w[\w.]*(?:\s*\([^)]*\))?\s+)|(?:(?:static|final|abstract|synchronized|native|default|strictfp)\s+))*public\s+(?:(?:static|final|abstract|synchronized|native|default|strictfp)\s+)*(?!class\b|interface\b|enum\b|@interface\b)\S'

declare -A classes metodos testes

# pacote de 2º nível de cada linha "caminho:..." do grep (o que vem depois de src/<main|test>/java/)
pacoteDoCaminho() { sed -E 's#^[^:]*src/(main|test)/java/([^/]+)/([^/:]+)/.*#\2.\3#'; }

# código de produção: src/main/java de cada módulo, sem os dependency chooser (só fazem o wiring da DI; o diretório
# jn_mensageria-consumer_gcp-pubsub-push-spring_dependency está truncado em _dependency), sem o módulo de testes e sem
# documentation/ (módulos aposentados guardados só como fonte). Um grep só para todos os arquivos, por desempenho
mapfile -t PRODUCAO < <(find . -path ./.metadata -prune -o -path '*/node_modules' -prune -o -path '*/documentation' -prune \
    -o -path "./$TESTES" -prune -o -path './*dependency?chooser*' -prune -o -path './*_dependency' -prune \
    -o -path '*/src/main/java/*' -name '*.java' -print 2>/dev/null)

while read -r n p; do classes[$p]=$n; done < <(grep -lE "$TIPO" "${PRODUCAO[@]}" | sed 's/$/:/' | pacoteDoCaminho | sort | uniq -c)
# linha com "nome(" e sem atribuição de campo com "(" no inicializador
while read -r n p; do metodos[$p]=$n; done < <(grep -HP "$METODO" "${PRODUCAO[@]}" | grep -E ':.*\w\s*\(' \
    | grep -vE ':.*=\s*\S.*\(' | pacoteDoCaminho | sort | uniq -c)

# testes: @Test no início da linha (sozinho, com parâmetros ou com o método na mesma linha), atribuídos ao pacote de
# 2º nível do arquivo de teste. Também conta as classes do módulo de testes, que é a linha agregadora
mapfile -t TESTE < <(find . -path ./.metadata -prune -o -path '*/node_modules' -prune -o -path '*/documentation' -prune \
    -o -path '*/src/test/java/*' -name '*.java' -print 2>/dev/null)

classesDeTeste=$(grep -lE "$TIPO" "${TESTE[@]}" | grep -c "^\./$TESTES/")
while read -r n p; do testes[$p]=$n; done < <(grep -HE '^\s*@Test\b' "${TESTE[@]}" | pacoteDoCaminho | sort | uniq -c)

declare -A testesPorModulo
while read -r n m; do testesPorModulo[$m]=$n; done < <(grep -HE '^\s*@Test\b' "${TESTE[@]}" | cut -d/ -f2 | sort | uniq -c)

ignorados=0; listaIgnorados=""
while read -r n arquivo; do
    ignorados=$((ignorados + n))
    listaIgnorados+="$(basename "$arquivo" .java) ($n)  "
done < <(grep -HE '^\s*@Ignore\b' "${TESTE[@]}" | cut -d: -f1 | sort | uniq -c)

# uma linha por pacote: pacote, classes, métodos públicos, testes (ordenadas por classes)
declare -A todos
for p in "${!classes[@]}" "${!testes[@]}"; do todos[$p]=1; done
for p in "${!todos[@]}"; do
    printf 'pacote\t%s\t%s\t%s\t%s\n' "$p" "${classes[$p]:-0}" "${metodos[$p]:-0}" "${testes[$p]:-0}"
done | sort -t$'\t' -k3 -nr
# a linha agregadora do módulo de testes: só as classes; métodos e testes ficam zerados (os testes já estão nos pacotes)
printf 'agregador\t%s\t%s\t0\t0\n' "$TESTES" "$classesDeTeste"

printf 'ignorados\t%s\n' "$ignorados"
printf 'classesComIgnore\t%s\n' "${listaIgnorados:-nenhuma}"
for m in "${!testesPorModulo[@]}"; do printf 'moduloComTestes\t%s\t%s\n' "$m" "${testesPorModulo[$m]}"; done

# front end (fora da suíte Java): casos it(...) / test(...) nos *.spec.* e *.test.*
frontTestes=0; frontArquivos=0
while IFS= read -r spec; do
    n=$(grep -cE '^\s*(it|test)(\.only|\.skip)?\s*\(' "$spec")
    frontTestes=$((frontTestes + n)); frontArquivos=$((frontArquivos + 1))
done < <(find ./jn_frontend_calistrato-react -path '*/node_modules' -prune -o -path '*/.next' -prune -o \( -name '*.spec.ts' -o -name '*.spec.tsx' -o -name '*.test.ts' -o -name '*.test.tsx' -o -name '*.spec.js' -o -name '*.test.js' \) -print 2>/dev/null)
printf 'frontend\t%s\t%s\n' "$frontTestes" "$frontArquivos"
