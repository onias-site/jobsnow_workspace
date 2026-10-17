// Carga concorrente sobre os currículos que já existem (vis_resume e vis_inactive_resume): para cada candidato da carga
// do profissionais2, login, GET, inativar, reativar, excluir, reinserir, fromText e logout, com N clientes simultâneos
// disputando as APIs. Mede, por requisição: endpoint, bytes de entrada e de saída, quantas requisições estavam em voo e
// o heap da JVM que atendeu (jstat -gc a cada 500 ms). Os níveis de concorrência vêm de THREADS; os currículos são
// repartidos entre os níveis na proporção do número de clientes, para cada nível ter itens para chegar ao seu N. Um nível
// com mais de STOP_ERROR_RATE de erros (5xx, timeout ou falha de conexão) interrompe os seguintes ("quanto o ambiente
// aguentar").
//
// Uso: node 10-carga-concorrente-curriculos.mjs <pasta de saída> [THREADS=10,50,100,250,500,1000] [LIMITE=0 (todos)]
//   env STOP_ERROR_RATE (padrão 0.05), CARGA (padrão C:\logs\carga-profissionais2), RESET_FROM (pasta de uma rodada
//   anterior: antes de tudo, devolve cada currículo à situação ativo/inativo do backup dela, pela API) e RESET_ONLY
//   (com RESET_FROM, só faz o reset e sai)
// Saídas na pasta: requests.csv (uma linha por requisição), summary.csv e summary.md (nível x endpoint),
//   falhas.jsonl (currículos que não voltaram), backup-vis_resume.jsonl e backup-vis_inactive_resume.jsonl (cópia do ES
//   antes de qualquer exclusão) e progress.log.
//
// Antes de excluir, todo currículo é copiado do ES. A reinserção usa o que o GET devolveu (a experiência volta de ano de
// início para anos); se o back recusar, tenta o corpo original da carga; o que ainda falhar é refeito no fim, um a um.
import fs from 'fs';
import http from 'http';
import path from 'path';
import { execSync, spawn } from 'child_process';
import { createHash } from 'crypto';

const [, , outDir, threadsArg, limitArg] = process.argv;
if (!outDir) {
    console.error('uso: node 10-carga-concorrente-curriculos.mjs <pasta de saída> [10,50,100,250,500,1000] [limite]');
    process.exit(1);
}
const LEVELS = (threadsArg || '10,50,100,250,500,1000').split(',').map(Number).filter((n) => n > 0);
const LIMIT = Number(limitArg || 0);
const STOP_ERROR_RATE = Number(process.env.STOP_ERROR_RATE || 0.05);
const LOAD_DIR = process.env.CARGA || 'C:\\logs\\carga-profissionais2';
const PASSWORD = 'Carga@2026Curriculo';
const UA = 'carga-concorrente';
const JN = 8080;
const VIS = 8081;
const JSTAT = 'C:\\Program Files\\Java\\jdk-17\\bin\\jstat.exe';
const TOKEN_FILE = 'com.jn.business.messages.JnMessages$JnNotifyUserAboutLoginToken.html';
const RESUME_FIELDS = ['ddd', 'desiredJob', 'disponibility', 'resumeType', 'skill', 'experience', 'spokenLanguage', 'linkedinAddress',
    'negotiableClaim', 'notAllowedCompany', 'pcd', 'temporallyJobTime', 'travel', 'lastJob', 'clt', 'pj', 'btc'];
// conta real, com outra senha: fica de fora
const SKIP = new Set(['onias85@gmail.com']);

fs.mkdirSync(outDir, { recursive: true });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const progress = (text) => {
    const line = `${new Date().toISOString()} ${text}`;
    console.log(line);
    fs.appendFileSync(path.join(outDir, 'progress.log'), line + '\n');
};

// ───────────────────────────── memória das JVMs (jstat) ─────────────────────────────
function pidOfPort(port) {
    const lines = execSync('netstat -ano', { encoding: 'utf8' }).split('\n');
    const listening = lines.find((l) => l.includes(`:${port} `) && l.includes('LISTENING'));
    if (!listening) throw new Error(`nada escutando na porta ${port}`);
    return listening.trim().split(/\s+/).pop();
}
const samples = { [JN]: [], [VIS]: [] };
const monitors = [];
function startMonitor(port) {
    const pid = pidOfPort(port);
    const proc = spawn(JSTAT, ['-gc', pid, '500']);
    let header = null;
    let buffer = '';
    proc.stdout.on('data', (chunk) => {
        buffer += chunk.toString();
        const lines = buffer.split('\n');
        buffer = lines.pop();
        for (const raw of lines) {
            const cols = raw.trim().split(/\s+/);
            if (cols[0] === 'S0C') { header = cols; continue; }
            if (!header || cols.length !== header.length) continue;
            const v = Object.fromEntries(header.map((h, i) => [h, Number(cols[i].replace(',', '.'))]));
            const usedMb = (v.S0U + v.S1U + v.EU + v.OU) / 1024;
            const capacityMb = (v.S0C + v.S1C + v.EC + v.OC) / 1024;
            samples[port].push({ t: Date.now(), usedMb, capacityMb });
        }
    });
    monitors.push(proc);
    progress(`jstat da porta ${port} (pid ${pid}) iniciado`);
}
function jvmAt(port, t) {
    const list = samples[port];
    let best = null;
    for (let i = list.length - 1; i >= 0; i--) {
        if (list[i].t <= t + 500) { best = list[i]; break; }
    }
    return best || list[0] || { usedMb: NaN, capacityMb: NaN };
}

// ───────────────────────────── HTTP com medição ─────────────────────────────
let agents = {};
let inFlight = 0;
let currentLevel = 0;
let currentPhase = '';
const records = [];
function call(port, method, template, uri, body, headers = {}) {
    const data = body === undefined ? null : JSON.stringify(body);
    const inBytes = data ? Buffer.byteLength(data) : 0;
    inFlight++;
    const concurrentAtStart = inFlight;
    const started = Date.now();
    const finish = (status, text, error = '') => {
        inFlight--;
        const ended = Date.now();
        const jvm = jvmAt(port, ended);
        records.push({ level: currentLevel, phase: currentPhase, api: port === JN ? 'jn' : 'vis', endpoint: `${method} ${template}`, status, error,
            inBytes, outBytes: Buffer.byteLength(text || ''), concurrentAtStart, concurrentAtEnd: inFlight + 1, ms: ended - started,
            heapUsedMb: Math.round(jvm.usedMb), heapCapacityMb: Math.round(jvm.capacityMb), at: new Date(started).toISOString() });
        let json = {};
        try { json = text ? JSON.parse(text) : {}; } catch { json = {}; }
        return { status, body: json };
    };
    return new Promise((resolve) => {
        const req = http.request({ host: 'localhost', port, method, path: encodeURI(uri), agent: agents[port], timeout: 120000,
            headers: { 'Content-Type': 'application/json', 'User-Agent': UA, ...(data ? { 'Content-Length': inBytes } : {}), ...headers } }, (res) => {
            let text = '';
            res.setEncoding('utf8');
            res.on('data', (c) => (text += c));
            res.on('end', () => resolve(finish(res.statusCode, text)));
        });
        req.on('timeout', () => req.destroy(new Error('timeout')));
        // o código diz a causa: ECONNRESET/ECONNREFUSED (o servidor recusou ou derrubou), timeout (os 120 s do cliente)
        req.on('error', (e) => resolve(finish(0, '', e.code || e.message)));
        if (data) req.write(data);
        req.end();
    });
}
async function pool(threads, items, worker) {
    let next = 0;
    const runners = Array.from({ length: Math.min(threads, items.length) }, async () => {
        while (next < items.length) {
            const item = items[next++];
            try { await worker(item); } catch (e) { item.error = String(e); }
        }
    });
    await Promise.all(runners);
}

// ───────────────────────────── login ─────────────────────────────
async function readToken(email, since) {
    const file = path.join('c:\\logs\\email', email, TOKEN_FILE);
    for (let i = 0; i < 120; i++) {
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
// com sessão corrente o login dá 409: o token por e-mail + salvar a senha de novo derruba a outra sessão, como o modal faz
async function login(item) {
    const email = item.email;
    await call(JN, 'HEAD', '/login/{email}/token', `/login/${email}/token`);
    const logged = await call(JN, 'POST', '/login/{email}', `/login/${email}`, { password: PASSWORD });
    if (logged.status === 200 && logged.body.sessionToken) { item.token = logged.body.sessionToken; return; }
    const since = Date.now();
    const sent = await call(JN, 'POST', '/login/{email}/token/language/{language}', `/login/${email}/token/language/portuguese`, {});
    const token = await readToken(email, sent.status === 429 ? 0 : since);
    const saved = await call(JN, 'POST', '/login/{email}/password', `/login/${email}/password`, { password: PASSWORD, confirmPassword: PASSWORD, token });
    item.token = saved.status === 200 && saved.body.sessionToken ? saved.body.sessionToken : '';
}
const auth = (item) => ({ sessionToken: item.token, email: item.email });

// ───────────────────────────── corpo da reinserção ─────────────────────────────
// o GET devolve o que foi gravado: a experiência gravada é o ano em que começou, e o save espera os anos
function bodyFromStored(item) {
    const stored = item.stored;
    const body = { email: item.email };
    for (const field of RESUME_FIELDS) {
        if (stored[field] !== undefined) body[field] = stored[field];
    }
    if (typeof body.experience === 'number' && body.experience > 1900) body.experience = new Date().getFullYear() - body.experience;
    return body;
}
async function save(item, body) {
    const saved = await call(VIS, 'POST', '/resume/{email}/language/{language}', `/resume/${item.email}/language/portuguese`, body, auth(item));
    return saved.status === 200;
}
async function reinsert(item) {
    if (await save(item, bodyFromStored(item))) { item.reinserted = true; return; }
    if (item.original && await save(item, item.original)) { item.reinserted = true; item.reinsertedWith = 'original'; return; }
    item.reinserted = false;
}

// ───────────────────────────── backup do ES ─────────────────────────────
async function backup(index) {
    const file = path.join(outDir, `backup-${index}.jsonl`);
    fs.writeFileSync(file, '');
    let response = await fetch(`http://localhost:9200/${index}/_search?scroll=2m&size=1000`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{"query":{"match_all":{}}}' }).then((r) => r.json());
    let total = 0;
    while (response.hits && response.hits.hits.length) {
        fs.appendFileSync(file, response.hits.hits.map((hit) => JSON.stringify({ _id: hit._id, _source: hit._source })).join('\n') + '\n');
        total += response.hits.hits.length;
        response = await fetch('http://localhost:9200/_search/scroll', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ scroll: '2m', scroll_id: response._scroll_id }) }).then((r) => r.json());
    }
    progress(`backup de ${index}: ${total} documentos em ${file}`);
}

// ───────────────────────────── espera da escrita assíncrona ─────────────────────────────
// com a mensageria assíncrona a API responde antes de gravar: o login devolve o token antes de a sessão existir (o GET
// logo depois dá 401) e o inativar responde antes de mover o currículo (o reativar chegaria a tempo de inativar de novo).
// Por isso, depois de cada fase que grava, o script consulta o ES até ver o estado esperado, e mede essa espera.
// e-mail e token são gravados como SHA-1 em hexadecimal com sinal (BigInteger.toString(16) do CcpHashDecorator)
const sha1Signed = (text) => BigInt.asIntN(160, BigInt('0x' + createHash('sha1').update(text, 'utf8').digest('hex'))).toString(16);
const emailHash = sha1Signed;
const SETTLE_TIMEOUT = Number(process.env.SETTLE_TIMEOUT || 180000);
const settles = [];
// valores de `field` encontrados em `index` (o token da sessão é text: o "-" do começo não vira termo)
async function foundValues(index, field, values) {
    const found = new Set();
    for (let i = 0; i < values.length; i += 1000) {
        const chunk = values.slice(i, i + 1000);
        const response = await fetch(`http://localhost:9200/${index}/_search?size=10000&_source=${field}`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: { terms: { [field]: chunk } } }) }).then((r) => r.json());
        (response.hits ? response.hits.hits : []).forEach((hit) => found.add(String(hit._source[field]).replace(/^-/, '')));
    }
    return found;
}
async function sessionsReady(items) {
    const hashes = items.map((item) => sha1Signed(item.token).replace(/^-/, ''));
    const found = await foundValues('jn_login_session_validation', 'token', hashes);
    return hashes.every((hash) => found.has(hash));
}
// 'A' ativo, 'I' inativo, '-' em nenhuma das duas
async function locations(items) {
    const hashes = items.map((item) => emailHash(item.email));
    const active = await foundValues('vis_resume', 'email', hashes);
    const inactive = await foundValues('vis_inactive_resume', 'email', hashes);
    const strip = (hash) => hash.replace(/^-/, '');
    return new Map(items.map((item, i) => [item, active.has(strip(hashes[i])) ? 'A' : inactive.has(strip(hashes[i])) ? 'I' : '-']));
}
async function locationsAre(items, expected) {
    const now = await locations(items);
    return items.every((item) => now.get(item) === expected(item));
}
async function awaitWrites(name, items, check) {
    if (!items.length) return;
    const started = Date.now();
    let converged = false;
    while (Date.now() - started < SETTLE_TIMEOUT) {
        if (await check()) { converged = true; break; }
        await sleep(250);
    }
    const ms = Date.now() - started;
    settles.push({ level: currentLevel, phase: name, items: items.length, ms, converged });
    progress(`  nível ${currentLevel} | espera da escrita assíncrona depois de ${name}: ${ms} ms${converged ? '' : ` (não convergiu em ${SETTLE_TIMEOUT / 1000} s)`}`);
}
const awaitSessions = (name, items) => awaitWrites(name, items, () => sessionsReady(items));
const opposite = (location) => (location === 'A' ? 'I' : 'A');

// ───────────────────────────── reset pela API ─────────────────────────────
const readBackup = (dir, index) => new Set(fs.readFileSync(path.join(dir, `backup-${index}.jsonl`), 'utf8').split('\n').filter(Boolean)
    .map((line) => JSON.parse(line)._source.email));
async function idsIn(index) {
    const ids = new Set();
    let response = await fetch(`http://localhost:9200/${index}/_search?scroll=2m&size=1000&_source=email`).then((r) => r.json());
    while (response.hits && response.hits.hits.length) {
        response.hits.hits.forEach((hit) => ids.add(hit._source.email));
        response = await fetch('http://localhost:9200/_search/scroll', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ scroll: '2m', scroll_id: response._scroll_id }) }).then((r) => r.json());
    }
    return ids;
}
// devolve cada currículo à situação do backup de uma rodada anterior (ativo ou inativo; o que sumiu volta com o corpo
// original da carga), sempre pela API, para os grupos de hash do jn acompanharem; não entra no relatório
async function resetFrom(dir, candidates) {
    const backupActive = readBackup(dir, 'vis_resume');
    const backupInactive = readBackup(dir, 'vis_inactive_resume');
    const where = async () => ({ active: await idsIn('vis_resume'), inactive: await idsIn('vis_inactive_resume') });
    const pending = (now) => candidates.filter((item) => {
        const id = emailHash(item.email);
        const expected = backupActive.has(id) ? 'A' : backupInactive.has(id) ? 'I' : '-';
        const current = now.active.has(id) ? 'A' : now.inactive.has(id) ? 'I' : '-';
        item.resetMissing = current === '-' && expected !== '-';
        item.resetToggle = expected !== '-' && current !== '-' && expected !== current || item.resetMissing && expected === 'I';
        return item.resetMissing || item.resetToggle;
    });
    const toFix = pending(await where());
    progress(`reset: ${toFix.length} currículos fora da situação do backup (${toFix.filter((i) => i.resetMissing).length} ausentes)`);
    currentLevel = 0;
    currentPhase = 'reset';
    agents = { [JN]: new http.Agent({ keepAlive: true, maxSockets: 10 }), [VIS]: new http.Agent({ keepAlive: true, maxSockets: 10 }) };
    await pool(10, toFix, login);
    const logged = toFix.filter((item) => item.token);
    await awaitSessions('login do reset', logged);
    const missing = logged.filter((item) => item.resetMissing);
    await pool(10, missing, (item) => save(item, item.original));
    await awaitWrites('salvar do reset', missing, () => locationsAre(missing, () => 'A'));
    const toToggle = logged.filter((item) => item.resetToggle);
    await pool(10, toToggle, (item) => call(VIS, 'DELETE', '/resume/{email}/language/{language}/status', `/resume/${item.email}/language/portuguese/status`, {}, auth(item)));
    await awaitWrites('situação do reset', toFix, async () => pending(await where()).length === 0);
    await pool(10, logged, (item) => call(JN, 'DELETE', '/login/{email}/{sessionToken}', `/login/${item.email}/${item.token}`, {}, auth(item)));
    logged.forEach((item) => delete item.token);
    settles.length = 0;
    const left = pending(await where());
    records.length = 0;
    progress(`reset: ${toFix.length - left.length} de ${toFix.length} devolvidos à situação do backup; ${left.length} restantes`);
    if (left.length) throw new Error(`reset incompleto: ${left.map((item) => item.email).join(', ')}`);
}

// ───────────────────────────── candidatos da carga ─────────────────────────────
function loadCandidates() {
    const files = ['curriculos.jsonl', 'experiencia-70/curriculos.jsonl', 'linkedin-com-hifen/curriculos.jsonl', 'linkedin-inventado/curriculos.jsonl'];
    const byEmail = new Map();
    for (const file of files) {
        const full = path.join(LOAD_DIR, file);
        if (!fs.existsSync(full)) continue;
        for (const line of fs.readFileSync(full, 'utf8').split('\n')) {
            if (!line.trim()) continue;
            const item = JSON.parse(line);
            if (SKIP.has(item.id)) continue;
            // o último corpo de cada e-mail vale: as recargas corrigiram o LinkedIn e a experiência
            byEmail.set(item.id, { email: item.id, original: item.resume, resumeText: item.resumeText || '' });
        }
    }
    const candidates = [...byEmail.values()];
    return LIMIT > 0 ? candidates.slice(0, LIMIT) : candidates;
}
// cada nível recebe uma fatia proporcional ao seu número de clientes
function slices(candidates) {
    const total = LEVELS.reduce((a, b) => a + b, 0);
    const result = [];
    let start = 0;
    LEVELS.forEach((threads, i) => {
        const size = i === LEVELS.length - 1 ? candidates.length - start : Math.round((candidates.length * threads) / total);
        result.push(candidates.slice(start, start + size));
        start += size;
    });
    return result;
}

// ───────────────────────────── uma rodada por nível ─────────────────────────────
async function phase(name, threads, items, worker) {
    currentPhase = name;
    const before = records.length;
    const started = Date.now();
    await pool(threads, items, worker);
    progress(`  nível ${threads} | ${name}: ${records.length - before} requisições em ${((Date.now() - started) / 1000).toFixed(1)} s`);
}
async function runLevel(threads, items) {
    currentLevel = threads;
    agents = { [JN]: new http.Agent({ keepAlive: true, maxSockets: threads }), [VIS]: new http.Agent({ keepAlive: true, maxSockets: threads }) };
    const firstRecord = records.length;
    progress(`nível ${threads}: ${items.length} candidatos`);

    await phase('login', threads, items, login);
    const logged = items.filter((item) => item.token);
    await awaitSessions('login', logged);
    await phase('get', threads, logged, async (item) => {
        const got = await call(VIS, 'GET', '/resume/{email}', `/resume/${item.email}`, undefined, auth(item));
        const active = got.body.vis_resume || {};
        const inactive = got.body.vis_inactive_resume || {};
        item.stored = Object.keys(active).length ? active : inactive;
        item.exists = got.status === 200 && Object.keys(item.stored).length > 0;
    });
    const existing = logged.filter((item) => item.exists);
    const initial = await locations(existing);
    await phase('inativar', threads, existing, (item) => call(VIS, 'DELETE', '/resume/{email}/language/{language}/status', `/resume/${item.email}/language/portuguese/status`, {}, auth(item)));
    await awaitWrites('inativar', existing, () => locationsAre(existing, (item) => opposite(initial.get(item))));
    await phase('reativar', threads, existing, (item) => call(VIS, 'DELETE', '/resume/{email}/language/{language}/status', `/resume/${item.email}/language/portuguese/status`, {}, auth(item)));
    await awaitWrites('reativar', existing, () => locationsAre(existing, (item) => initial.get(item)));
    await phase('excluir', threads, existing, (item) => call(VIS, 'DELETE', '/resume/{email}/language/{language}', `/resume/${item.email}/language/portuguese`, {}, auth(item)));
    await awaitWrites('excluir', existing, () => locationsAre(existing, () => '-'));
    await phase('reinserir', threads, existing, reinsert);
    const reinserted = existing.filter((item) => item.reinserted);
    await awaitWrites('reinserir', reinserted, () => locationsAre(reinserted, () => 'A'));
    const withText = existing.filter((item) => item.resumeText.trim().length > 0);
    await phase('fromText', threads, withText, (item) => call(VIS, 'POST', '/skills/fromText', '/skills/fromText', { text: item.resumeText, excludedSkill: [] }, auth(item)));
    await phase('logout', threads, logged, (item) => call(JN, 'DELETE', '/login/{email}/{sessionToken}', `/login/${item.email}/${item.token}`, {}, auth(item)));

    const levelRecords = records.slice(firstRecord);
    const errors = levelRecords.filter((r) => r.status === 0 || r.status >= 500).length;
    const errorRate = levelRecords.length ? errors / levelRecords.length : 0;
    progress(`nível ${threads}: ${levelRecords.length} requisições, ${errors} erros (${(errorRate * 100).toFixed(2)}%), ${existing.length} currículos no ciclo, ${items.length - logged.length} sem login`);
    return { errorRate, existing };
}

// ───────────────────────────── relatório ─────────────────────────────
const percentile = (values, p) => {
    if (!values.length) return 0;
    const sorted = [...values].sort((a, b) => a - b);
    return sorted[Math.min(sorted.length - 1, Math.floor((p / 100) * sorted.length))];
};
const avg = (values) => (values.length ? values.reduce((a, b) => a + b, 0) / values.length : 0);
function writeReports() {
    const columns = ['level', 'phase', 'api', 'endpoint', 'status', 'error', 'inBytes', 'outBytes', 'concurrentAtStart', 'concurrentAtEnd', 'ms', 'heapUsedMb', 'heapCapacityMb', 'at'];
    const csv = [columns.join(';'), ...records.map((r) => columns.map((c) => r[c]).join(';'))].join('\n');
    fs.writeFileSync(path.join(outDir, 'requests.csv'), csv);

    const groups = new Map();
    for (const r of records) {
        const key = `${r.level}|${r.endpoint}`;
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key).push(r);
    }
    const rows = [...groups.entries()].map(([key, list]) => {
        const [level, endpoint] = key.split('|');
        const heap = list.map((r) => r.heapUsedMb).filter((v) => !Number.isNaN(v));
        return {
            level: Number(level), endpoint, api: list[0].api, requests: list.length,
            errors: list.filter((r) => r.status === 0 || r.status >= 500).length,
            statuses: [...new Set(list.map((r) => r.status))].sort().join(' '),
            errorCodes: Object.entries(list.filter((r) => r.error).reduce((acc, r) => ({ ...acc, [r.error]: (acc[r.error] || 0) + 1 }), {})).map(([code, n]) => `${code}:${n}`).join(' '),
            avgInBytes: Math.round(avg(list.map((r) => r.inBytes))), maxInBytes: Math.max(...list.map((r) => r.inBytes)),
            avgOutBytes: Math.round(avg(list.map((r) => r.outBytes))), maxOutBytes: Math.max(...list.map((r) => r.outBytes)),
            avgConcurrent: Math.round(avg(list.map((r) => r.concurrentAtStart))), maxConcurrent: Math.max(...list.map((r) => r.concurrentAtStart)),
            p50Ms: percentile(list.map((r) => r.ms), 50), p95Ms: percentile(list.map((r) => r.ms), 95), maxMs: Math.max(...list.map((r) => r.ms)),
            heapMinMb: heap.length ? Math.min(...heap) : '', heapAvgMb: heap.length ? Math.round(avg(heap)) : '', heapMaxMb: heap.length ? Math.max(...heap) : '',
            heapCapacityMb: Math.max(...list.map((r) => r.heapCapacityMb).filter((v) => !Number.isNaN(v)), 0),
        };
    }).sort((a, b) => a.level - b.level || a.endpoint.localeCompare(b.endpoint));
    const summaryColumns = Object.keys(rows[0] || {});
    fs.writeFileSync(path.join(outDir, 'summary.csv'), [summaryColumns.join(';'), ...rows.map((r) => summaryColumns.map((c) => r[c]).join(';'))].join('\n'));

    const md = [
        '# Carga concorrente sobre os currículos',
        '',
        `Níveis pedidos: ${LEVELS.join(', ')} clientes simultâneos. Requisições: ${records.length}.`,
        '',
        '| Clientes | Endpoint | API | Req. | Erros | Status | Causa dos status 0 | Entrada méd. (B) | Saída méd. (B) | Em voo méd. | Em voo máx. | p50 (ms) | p95 (ms) | Heap méd. (MB) | Heap máx. (MB) | Heap total (MB) |',
        '|--:|---|---|--:|--:|---|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|',
        ...rows.map((r) => `| ${r.level} | \`${r.endpoint}\` | ${r.api} | ${r.requests} | ${r.errors} | ${r.statuses} | ${r.errorCodes} | ${r.avgInBytes} | ${r.avgOutBytes} | ${r.avgConcurrent} | ${r.maxConcurrent} | ${r.p50Ms} | ${r.p95Ms} | ${r.heapAvgMb} | ${r.heapMaxMb} | ${r.heapCapacityMb} |`),
        '',
        '## Espera da escrita assíncrona',
        '',
        'Tempo entre o fim de uma fase (todas as respostas recebidas) e o ES mostrar o que ela gravou.',
        '',
        '| Clientes | Depois de | Itens | Espera (ms) | Convergiu |',
        '|--:|---|--:|--:|---|',
        ...settles.map((s) => `| ${s.level} | ${s.phase} | ${s.items} | ${s.ms} | ${s.converged ? 'sim' : 'não'} |`),
    ].join('\n');
    fs.writeFileSync(path.join(outDir, 'summary.md'), md);
    fs.writeFileSync(path.join(outDir, 'settles.csv'), ['level;phase;items;ms;converged', ...settles.map((s) => `${s.level};${s.phase};${s.items};${s.ms};${s.converged}`)].join('\n'));
}

// ───────────────────────────── principal ─────────────────────────────
const candidates = loadCandidates();
progress(`${candidates.length} candidatos da carga; níveis ${LEVELS.join(', ')}; parada com mais de ${STOP_ERROR_RATE * 100}% de erros`);
if (process.env.RESET_FROM) {
    await resetFrom(process.env.RESET_FROM, candidates);
    if (process.env.RESET_ONLY) process.exit(0);
}
await backup('vis_resume');
await backup('vis_inactive_resume');
startMonitor(JN);
startMonitor(VIS);
await sleep(1500);

const parts = slices(candidates);
const failures = [];
let stoppedAt = null;
for (let i = 0; i < LEVELS.length; i++) {
    if (stoppedAt) break;
    const { errorRate, existing } = await runLevel(LEVELS[i], parts[i]);
    failures.push(...existing.filter((item) => !item.reinserted));
    if (errorRate > STOP_ERROR_RATE) {
        stoppedAt = LEVELS[i];
        progress(`nível ${LEVELS[i]} passou de ${STOP_ERROR_RATE * 100}% de erros: os níveis seguintes não rodam (os currículos deles não foram tocados)`);
    }
}

// o que não voltou é refeito um a um, com login novo
if (failures.length) {
    currentLevel = 1;
    agents = { [JN]: new http.Agent({ keepAlive: true, maxSockets: 1 }), [VIS]: new http.Agent({ keepAlive: true, maxSockets: 1 }) };
    await phase('reparo', 1, failures, async (item) => {
        await login(item);
        if (item.token) await awaitSessions('login do reparo', [item]);
        await reinsert(item);
    });
}
const lost = failures.filter((item) => !item.reinserted);
fs.writeFileSync(path.join(outDir, 'falhas.jsonl'), lost.map((item) => JSON.stringify({ email: item.email, stored: item.stored, original: item.original })).join('\n'));
progress(`reparo: ${failures.length - lost.length} de ${failures.length} reinseridos; ${lost.length} em falhas.jsonl`);

monitors.forEach((proc) => proc.kill());
writeReports();
progress(`fim: ${records.length} requisições; relatório em ${path.join(outDir, 'summary.md')}${stoppedAt ? ` (parou no nível ${stoppedAt})` : ''}`);
process.exit(0);
