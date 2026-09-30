const fs = require('fs');
const path = require('path');
const ROOT = 'C:/eclipse-workspaces/ccp';
const APPLY = process.argv.includes('--apply');
const data = JSON.parse(fs.readFileSync('enums.json', 'utf8'));
const enums = data.enums;

const JC = new Set(enums['JnJsonCommonsFields'][0].constants);
const IM = new Set(enums['JnJsonInstantMessengerFields'][0].constants);
const VC = new Set(enums['VisJsonCommonsFields'][0].constants);
const CENTRALIZERS = { JnJsonCommonsFields: 'com.jn.json.fields.validation.JnJsonCommonsFields',
                       JnJsonInstantMessengerFields: 'com.jn.json.fields.validation.JnJsonInstantMessengerFields',
                       VisJsonCommonsFields: 'com.vis.json.fields.validation.VisJsonCommonsFields' };
// fields whose messenger meaning wins over the commons one
const MESSENGER_FIELDS = new Set(['stepName','commandName','botName','chatId','botToken','instantMessageType','caption','fileName','contentType','message','moreParameters','templateId']);
// qualifiers that are not field-name enums (behavioural enums / DI providers)
const BLACKLIST_QUALIFIERS = new Set(['CcpLocalInstances','JbDefaultBotCommandStep','JnJsonTransformersFieldsEntityDefault','JnJsonTransformersFieldsEntityDoNothing','LoginTokenTicketsJsonTransformers']);

function pickTarget(field, file) {
  const isVis = /\/vis_/.test(file);
  const canVis = isVis; // only vis modules may reference VisJsonCommonsFields
  if (canVis && VC.has(field)) return 'VisJsonCommonsFields';
  if (MESSENGER_FIELDS.has(field) && IM.has(field)) return 'JnJsonInstantMessengerFields';
  if (JC.has(field)) return 'JnJsonCommonsFields';
  return null;
}

function walk(dir, out) {
  let entries; try { entries = fs.readdirSync(dir, { withFileTypes: true }); } catch (e) { return out; }
  for (const e of entries) { const p = path.join(dir, e.name);
    if (e.isDirectory()) { if (['node_modules','target','.git'].includes(e.name)) continue; walk(p, out); }
    else if (e.name.endsWith('.java')) out.push(p.replace(/\\/g, '/')); }
  return out;
}
const modules = fs.readdirSync(ROOT, { withFileTypes: true })
  .filter(d => d.isDirectory() && d.name !== 'ccp_rest-api-tests_jobsnow' && /^(jb_|jn_|vis_)/.test(d.name)).map(d => d.name);
let files = []; for (const m of modules) walk(path.join(ROOT, m, 'src', 'main', 'java'), files);

// mask[i] = true when position i is inside a comment or string literal
function buildMask(src) {
  const mask = new Array(src.length).fill(false);
  let i = 0;
  while (i < src.length) {
    const c = src[i], n = src[i + 1];
    if (c === '/' && n === '*') { let j = src.indexOf('*/', i + 2); if (j < 0) j = src.length; for (let k = i; k < Math.min(j + 2, src.length); k++) mask[k] = true; i = j + 2; continue; }
    if (c === '/' && n === '/') { let j = src.indexOf('\n', i); if (j < 0) j = src.length; for (let k = i; k < j; k++) mask[k] = true; i = j; continue; }
    if (c === '"' || c === "'") {
      let j = i + 1;
      while (j < src.length) { if (src[j] === '\\') { j += 2; continue; } if (src[j] === c) break; if (src[j] === '\n') break; j++; }
      for (let k = i; k <= Math.min(j, src.length - 1); k++) mask[k] = true; i = j + 1; continue;
    }
    i++;
  }
  return mask;
}

const report = [];
for (const f of files) {
  let src = fs.readFileSync(f, 'utf8');
  const mask = buildMask(src);
  const re = /\b((?:[A-Z][\w$]*\.)+)([a-z][\w$]*)\b/g;
  const edits = [];
  let m;
  while ((m = re.exec(src)) !== null) {
    if (mask[m.index]) continue;
    const chain = m[1].split('.').filter(Boolean);
    const field = m[2];
    const lastSeg = chain[chain.length - 1];
    if (CENTRALIZERS[lastSeg]) continue;
    if (chain.some(s => BLACKLIST_QUALIFIERS.has(s))) continue;
    const decl = enums[lastSeg];
    if (!decl || !decl.some(e => e.constants.includes(field))) continue;
    const target = pickTarget(field, f);
    if (!target) { report.push(`SKIP  ${f.replace(ROOT + '/','')}  ${m[0]} (no reachable centralizer)`); continue; }
    edits.push({ start: m.index, end: m.index + m[0].length, from: m[0], to: `${target}.${field}`, target });
  }
  if (!edits.length) continue;
  const needed = new Set(edits.map(e => e.target));
  for (let i = edits.length - 1; i >= 0; i--) src = src.slice(0, edits[i].start) + edits[i].to + src.slice(edits[i].end);
  // add imports
  const pkg = (/^\s*package\s+([\w.]+);/m.exec(src) || [])[1] || '';
  const toAdd = [];
  for (const t of needed) {
    const fqn = CENTRALIZERS[t];
    if (new RegExp(`^\\s*import\\s+${fqn.replace(/\./g,'\\.')}\\s*;`, 'm').test(src)) continue;
    if (fqn.substring(0, fqn.lastIndexOf('.')) === pkg) continue;
    toAdd.push(`import ${fqn};`);
  }
  if (toAdd.length) {
    const lastImport = [...src.matchAll(/^import [^\n]*;\s*$/gm)].pop();
    if (lastImport) src = src.slice(0, lastImport.index + lastImport[0].length) + '\n' + toAdd.join('\n') + src.slice(lastImport.index + lastImport[0].length);
    else { const pm = /^\s*package\s+[\w.]+;\s*$/m.exec(src); src = src.slice(0, pm.index + pm[0].length) + '\n\n' + toAdd.join('\n') + src.slice(pm.index + pm[0].length); }
  }
  // drop now-unused single-type imports
  const importLines = [...src.matchAll(/^import (?:static )?([\w.]+);\s*\n/gm)];
  const removals = [];
  for (const im of importLines) {
    const fqn = im[1];
    if (fqn.endsWith('.*')) continue;
    const simple = fqn.substring(fqn.lastIndexOf('.') + 1);
    const body = src.slice(0, im.index) + src.slice(im.index + im[0].length);
    const bodyNoImports = body.replace(/^import [^\n]*;\s*\n/gm, '');
    if (!new RegExp(`\\b${simple}\\b`).test(bodyNoImports)) removals.push(im);
  }
  for (let i = removals.length - 1; i >= 0; i--) {
    src = src.slice(0, removals[i].index) + src.slice(removals[i].index + removals[i][0].length);
    report.push(`  - removed unused import ${removals[i][1]} from ${f.replace(ROOT + '/','')}`);
  }
  report.push(`${edits.length.toString().padStart(3)} edits  ${f.replace(ROOT + '/','')}`);
  if (APPLY) fs.writeFileSync(f, src);
}
console.log(report.join('\n'));
console.log(APPLY ? 'APPLIED' : 'DRY RUN');
