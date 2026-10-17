// Ciclo de vida dos currículos já carregados pelo 04-carga-de-curriculos.mjs: inativar, reativar, salvar inativo,
// excluir ativo e inativo, status de quem não tem currículo e concorrência. Para cada ação confere o ES (vis_resume,
// vis_inactive_resume, jn_grouper, jn_inactive_grouper) e o e-mail de aviso em c:\logs\email\<e-mail>\.
//
// Uso: node 05-ciclo-de-vida-curriculos.mjs <pasta da carga> [quantidade por caso=10]
//   CASOS=7 (variável de ambiente, lista separada por vírgula) roda só os casos pedidos; sem ela, todos
// Lê curriculos.jsonl e resultados.jsonl da pasta; grava ciclo-de-vida.jsonl (uma linha por verificação).
import fs from 'fs';
import http from 'http';
import path from 'path';

const [, , dir, perCaseArg] = process.argv;
const PER_CASE = Number(perCaseArg || 10);
const CASES = (process.env.CASOS || '1,2,3,4,5,6,7,8').split(',');
const wants = (caseName) => CASES.includes(caseName.split('-')[0]);
const PASSWORD = 'Carga@2026Curriculo';
const UA = 'roteiro-04-carga';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function request(port, method, uri, body, headers = {}) {
    const data = JSON.stringify(body === undefined ? {} : body);
    const started = Date.now();
    return new Promise((resolve) => {
        const req = http.request({ host: 'localhost', port, method, path: encodeURI(uri), timeout: 900000,
            headers: { 'Content-Type': 'application/json', 'User-Agent': UA, 'Content-Length': Buffer.byteLength(data), ...headers } }, (res) => {
            let text = '';
            res.setEncoding('utf8');
            res.on('data', (c) => (text += c));
            res.on('end', () => {
                let json = {};
                try { json = text ? JSON.parse(text) : {}; } catch { json = { raw: text.slice(0, 300) }; }
                resolve({ status: res.statusCode, body: json, ms: Date.now() - started });
            });
        });
        req.on('timeout', () => req.destroy(new Error('timeout')));
        req.on('error', (e) => resolve({ status: 0, body: { error: String(e) }, ms: Date.now() - started }));
        req.write(data);
        req.end();
    });
}
const es = (method, uri, body) => request(9200, method, uri, body);

const out = fs.createWriteStream(path.join(dir, 'ciclo-de-vida.jsonl'), { flags: 'a' });
const summary = {};
function check(caseName, email, label, ok, detail = {}) {
    summary[caseName] = summary[caseName] || { ok: 0, fail: 0 };
    summary[caseName][ok ? 'ok' : 'fail']++;
    out.write(JSON.stringify({ case: caseName, email, label, ok, ...detail }) + '\n');
    if (!ok) console.log(`FALHA ${caseName} ${email} ${label} ${JSON.stringify(detail).slice(0, 300)}`);
}

// o token de sessão da carga não foi guardado: com sessão corrente o login dá 409, então desfaz o outro login como o
// modal faz (novo token por e-mail + salvar a senha de novo derruba as outras sessões)
async function readToken(email, since) {
    const file = path.join('c:\\logs\\email', email, 'com.jn.business.messages.JnMessages$JnNotifyUserAboutLoginToken.html');
    for (let i = 0; i < 80; i++) {
        try {
            if (fs.statSync(file).mtimeMs >= since - 50) {
                const match = fs.readFileSync(file, 'utf8').match(/esse token é ([A-Z0-9]{8})/);
                if (match) return match[1];
            }
        } catch {}
        await sleep(250);
    }
    return '';
}
async function session(email) {
    const login = await request(8082, 'POST', `/login/${email}`, { password: PASSWORD });
    if (login.status === 200 && login.body.sessionToken) return login.body.sessionToken;
    const since = Date.now();
    const sent = await request(8082, 'POST', `/login/${email}/token/language/portuguese`);
    // 429: o token desta hora já foi enviado e continua valendo, então serve o último e-mail
    const token = await readToken(email, sent.status === 429 ? 0 : since);
    const saved = await request(8082, 'POST', `/login/${email}/password`, { password: PASSWORD, confirmPassword: PASSWORD, token });
    return saved.status === 200 && saved.body.sessionToken ? saved.body.sessionToken : '';
}
const auth = (email, token) => ({ sessionToken: token, email });

// o id do currículo no ES: o e-mail fica transformado, então busca pelo hash gravado comparando o desiredJob e o linkedin
async function findStored(index, resume) {
    const r = await es('POST', `/${index}/_search`, { size: 5, query: { term: { 'linkedinAddress.keyword': resume.linkedinAddress } } });
    let hits = (r.body.hits && r.body.hits.hits) || [];
    if (!hits.length) {
        const r2 = await es('POST', `/${index}/_search`, { size: 5, query: { match_phrase: { linkedinAddress: resume.linkedinAddress } } });
        hits = (r2.body.hits && r2.body.hits.hits) || [];
    }
    return hits.find((h) => h._source.linkedinAddress === resume.linkedinAddress);
}
async function groupsWith(index, id) {
    const r = await es('POST', `/${index}/_count`, { query: { term: { child: id } } });
    return r.body.count || 0;
}
async function poll(fn, until, timeoutMs = 60000) {
    const start = Date.now();
    let value = await fn();
    while (!until(value) && Date.now() - start < timeoutMs) { await sleep(1000); value = await fn(); }
    return value;
}
function emailArrived(email, templateSuffix, since) {
    try {
        const folder = path.join('c:\\logs\\email', email);
        const file = fs.readdirSync(folder).find((f) => f.includes(templateSuffix));
        return !!file && fs.statSync(path.join(folder, file)).mtimeMs >= since - 1000;
    } catch { return false; }
}

// estado esperado: side = 'main' | 'twin' | 'none'
async function verifyState(caseName, email, resume, side, hashCount) {
    const main = await poll(() => findStored('vis_resume', resume), (v) => (side === 'main') === !!v);
    const twin = await poll(() => findStored('vis_inactive_resume', resume), (v) => (side === 'twin') === !!v);
    check(caseName, email, `vis_resume ${side === 'main' ? 'tem' : 'não tem'}`, (side === 'main') === !!main);
    check(caseName, email, `vis_inactive_resume ${side === 'twin' ? 'tem' : 'não tem'}`, (side === 'twin') === !!twin);
    const id = (main || twin || {})._id || resume.__id;
    if (!id) return;
    const inMain = await poll(() => groupsWith('jn_grouper', id), (c) => side === 'main' ? c >= hashCount : c === 0);
    const inTwin = await poll(() => groupsWith('jn_inactive_grouper', id), (c) => side === 'twin' ? c >= hashCount : c === 0);
    check(caseName, email, 'grupos principais', side === 'main' ? inMain === hashCount : inMain === 0, { inMain, hashCount });
    check(caseName, email, 'grupos gêmeos', side === 'twin' ? inTwin === hashCount : inTwin === 0, { inTwin, hashCount });
}

async function changeStatus(email, token) { return request(8081, 'DELETE', `/resume/${email}/language/portuguese/status`, {}, auth(email, token)); }
async function remove(email, token) { return request(8081, 'DELETE', `/resume/${email}/language/portuguese`, {}, auth(email, token)); }
async function save(email, token, resume) { return request(8081, 'POST', `/resume/${email}/language/portuguese`, resume, auth(email, token)); }
async function getData(email, token) { return request(8081, 'GET', `/resume/${email}`, {}, auth(email, token)); }

async function main() {
    const resumes = new Map(fs.readFileSync(path.join(dir, 'curriculos.jsonl'), 'utf8').trim().split('\n').map((l) => JSON.parse(l)).map((l) => [l.id, l]));
    const saved = fs.readFileSync(path.join(dir, 'resultados.jsonl'), 'utf8').trim().split('\n').map((l) => JSON.parse(l)).filter((r) => r.ok).map((r) => r.email);
    // os de poucos hashes primeiro: o caso testa o ciclo, não o volume
    const candidates = [];
    for (const email of saved) {
        const entry = resumes.get(email);
        const stored = await findStored('vis_resume', entry.resume);
        if (!stored) continue;
        entry.resume.__id = stored._id;
        candidates.push({ email, entry, id: stored._id, hashCount: (stored._source.hash || []).length });
    }
    candidates.sort((a, b) => a.hashCount - b.hashCount);
    console.log(`${candidates.length} currículos ativos encontrados`);
    const take = (n) => candidates.splice(0, n);

    const run = async (caseName, list, fn) => {
        if (!wants(caseName)) return;
        for (const item of list) {
            const token = await session(item.email);
            if (!token) { check(caseName, item.email, 'login', false); continue; }
            await fn(item, token);
        }
    };
    const statusCheck = (caseName, item, r, expected) => check(caseName, item.email, `HTTP ${expected}`, r.status === expected, { status: r.status, ms: r.ms, body: r.status === expected ? undefined : r.body });
    const mail = async (caseName, item, suffix, since) => check(caseName, item.email, `e-mail ${suffix}`, await poll(async () => emailArrived(item.email, suffix, since), (v) => v, 30000));

    // 1, 2 e 3: inativar; reativar metade; salvar inativo
    const inactivate = take(PER_CASE * 2);
    await run('1-inativar', inactivate, async (item, token) => {
        const since = Date.now();
        statusCheck('1-inativar', item, await changeStatus(item.email, token), 200);
        await verifyState('1-inativar', item.email, item.entry.resume, 'twin', item.hashCount);
        const data = await getData(item.email, token);
        check('1-inativar', item.email, 'GET devolve vis_inactive_resume', !!(data.body.vis_inactive_resume && Object.keys(data.body.vis_inactive_resume).length), { status: data.status });
        await mail('1-inativar', item, 'VisNotifyUserAboutDeactivatedResume', since);
    });
    await run('2-reativar', inactivate.slice(0, PER_CASE), async (item, token) => {
        const since = Date.now();
        statusCheck('2-reativar', item, await changeStatus(item.email, token), 200);
        await verifyState('2-reativar', item.email, item.entry.resume, 'main', item.hashCount);
        await mail('2-reativar', item, 'VisNotifyUserAboutReactivatedResume', since);
    });
    await run('3-salvar-inativo', inactivate.slice(PER_CASE, PER_CASE + 5), async (item, token) => {
        statusCheck('3-salvar-inativo', item, await save(item.email, token, stripId(item.entry.resume)), 200);
        await verifyState('3-salvar-inativo', item.email, item.entry.resume, 'main', item.hashCount);
    });
    // 4 e 5: excluir ativo e inativo
    await run('4-excluir-ativo', take(PER_CASE), async (item, token) => {
        const since = Date.now();
        statusCheck('4-excluir-ativo', item, await remove(item.email, token), 200);
        await verifyState('4-excluir-ativo', item.email, item.entry.resume, 'none', item.hashCount);
        await mail('4-excluir-ativo', item, 'VisNotifyUserAboutDeletedResume', since);
    });
    const toDeleteInactive = inactivate.slice(PER_CASE + 5);
    await run('5-excluir-inativo', toDeleteInactive, async (item, token) => {
        const since = Date.now();
        statusCheck('5-excluir-inativo', item, await remove(item.email, token), 200);
        await verifyState('5-excluir-inativo', item.email, item.entry.resume, 'none', item.hashCount);
        await mail('5-excluir-inativo', item, 'VisNotifyUserAboutDeletedResume', since);
    });
    // 6: status, exclusão e leitura de quem já não tem currículo
    await run('6-sem-curriculo', toDeleteInactive.slice(0, 3), async (item, token) => {
        statusCheck('6-sem-curriculo', item, await changeStatus(item.email, token), 404);
        const again = await remove(item.email, token);
        check('6-sem-curriculo', item.email, 'excluir de novo', [200, 404].includes(again.status), { status: again.status, body: again.body });
        const data = await getData(item.email, token);
        check('6-sem-curriculo', item.email, 'GET sem currículo', [200, 404].includes(data.status) && !(data.body.vis_resume && Object.keys(data.body.vis_resume).length), { status: data.status, body: data.body });
    });
    // 7: concorrência, inativar e reativar ao mesmo tempo o mesmo currículo, e vários em paralelo
    const concurrent = wants('7') ? take(8) : [];
    const tokens = await Promise.all(concurrent.map((c) => session(c.email)));
    const results = await Promise.all(concurrent.map((c, i) => Promise.all([changeStatus(c.email, tokens[i]), changeStatus(c.email, tokens[i])])));
    for (let i = 0; i < concurrent.length; i++) {
        const item = concurrent[i];
        const statuses = results[i].map((r) => r.status);
        // desde 2026-10-14 a troca que esbarra na outra responde 200 (antes 500 ou 301)
        check('7-concorrencia', item.email, 'as duas respostas 200', statuses.every((s) => s === 200), { statuses });
        // espera o refresh do ES, como o verifyState dos outros casos: lido na hora, o grupo ainda aparecia dos dois
        // lados (ou de nenhum) e a falha era do roteiro, não do sistema (visto em 2026-10-15)
        const readState = async () => {
            const main = await findStored('vis_resume', item.entry.resume);
            const twin = await findStored('vis_inactive_resume', item.entry.resume);
            const inMain = await groupsWith('jn_grouper', item.id);
            const inTwin = await groupsWith('jn_inactive_grouper', item.id);
            return { main, twin, inMain, inTwin };
        };
        const isCoherent = ({ main, twin, inMain, inTwin }) => (!!main !== !!twin) && (main ? inMain === item.hashCount && inTwin === 0 : inTwin === item.hashCount && inMain === 0);
        const { main, twin, inMain, inTwin } = await poll(readState, isCoherent, 30000);
        const coherent = isCoherent({ main, twin, inMain, inTwin });
        check('7-concorrencia', item.email, 'currículo em um só lado e grupos no mesmo lado', coherent, { statuses, main: !!main, twin: !!twin, inMain, inTwin, hashCount: item.hashCount });
    }
    // 8: os de status 0 no índice legado ficam inativos
    const legacyInactive = candidates.filter((c) => c.entry.meta.legacyStatus === 0);
    await run('8-status-legado', legacyInactive, async (item, token) => {
        statusCheck('8-status-legado', item, await changeStatus(item.email, token), 200);
    });
    out.end();
    console.log(JSON.stringify(summary, null, 1));
}
const stripId = (resume) => { const { __id, ...rest } = resume; return rest; };

main();
