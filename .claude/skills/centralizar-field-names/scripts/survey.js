const fs = require('fs');
const path = require('path');

const ROOT = 'C:/eclipse-workspaces/ccp';
const EXCLUDE_MODULE = 'ccp_rest-api-tests_jobsnow';

function walk(dir, out) {
  let entries;
  try { entries = fs.readdirSync(dir, { withFileTypes: true }); } catch (e) { return out; }
  for (const e of entries) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) {
      if (e.name === 'node_modules' || e.name === 'target' || e.name === '.git') continue;
      walk(p, out);
    } else if (e.name.endsWith('.java')) {
      out.push(p.replace(/\\/g, '/'));
    }
  }
  return out;
}

const modules = fs.readdirSync(ROOT, { withFileTypes: true })
  .filter(d => d.isDirectory() && d.name !== EXCLUDE_MODULE && d.name !== 'documentation')
  .map(d => d.name);

let files = [];
for (const m of modules) {
  walk(path.join(ROOT, m, 'src', 'main', 'java'), files);
}

// strip comments and strings for analysis
function stripped(src) {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, m => m.replace(/[^\n]/g, ' '))
    .replace(/\/\/[^\n]*/g, m => m.replace(/[^\n]/g, ' '))
    .replace(/"(\\.|[^"\\])*"/g, m => '"' + ' '.repeat(Math.max(0, m.length - 2)) + '"');
}

// Extract enum bodies: name -> {file, constants:[], isFieldName:bool, hasAnnotations:bool}
const enums = {};
for (const f of files) {
  const raw = fs.readFileSync(f, 'utf8');
  const src = stripped(raw);
  const re = /\benum\s+([A-Za-z_$][\w$]*)\s*(implements\s+[^{]*)?\{/g;
  let m;
  while ((m = re.exec(src)) !== null) {
    const name = m[1];
    const impl = (m[2] || '').trim();
    // find matching brace
    let depth = 1, i = m.index + m[0].length;
    while (i < src.length && depth > 0) {
      const c = src[i];
      if (c === '{') depth++;
      else if (c === '}') depth--;
      i++;
    }
    const body = src.slice(m.index + m[0].length, i - 1);
    const rawBody = raw.slice(m.index + m[0].length, i - 1);
    // constants: up to first ';' at depth 0 (ignoring parens/braces)
    let d = 0, j = 0;
    for (; j < body.length; j++) {
      const c = body[j];
      if (c === '(' || c === '{' || c === '[') d++;
      else if (c === ')' || c === '}' || c === ']') d--;
      else if (c === ';' && d === 0) break;
    }
    const constSection = body.slice(0, j);
    const consts = [];
    let dd = 0, cur = '';
    const parts = [];
    for (const c of constSection) {
      if (c === '(' || c === '{' || c === '[') { dd++; cur += c; }
      else if (c === ')' || c === '}' || c === ']') { dd--; cur += c; }
      else if (c === ',' && dd === 0) { parts.push(cur); cur = ''; }
      else cur += c;
    }
    parts.push(cur);
    for (const p of parts) {
      // remove annotations
      const noAnn = p.replace(/@[\w.]+(\s*\([\s\S]*?\))?/g, ' ').trim();
      const mm = /^([A-Za-z_$][\w$]*)/.exec(noAnn);
      if (mm) consts.push(mm[1]);
    }
    const key = name;
    if (!enums[key]) enums[key] = [];
    enums[key].push({
      file: f,
      implementsFieldName: /CcpJsonFieldName/.test(impl),
      hasAnnotations: /@Ccp/.test(rawBody.slice(0, rawBody.indexOf(';') === -1 ? rawBody.length : undefined)) && /@Ccp\w*(Json|Entity)/.test(constSection === '' ? '' : rawBody),
      constants: consts,
    });
  }
}

fs.writeFileSync(process.argv[2] || 'enums.json', JSON.stringify({ fileCount: files.length, enums }, null, 1));
console.log('files', files.length, 'enums', Object.keys(enums).length);
