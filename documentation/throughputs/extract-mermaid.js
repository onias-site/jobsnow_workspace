const fs = require('fs');
const path = require('path');

const src = process.argv[2];
const outDir = process.argv[3];

const md = fs.readFileSync(src, 'utf8');
const lines = md.split(/\r?\n/);

fs.mkdirSync(outDir, { recursive: true });

// nomes na ordem em que os blocos aparecem no relatório
const names = [
  '01-mapa-geral-das-portas',
  '02-bloco-b1-unionall',
  '03-bloco-b5-async-writer',
  '04-bloco-b7-send-message',
  '05-execute-login',
  '06-create-login-token',
  '07-vis-resume-save',
  '08-jb-bot-message-reader',
  '09-caminho-de-erro-transversal',
];

let inBlock = false;
let buf = [];
let idx = 0;
const written = [];

for (const line of lines) {
  if (!inBlock && /^```mermaid\s*$/.test(line)) {
    inBlock = true;
    buf = [];
    continue;
  }
  if (inBlock && /^```\s*$/.test(line)) {
    inBlock = false;
    const name = names[idx] || `bloco-${String(idx + 1).padStart(2, '0')}`;
    const file = path.join(outDir, `${name}.mmd`);
    fs.writeFileSync(file, buf.join('\n') + '\n', 'utf8');
    written.push({ name, file, lines: buf.length });
    idx++;
    continue;
  }
  if (inBlock) buf.push(line);
}

console.log(`blocos extraidos: ${written.length}`);
for (const w of written) console.log(`  ${w.name}.mmd (${w.lines} linhas)`);
if (idx > names.length) console.log(`AVISO: ${idx - names.length} bloco(s) sem nome definido`);
if (idx < names.length) console.log(`AVISO: esperava ${names.length} blocos, achei ${idx}`);
