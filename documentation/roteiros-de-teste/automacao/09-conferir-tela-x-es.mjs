// Confere a automação pela tela (roteiro 04): para cada candidato da amostra, junta o resultado do salvamento e da
// recarga (resultados-tela.jsonl) e compara o currículo da amostra com o que ficou gravado no Elasticsearch
// (vis_resume ou vis_inactive_resume, achado pelo LinkedIn). Os excluídos de propósito precisam ter sumido.
//
// Uso: node 09-conferir-tela-x-es.mjs <pasta com amostra.json e resultados-tela.jsonl>
import fs from 'fs';
import path from 'path';

const dir = process.argv[2];
const sample = JSON.parse(fs.readFileSync(path.join(dir, 'amostra.json'), 'utf8'));
const results = fs.readFileSync(path.join(dir, 'resultados-tela.jsonl'), 'utf8').trim().split('\n').map((line) => JSON.parse(line));

async function stored(linkedinAddress) {
    const response = await fetch('http://localhost:9200/vis_resume,vis_inactive_resume/_search', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        // linkedinAddress é text no vis_resume: a frase acha os candidatos e a igualdade exata fica aqui
        body: JSON.stringify({ size: 50, query: { match_phrase: { linkedinAddress } } }),
    });
    const hits = (await response.json()).hits.hits;
    return hits.filter((hit) => hit._source.linkedinAddress === linkedinAddress).map((hit) => ({ index: hit._index, source: hit._source }));
}

const sameSet = (a, b) => JSON.stringify([...(a || [])].map(String).sort()) === JSON.stringify([...(b || [])].map(String).sort());
const currentYear = new Date().getFullYear();
const rows = [];
for (const [index, item] of sample.entries()) {
    const saves = results.filter((r) => r.index === index && r.step === 'salvar');
    const blocked = results.filter((r) => r.index === index && r.step && r.step.startsWith('aba'));
    const reloads = results.filter((r) => r.index === index && r.step === 'recarga');
    const lastSave = saves[saves.length - 1];
    const lastReload = reloads[reloads.length - 1];
    const kind = lastReload ? lastReload.lifecycleKind : 'sem recarga';
    const found = await stored(item.resume.linkedinAddress);
    const differences = [];
    const deleted = kind === 'excluir' || kind === 'inativar-excluir';
    if (deleted && found.length) differences.push(`excluído pela tela, mas ainda em ${found.map((f) => f.index)}`);
    if (!deleted && found.length !== 1) differences.push(`${found.length} registros com este LinkedIn`);
    if (!deleted && found.length) {
        const s = found[0].source;
        const r = item.resume;
        const expectedIndex = 'vis_resume';
        found[0].index !== expectedIndex && differences.push(`está em ${found[0].index}`);
        for (const field of ['desiredJob', 'lastJob', 'resumeType', 'pcd', 'travel', 'negotiableClaim', 'disponibility', 'temporallyJobTime']) {
            const expected = r[field] === undefined ? undefined : r[field];
            const actual = s[field];
            const bothEmpty = (expected === undefined || expected === '' || expected === 0 || expected === false) && (actual === undefined || actual === '' || actual === 0 || actual === false);
            !bothEmpty && String(expected) !== String(actual) && differences.push(`${field}: enviado ${JSON.stringify(expected)} gravado ${JSON.stringify(actual)}`);
        }
        for (const field of ['clt', 'pj', 'btc']) {
            const expected = r[field] || 0;
            const actual = s[field] || 0;
            Number(expected) !== Number(actual) && differences.push(`${field}: enviado ${expected} gravado ${actual}`);
        }
        const expectedStartYear = currentYear - (r.experience || 0);
        Number(s.experience) !== expectedStartYear && differences.push(`experience: ${r.experience} anos devia gravar ${expectedStartYear}, gravado ${s.experience}`);
        !sameSet(r.ddd, s.ddd) && differences.push(`ddd: enviado ${(r.ddd || []).length} gravado ${(s.ddd || []).length}`);
        const languages = (list) => (list || []).map((l) => `${l.name}:${l.level}`);
        !sameSet(languages(r.spokenLanguage), languages(s.spokenLanguage)) && differences.push(`idiomas: enviado ${languages(r.spokenLanguage)} gravado ${languages(s.spokenLanguage)}`);
        const companiesOnScreen = lastReload && lastReload.form ? lastReload.form.companies : [];
        !sameSet(companiesOnScreen, s.notAllowedCompany) && differences.push(`empresas: tela ${JSON.stringify(companiesOnScreen)} gravado ${JSON.stringify(s.notAllowedCompany)}`);
        r.resumeType === 1 && !(s.skill || []).length && differences.push('currículo de TI gravado sem habilidades');
    }
    const lifecycleOk = !lastReload || (lastReload.lifecycle || []).every((step) => !step.action || step.ok);
    rows.push({
        index, email: item.email, kind: item.kind, resumeType: item.resume.resumeType,
        saved: !!(lastSave && lastSave.saved), saveMs: lastSave ? lastSave.saveMs : null,
        blockedAt: blocked.length && !lastSave ? blocked[blocked.length - 1].step : '',
        reloadDifferences: lastReload ? lastReload.differences : ['sem recarga'],
        lifecycle: kind, lifecycleOk, esDifferences: differences,
    });
}
fs.writeFileSync(path.join(dir, 'conferencia.json'), JSON.stringify(rows, null, 1));
for (const row of rows) {
    const problems = [row.blockedAt, ...row.reloadDifferences, ...(row.lifecycleOk ? [] : ['ciclo de vida falhou']), ...row.esDifferences].filter(Boolean);
    console.log(row.index, row.kind, row.resumeType, row.saved ? 'salvo' : 'NÃO SALVO', row.saveMs, row.lifecycle, problems.length ? problems.join(' | ') : 'ok');
}
