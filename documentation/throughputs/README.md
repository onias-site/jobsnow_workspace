# Diagramas do relatório de portas de saída

Os `.svg` desta pasta são renderizações dos blocos Mermaid de `relatorio_throughputs.md` (raiz do
workspace). **A fonte da verdade é o markdown** — estes arquivos são derivados e precisam ser
regerados sempre que o relatório mudar.

| Arquivo | Seção do relatório |
|---|---|
| `01-mapa-geral-das-portas.svg` | §1 — as caixinhas de sistemas |
| `02-bloco-b1-unionall.svg` | §3 — catálogo, B1 |
| `03-bloco-b5-async-writer.svg` | §3 — catálogo, B5 |
| `04-bloco-b7-send-message.svg` | §3 — catálogo, B7 |
| `05-execute-login.svg` | §4.1 |
| `06-create-login-token.svg` | §4.2 |
| `07-vis-resume-save.svg` | §4.3 |
| `08-jb-bot-message-reader.svg` | §4.4 |
| `09-caminho-de-erro-transversal.svg` | §5 |

## Quando NÃO precisa gerar imagem

O GitHub renderiza Mermaid nativamente em markdown. Com o relatório no
`onias-site/jobsnow_workspace`, os diagramas já aparecem desenhados no navegador. O VS Code (com
extensão de preview) e o Obsidian também. As imagens servem para o preview do Eclipse, que não
renderiza Mermaid, e para colar em apresentação ou PDF.

## Como regerar

Precisa de Node. O `mermaid-cli` baixa um Chromium (~150 MB) na primeira vez.

```bash
# 1. instalar o renderizador num diretório temporário qualquer
npm install @mermaid-js/mermaid-cli

# 2. extrair os blocos do markdown para .mmd
#    (a lista de nomes está no próprio script — atualize se acrescentar diagramas)
node documentation/throughputs/extract-mermaid.js relatorio_throughputs.md /tmp/mmd

# 3. renderizar cada um
for f in /tmp/mmd/*.mmd; do
  npx mmdc -i "$f" \
    -o "documentation/throughputs/$(basename "${f%.mmd}").svg" \
    -c documentation/throughputs/mermaid-config.json \
    -b white
done
```

Para PNG em vez de SVG, troque a extensão do `-o` e acrescente `-w 1400`. Prefira SVG: escala sem
perder qualidade e o texto continua selecionável e pesquisável.

**Armadilha:** se o Chromium ainda estiver baixando, o `mmdc` falha com `Could not find Chrome` ou
`spawn EBUSY`. Espere o `npm install` terminar de verdade antes de renderizar.

## Conferir se saiu certo

`mmdc` grava um SVG com um ícone de erro em vez de falhar quando o diagrama tem erro de sintaxe.
Para detectar:

```bash
grep -l "Syntax error in text" documentation/throughputs/*.svg
```

Não procure por `error-icon` — essa classe CSS está embutida em **todo** SVG do Mermaid e dá falso
positivo em todos os arquivos.
