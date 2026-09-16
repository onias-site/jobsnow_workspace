const fs = require('fs');
const data = JSON.parse(fs.readFileSync('enums.json', 'utf8'));
const enums = data.enums;

const CENTRALIZERS = ['JnJsonCommonsFields', 'JnJsonInstantMessengerFields', 'VisJsonCommonsFields'];
const cent = {};
for (const c of CENTRALIZERS) {
  cent[c] = enums[c][0].constants;
  console.log(c, '(' + enums[c][0].constants.length + '):', enums[c][0].constants.join(', '));
}
console.log('');
const all = new Set();
for (const c of CENTRALIZERS) for (const k of cent[c]) all.add(k);

// report enums with homonyms
const rows = [];
for (const [name, list] of Object.entries(enums)) {
  if (CENTRALIZERS.includes(name)) continue;
  for (const e of list) {
    const hom = e.constants.filter(k => all.has(k));
    if (hom.length) rows.push({ name, file: e.file.replace('C:/eclipse-workspaces/ccp/', ''), total: e.constants.length, hom });
  }
}
rows.sort((a, b) => b.hom.length - a.hom.length);
console.log('ENUMS WITH HOMONYMS:', rows.length);
for (const r of rows) console.log(`${r.hom.length}/${r.total}  ${r.name}  [${r.hom.join(',')}]  ${r.file}`);
