// Hook SessionStart: lembra os links do front sem destino, lendo a tabela "Visíveis" da memória.
// Sem linhas na tabela (ou sem o arquivo), não imprime nada.
const fs = require('fs');
const os = require('os');
const path = require('path');

const memoryFile = path.join(os.homedir(), '.claude', 'projects', 'C--eclipse-workspaces-ccp', 'memory', 'project_frontend_pending_links.md');

let text;
try {
    text = fs.readFileSync(memoryFile, 'utf8');
} catch (e) {
    process.exit(0);
}

const lines = text.split(/\r?\n/);
const start = lines.findIndex((line) => line.startsWith('Visíveis'));
if (start < 0) {
    process.exit(0);
}

// linhas de dado da tabela: começam com "|", sem o cabeçalho e o separador
const rows = [];
for (let i = start + 1; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) {
        if (rows.length) break;
        continue;
    }
    if (!line.startsWith('|')) break;
    if (/^\|\s*#\s*\|/.test(line) || /^\|[\s-|]+\|$/.test(line)) continue;
    rows.push(line.split('|').slice(1, -1).map((cell) => cell.trim()));
}

if (!rows.length) {
    process.exit(0);
}

const items = rows.map(([n, where, label, href]) => `${n}. ${label} (${where}) -> ${href}`);
const message = `Débitos do front end (${rows.length} links sem destino, decisão sua):\n` + items.join('\n');

process.stdout.write(JSON.stringify({
    systemMessage: message,
    hookSpecificOutput: {
        hookEventName: 'SessionStart',
        additionalContext: message + '\nLembre o usuário desses débitos na primeira resposta da sessão. Lista completa em project_frontend_pending_links.md.',
    },
}));
