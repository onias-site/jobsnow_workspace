// Roteiro 09 (reescrito em 2026-11-10 a partir do 13-quem-me-viu-por-tipo-de-recrutador.mjs; a versão de 2026-11-03
// usava contas fixas que não existem mais depois dos resets).
// Foco: LinkedIn compartilhado entre dois candidatos, Currículos visualizados de cada recrutador, Quem me viu, e o D4
// (empresa indesejada: Empresa09, empresa 09, EMPRESA-09, nome de 3 letras no meio do domínio, freelancer não barrado).
//
// Uso (pasta corrente = automacao; estado em dyn-state.json; variável D opcional, padrão 20261109):
//   node 09-dinamica-candidato-recrutador.mjs candidates   cadastra os 6 candidatos e salva o currículo de cada um
//   node 09-dinamica-candidato-recrutador.mjs sessions     abre a sessão dos 6 recrutadores (cadastro pelo token do e-mail mock)
//   (rodar SendResumesToRecruiters.java com os 6 recrutadores: node ... recruiters imprime a lista)
//   node 09-dinamica-candidato-recrutador.mjs links        lê Currículos da semana de cada recrutador, guarda os links e confere o D4
//   node 09-dinamica-candidato-recrutador.mjs views        executa a matriz do D2.2 (com repetições)
//   node 09-dinamica-candidato-recrutador.mjs check        Quem me viu de cada candidato e Currículos visualizados de cada recrutador
//   node 09-dinamica-candidato-recrutador.mjs view <recrutador> <candidato> [apelido]
//   node 09-dinamica-candidato-recrutador.mjs url <recrutador> <candidato>    link para abrir no Chrome
//   node 09-dinamica-candidato-recrutador.mjs resave <candidato> [empresa...] salva de novo o currículo (exige a cota liberada)
//   node 09-dinamica-candidato-recrutador.mjs storage <e-mail>                JSON do `login` para o localStorage do Chrome
// As sessões usam o User-Agent do Chrome (157) para servirem também no localStorage da tela em localhost.
import fs from 'fs';
import path from 'path';
import crypto from 'crypto';

const D = process.env.D || '20261109';
const UA = process.env.UA || 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36';
const PASSWORD = 'Roteiro@2026x';
const TOKEN_TEMPLATE = 'com.jn.business.messages.JnMessages$JnNotifyUserAboutLoginToken.html';
const F1 = `rec09a.${D}@gmail.com`, F2 = `rec09b.${D}@gmail.com`;
const S1 = `rec091.${D}@empresa09.com.br`, S2 = `rec092.${D}@empresa09.com.br`;
const O1 = `rec09c.${D}@consultoria09.com.br`;
const L = `rec09l.${D}@teste.com`; // o recrutador logado na tela (2.3)
const RECRUITERS = [F1, F2, S1, S2, O1, L];
const CAND = Object.fromEntries('ABCDEF'.split('').map((k) => [k, `cand09${k.toLowerCase()}.${D}@teste.com`]));
// F usa o LinkedIn de A; B, C, D e E citam empresas indesejadas
const LINKEDIN = { F: 'A' };
const COMPANIES = { B: ['Empresa09'], C: ['empresa 09'], D: ['EMPRESA-09'], E: ['pre'] };
// D4: quem NÃO pode aparecer na lista de cada recrutador
const FORBIDDEN = { [S1]: ['B', 'C', 'D'], [S2]: ['B', 'C', 'D'] };
// D2.2: [recrutador, candidato]; repetições e o LinkedIn compartilhado de propósito
const VIEWS = [
  [F1, 'A'], [S1, 'A'], [O1, 'A'], [F1, 'A'],
  [F2, 'F'], [S2, 'F'], [S1, 'F'],
  [F1, 'B'], [F2, 'B'], [O1, 'B'],
  [F2, 'C'],
  [O1, 'D'],
  [S1, 'E'], [S2, 'E'],
];
// Quem me viu esperado (mês corrente) depois do D2.2 e do 2.3 (L vê C pela tela). A e F dividem o LinkedIn: mesmos números.
const AF = { freelancer: 2, 'empresa09.com.br': 2, 'consultoria09.com.br': 1 };
const EXPECTED_VIEWERS = {
  A: AF, F: AF,
  B: { freelancer: 2, 'consultoria09.com.br': 1 },
  C: { freelancer: 1, 'teste.com': 1 },
  D: { 'consultoria09.com.br': 1 },
  E: { 'empresa09.com.br': 2 },
};
// Currículos visualizados esperados: um item por LinkedIn (A e F = um item, o do LinkedIn de A)
const EXPECTED_VIEWED = { [F1]: ['A', 'B'], [F2]: ['A', 'B', 'C'], [S1]: ['A', 'E'], [S2]: ['A', 'E'], [O1]: ['A', 'B', 'D'], [L]: ['C'] };
const linkedinOf = (key) => `https://www.linkedin.com/in/cand09${(LINKEDIN[key] || key).toLowerCase()}${D}`;
const RESUME = (key, companies = COMPANIES[key]) => {
  const r = {
    ddd: [11], desiredJob: `Programador Java roteiro 09 ${key}`, disponibility: 5, experience: 4, resumeType: 1, temporallyJobTime: 0, pj: 9000,
    linkedinAddress: linkedinOf(key),
    resumeText: 'Desenvolvedor Java com Spring Boot, Elasticsearch, Docker, Kubernetes, SQL, Git, React e TypeScript.',
  };
  if (companies && companies.length) r.notAllowedCompany = companies;
  return r;
};
const STATE = 'dyn-state.json';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const state = fs.existsSync(STATE) ? JSON.parse(fs.readFileSync(STATE, 'utf8')) : { sessions: {}, links: {} };
const save = () => fs.writeFileSync(STATE, JSON.stringify(state, null, 1));
const month = () => { const n = new Date(); return `${n.getFullYear()}${String(n.getMonth() + 1).padStart(2, '0')}`; };
const keyOf = (who) => (CAND[who] ? who : who);
const recruiterOf = (who) => RECRUITERS.find((r) => r === who || r.startsWith(who + '.')) || who;

function hashOf(email) {
  const hex = crypto.createHash('sha1').update(email).digest('hex');
  let n = BigInt('0x' + hex);
  if (n >= (1n << 159n)) n -= (1n << 160n);
  return n < 0n ? '-' + (-n).toString(16) : n.toString(16);
}
async function call(port, method, uri, body, headers = {}) {
  const r = await fetch(`http://localhost:${port}${uri}`, { method, headers: { 'Content-Type': 'application/json', 'User-Agent': UA, ...headers }, body: method === 'GET' ? undefined : JSON.stringify(body || {}) });
  const t = await r.text(); let j; try { j = t ? JSON.parse(t) : {}; } catch { j = { raw: t.slice(0, 300) }; }
  return { status: r.status, body: j };
}
async function readToken(email, since) {
  const file = path.join('c:\\logs\\email', email, TOKEN_TEMPLATE);
  for (let i = 0; i < 80; i++) {
    try { if (fs.statSync(file).mtimeMs >= since - 50) { const m = fs.readFileSync(file, 'utf8').match(/token [^<]*?([A-Z0-9]{6,})/); if (m) return m[1]; } } catch {}
    await sleep(250);
  }
  return '';
}
async function session(email, goal) {
  const login = await call(8082, 'POST', `/login/${email}`, { password: PASSWORD });
  if (login.status === 200 && login.body.sessionToken) { await sleep(3000); return login.body.sessionToken; }
  if (login.status !== 404) { console.log('  login', email, login.status, JSON.stringify(login.body).slice(0, 150)); return ''; }
  await call(8082, 'POST', `/login/${email}/token`);
  await call(8082, 'POST', `/login/${email}/pre-registration`, { channel: 'telegram', goal }); // goal: jobs | recruiting
  const since = Date.now();
  await call(8082, 'POST', `/login/${email}/token/language/portuguese`);
  const token = await readToken(email, since);
  const saved = await call(8082, 'POST', `/login/${email}/password`, { password: PASSWORD, confirmPassword: PASSWORD, token });
  await sleep(3000); // a sessão nasce por escrita assíncrona (R05-1: chamada antes disso dá 401 e conta tentativa)
  if (saved.status !== 200) { console.log('  password', email, saved.status, JSON.stringify(saved.body).slice(0, 150)); return ''; }
  return saved.body.sessionToken || '';
}
const auth = (email) => ({ sessionToken: state.sessions[email], email });
async function weekList(r) {
  const res = await call(8081, 'GET', `/recruiter/${r}/resumes-of-the-week`, null, auth(r));
  const list = Array.isArray(res.body) ? res.body : (res.body.resumes || res.body.list || Object.values(res.body).find(Array.isArray) || []);
  return { status: res.status, list };
}
const [, , cmd, a, b, ...rest] = process.argv;

if (cmd === 'recruiters') console.log(RECRUITERS.join(' '));
if (cmd === 'candidates') {
  for (const [key, email] of Object.entries(CAND)) {
    if (!state.sessions[email]) state.sessions[email] = await session(email, 'jobs');
    const saved = await call(8081, 'POST', `/resume/${email}/language/portuguese`, RESUME(key), auth(email));
    console.log(key, email, 'sessão', state.sessions[email] ? 'ok' : 'FALHOU', 'save', saved.status, JSON.stringify(saved.body).slice(0, 200));
    save();
  }
}
if (cmd === 'resave') {
  const email = CAND[a];
  const companies = [b, ...rest].filter(Boolean);
  // como a tela: a lista vazia vai como [] (sem o campo, o update não apaga as empresas gravadas)
  const body = { ...RESUME(a, companies), notAllowedCompany: companies };
  const saved = await call(8081, 'POST', `/resume/${email}/language/portuguese`, body, auth(email));
  console.log(a, email, 'empresas', JSON.stringify(companies), 'save', saved.status, JSON.stringify(saved.body).slice(0, 300));
}
if (cmd === 'sessions') {
  for (const r of RECRUITERS) { if (!state.sessions[r]) state.sessions[r] = await session(r, 'recruiting'); console.log(r, state.sessions[r] ? 'ok' : 'FALHOU'); save(); }
}
if (cmd === 'links') {
  let failures = 0;
  for (const r of RECRUITERS) {
    const { status, list } = await weekList(r);
    state.links[r] = {};
    for (const [key, c] of Object.entries(CAND)) { const row = list.find((x) => x.resumeId === hashOf(hashOf(c))); if (row) state.links[r][key] = { email: r, resumeId: row.resumeId, token: row.token }; }
    const present = Object.keys(state.links[r]);
    const forbidden = FORBIDDEN[r] || [];
    const expected = Object.keys(CAND).filter((k) => !forbidden.includes(k));
    const ok = JSON.stringify(present) === JSON.stringify(expected);
    if (!ok) failures++;
    console.log(r, status, 'lista', list.length, 'candidatos', present.join(',') || 'NENHUM', ok ? 'OK' : `DIVERGE esperado ${expected.join(',')}`);
  }
  save();
  process.exitCode = failures ? 1 : 0;
}
if (cmd === 'present') { // node ... present <recrutador> : quais candidatos estão na lista agora (sem gravar)
  const r = recruiterOf(a);
  const { status, list } = await weekList(r);
  const present = Object.entries(CAND).filter(([, c]) => list.some((x) => x.resumeId === hashOf(hashOf(c)))).map(([k]) => k);
  console.log(r, status, 'lista', list.length, 'candidatos', present.join(','));
}
if (cmd === 'views') {
  for (const [r, key] of VIEWS) {
    const link = (state.links[r] || {})[key];
    if (!link) { console.log('SEM LINK', r, key); continue; }
    const v = await call(8081, 'POST', '/recruiter-email-link/view-resume', link);
    console.log('view', r, key, v.status, JSON.stringify(v.body).slice(0, 120));
    await sleep(1500); // o contador é escrito de forma assíncrona; a repetição precisa ver a visualização anterior
  }
}
if (cmd === 'view') {
  const r = recruiterOf(a); const link = state.links[r][b];
  const v = await call(8081, 'POST', '/recruiter-email-link/view-resume', link);
  console.log('view', r, b, v.status, JSON.stringify(v.body).slice(0, 200));
  if (rest[0]) { const s = await call(8081, 'POST', '/recruiter-email-link/alias', { ...link, alias: rest[0] }); console.log('alias', s.status, JSON.stringify(s.body).slice(0, 150)); }
}
if (cmd === 'check') {
  let failures = 0;
  const m = a || month();
  for (const [key, email] of Object.entries(CAND)) {
    const res = await call(8081, 'GET', `/resume/${email}/viewers/${m}`, null, auth(email));
    const got = {};
    for (const v of res.body.viewers || []) got[v.domain] = v.views;
    const exp = a ? {} : EXPECTED_VIEWERS[key];
    const ok = JSON.stringify(Object.entries(got).sort()) === JSON.stringify(Object.entries(exp).sort());
    if (!ok) failures++;
    console.log('quem me viu', key, res.status, ok ? 'OK' : 'DIVERGE', 'obtido', JSON.stringify(got), 'esperado', JSON.stringify(exp));
  }
  const linkedinKey = Object.fromEntries(Object.keys(CAND).map((k) => [linkedinOf(k), LINKEDIN[k] || k]));
  for (const r of RECRUITERS) {
    const res = await call(8081, 'GET', `/recruiter/${r}/viewed-resumes/${m}`, null, auth(r));
    // viewedResume: cada item é um texto JSON {alias, date, linkedin} (child do jn_grouper)
    const raw = res.body.viewedResume || Object.values(res.body).find(Array.isArray) || [];
    const items = raw.map((it) => (typeof it === 'string' ? JSON.parse(it) : it));
    const got = items.map((it) => linkedinKey[it.linkedinAddress || it.linkedin] || JSON.stringify(it).slice(0, 80)).sort();
    const exp = a ? [] : EXPECTED_VIEWED[r];
    const ok = JSON.stringify(got) === JSON.stringify(exp);
    if (!ok) failures++;
    console.log('visualizados', r, res.status, items.length, ok ? 'OK' : 'DIVERGE', 'obtido', got.join(','), 'esperado', exp.join(','));
  }
  process.exitCode = failures ? 1 : 0;
}
if (cmd === 'raw') { // node ... raw <recrutador|candidato> viewed|viewers [yyyyMM]
  const m = rest[0] || month();
  const who = CAND[a] || recruiterOf(a);
  const uri = b === 'viewers' ? `/resume/${who}/viewers/${m}` : `/recruiter/${who}/viewed-resumes/${m}`;
  const res = await call(8081, 'GET', uri, null, auth(who));
  console.log(res.status, JSON.stringify(res.body, null, 1).slice(0, 4000));
}
if (cmd === 'url') {
  const l = state.links[recruiterOf(a)][b];
  console.log(`http://localhost:3000/recrutador/ver-curriculo?email=${encodeURIComponent(l.email)}&resume=${encodeURIComponent(l.resumeId)}&token=${l.token}`);
}
if (cmd === 'storage') {
  const who = CAND[a] || recruiterOf(a);
  console.log(JSON.stringify({ email: who, sessionToken: state.sessions[who] }));
}
