const fs = require('fs');
const path = require('path');
const ROOT = 'C:/eclipse-workspaces/ccp';
const data = JSON.parse(fs.readFileSync('enums.json', 'utf8'));
const enums = data.enums;
const CENTRALIZERS = ['JnJsonCommonsFields', 'JnJsonInstantMessengerFields', 'VisJsonCommonsFields'];
const all = new Set();
for (const c of CENTRALIZERS) for (const k of enums[c][0].constants) all.add(k);
const MODULE_PREFIXES = (process.argv[2] || 'jb_,jn_,vis_').split(',');
function walk(dir, out) {
  let entries; try { entries = fs.readdirSync(dir, { withFileTypes: true }); } catch (e) { return out; }
  for (const e of entries) { const p = path.join(dir, e.name);
    if (e.isDirectory()) { if (['node_modules','target','.git'].includes(e.name)) continue; walk(p, out); }
    else if (e.name.endsWith('.java')) out.push(p.replace(/\\/g, '/')); }
  return out;
}
const modules = fs.readdirSync(ROOT, { withFileTypes: true })
  .filter(d => d.isDirectory() && d.name !== 'ccp_rest-api-tests_jobsnow' && MODULE_PREFIXES.some(p => d.name.startsWith(p))).map(d => d.name);
let files = []; for (const m of modules) walk(path.join(ROOT, m, 'src', 'main', 'java'), files);
function strip(src) {
  return src.replace(/\/\*[\s\S]*?\*\//g, m => m.replace(/[^\n]/g, ' '))
            .replace(/\/\/[^\n]*/g, m => m.replace(/[^\n]/g, ' '))
            .replace(/"(\\.|[^"\\])*"/g, m => '"' + ' '.repeat(Math.max(0, m.length - 2)) + '"');
}
for (const f of files) {
  const src = strip(fs.readFileSync(f, 'utf8'));
  const lines = src.split('\n');
  const hits = [];
  lines.forEach((line, i) => {
    const re = /\b([A-Z][\w$]*)\.(?:(Fields|JsonFieldNames)\.)?([a-z][\w$]*)\b/g;
    let m;
    while ((m = re.exec(line)) !== null) {
      const qual = m[1], mid = m[2], field = m[3];
      if (!all.has(field)) continue;
      if (CENTRALIZERS.includes(qual)) continue;
      if (!mid && !enums[qual]) continue;
      if (!mid && enums[qual] && !enums[qual].some(e => e.constants.includes(field))) continue;
      hits.push(`   L${i+1}: ${qual}${mid ? '.'+mid : ''}.${field}`);
    }
  });
  if (hits.length) { console.log(f.replace('C:/eclipse-workspaces/ccp/','')); hits.forEach(h=>console.log(h)); }
}
