const fs = require('fs'), path = require('path');
const ROOT = 'C:/eclipse-workspaces/ccp';
const DEST = __dirname + '/backup';
function walk(d, o) { let e; try { e = fs.readdirSync(d, { withFileTypes: true }); } catch (x) { return o; }
  for (const t of e) { const p = path.join(d, t.name);
    if (t.isDirectory()) { if (['node_modules','target','.git'].includes(t.name)) continue; walk(p, o); }
    else if (t.name.endsWith('.java')) o.push(p.replace(/\\/g, '/')); } return o; }
const mods = fs.readdirSync(ROOT, { withFileTypes: true })
  .filter(d => d.isDirectory() && d.name !== 'ccp_rest-api-tests_jobsnow' && /^(jb_|jn_|vis_)/.test(d.name)).map(d => d.name);
let files = []; for (const m of mods) walk(path.join(ROOT, m, 'src', 'main', 'java'), files);
let n = 0;
for (const f of files) {
  const rel = f.replace(ROOT + '/', '');
  const dst = path.join(DEST, rel);
  fs.mkdirSync(path.dirname(dst), { recursive: true });
  fs.copyFileSync(f, dst);
  n++;
}
console.log('backed up', n, 'files to', DEST);
