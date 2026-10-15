// Compara o corpo enviado pela carga (curriculos.jsonl) com o que ficou gravado em vis_resume / vis_inactive_resume,
// aplicando as conversões documentadas (experience vira ano de início, idioma perde o id). Lista as diferenças por campo.
//
// Uso: node 06-comparar-enviado-gravado.mjs <pasta da carga>
import fs from 'fs';
import path from 'path';

const [, , dir] = process.argv;
const CURRENT_YEAR = new Date().getFullYear();

async function search(index, body) {
    const r = await fetch(`http://localhost:9200/${index}/_search`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    return (await r.json()).hits.hits;
}

const sentLines = fs.readFileSync(path.join(dir, 'curriculos.jsonl'), 'utf8').trim().split('\n').map((l) => JSON.parse(l));
const sent = new Map(sentLines.map((l) => [l.resume.linkedinAddress, l]));
// o casamento é pelo linkedin; endereço repetido em mais de um currículo (o exemplo do modelo, um perfil cortado) casaria
// currículos de pessoas diferentes, então fica fora da comparação
const timesSent = {};
sentLines.forEach((l) => (timesSent[l.resume.linkedinAddress] = (timesSent[l.resume.linkedinAddress] || 0) + 1));
const stored = [...(await search('vis_resume', { size: 5000 })), ...(await search('vis_inactive_resume', { size: 5000 }))];
const diffs = {};
const examples = {};
const note = (field, email, detail) => {
    diffs[field] = (diffs[field] || 0) + 1;
    examples[field] = examples[field] || [];
    examples[field].length < 3 && examples[field].push({ email, ...detail });
};
const sameList = (a, b) => JSON.stringify([...a].sort()) === JSON.stringify([...b].sort());
let compared = 0;
for (const hit of stored) {
    const s = hit._source;
    const entry = sent.get(s.linkedinAddress);
    if (!entry) { note('sem correspondente no envio', hit._id, { linkedin: s.linkedinAddress }); continue; }
    if (timesSent[s.linkedinAddress] > 1) { note('linkedin repetido no envio (não comparado)', hit._id, { linkedin: s.linkedinAddress }); continue; }
    compared++;
    const r = entry.resume;
    const email = entry.id;
    for (const field of ['desiredJob', 'lastJob', 'linkedinAddress', 'resumeType', 'disponibility', 'temporallyJobTime', 'pcd', 'travel', 'negotiableClaim', 'clt', 'pj', 'btc']) {
        const a = r[field];
        const b = s[field];
        const equal = a === b || (a === undefined && (b === undefined || b === 0)) || Number(a) === Number(b) && typeof a === 'number';
        if (!equal) note(field, email, { enviado: a, gravado: b });
    }
    if (!sameList(r.ddd, (s.ddd || []).map(Number))) note('ddd', email, { enviado: r.ddd.length, gravado: (s.ddd || []).length });
    if (!sameList(r.notAllowedCompany, s.notAllowedCompany || [])) note('notAllowedCompany', email, { enviado: r.notAllowedCompany, gravado: s.notAllowedCompany });
    if (Number(s.experience) !== CURRENT_YEAR - r.experience) note('experience', email, { enviado: r.experience, gravado: s.experience });
    const langs = (x) => (x || []).map((l) => `${l.name}:${Number(l.level)}`);
    if (!sameList(langs(r.spokenLanguage), langs(s.spokenLanguage))) note('spokenLanguage', email, { enviado: langs(r.spokenLanguage), gravado: langs(s.spokenLanguage) });
    if ((s.spokenLanguage || []).some((l) => l.id !== undefined)) note('spokenLanguage com id', email, {});
    const skills = (x) => (x || []).map((k) => `${k.type}|${k.category}|${k.skill}|${k.word}`);
    if (!sameList(skills(r.skill), skills(s.skill))) note('skill', email, { enviado: r.skill.length, gravado: (s.skill || []).length });
    if (!s.hash || !s.hash.length) note('hash vazio', email, {});
}
console.log(JSON.stringify({ gravados: stored.length, comparados: compared, diferencas: diffs, exemplos: examples }, null, 1));
