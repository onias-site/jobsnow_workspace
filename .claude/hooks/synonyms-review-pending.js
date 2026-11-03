// Hook SessionStart: lembra as pendências da revisão do synonyms.json (2026-11-02), lendo a tabela "Pendentes" da memória.
// Sem linhas na tabela (ou sem o arquivo), não imprime nada.
const fs = require('fs');
const os = require('os');
const path = require('path');
const memoryFile = path.join(os.homedir(), '.claude', 'projects', 'C--eclipse-workspaces-ccp', 'memory', 'project_synonyms_review_2026_11_02.md');
const reportFile = 'C:\\eclipse-workspaces\\ccp\\ccp_rest-api-tests_jobsnow\\documentation\\jn\\skills\\synonyms_revisao_2026-11-02.md';
let text;
try { text = fs.readFileSync(memoryFile, 'utf8'); } catch (e) { process.exit(0); }
const lines = text.split(/\r?\n/);
const start = lines.findIndex((line) => line.startsWith('Pendentes'));
if (start < 0) { process.exit(0); }
// linhas de dado da tabela: começam com "|", sem o cabeçalho e o separador
const rows = [];
for (let i = start + 1; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) { if (rows.length) break; continue; }
    if (!line.startsWith('|')) break;
    if (/^\|\s*#\s*\|/.test(line) || /^\|[\s-|]+\|$/.test(line)) continue;
    rows.push(line.split('|').slice(1, -1).map((cell) => cell.trim()));
}
if (!rows.length) { process.exit(0); }
// numera pela posição: apagar uma linha resolvida não deixa buraco na lista
const items = rows.map(([, pending, how], index) => `${index + 1}. ${pending} -> ${how}`);
const message = `Pendências da revisão do synonyms.json (${rows.length} itens; relatório em ${reportFile}):\n` + items.join('\n');
process.stdout.write(JSON.stringify({
    systemMessage: message,
    hookSpecificOutput: { hookEventName: 'SessionStart',
        additionalContext: message + '\nLembre o usuário dessas pendências na primeira resposta da sessão. Lista completa em project_synonyms_review_2026_11_02.md.' },
}));
