const fs = require('fs'), path = require('path');
const ROOT = 'C:/eclipse-workspaces/ccp';
function walk(d, o) { let e; try { e = fs.readdirSync(d, { withFileTypes: true }); } catch (x) { return o; }
  for (const t of e) { const p = path.join(d, t.name);
    if (t.isDirectory()) { if (['node_modules','target','.git'].includes(t.name)) continue; walk(p, o); }
    else if (t.name.endsWith('.java')) o.push(p.replace(/\\/g, '/')); } return o; }
const mods = fs.readdirSync(ROOT, { withFileTypes: true })
  .filter(d => d.isDirectory() && d.name !== 'ccp_rest-api-tests_jobsnow' && /^(jb_|jn_|vis_)/.test(d.name)).map(d => d.name);
let files = []; for (const m of mods) walk(path.join(ROOT, m, 'src', 'main', 'java'), files);
const map = {};
for (const f of files) {
  const s = fs.readFileSync(f, 'utf8');
  const re = /@CcpJsonCopyFieldValidationsFrom\((\w+)\.class\)((?:\s*@[\w.]+(?:\([^)]*\))?)*)\s*([a-zA-Z_$][\w$]*)/g;
  let m;
  while ((m = re.exec(s)) !== null) { (map[m[3]] = map[m[3]] || new Set()).add(m[1]); }
}
for (const k of Object.keys(map).sort()) console.log(k, '->', [...map[k]].join(' | '));
