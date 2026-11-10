// Roteiro 13 (2026-11-09): contagem do "Quem me viu" do ponto de vista do candidato, por tipo de recrutador:
// freelancers (domínios do NONPROFESSIONALDOMAINS, todos sob a chave "freelancer"), recrutadores do mesmo domínio e de
// domínio diferente. Cada recrutador conta 1 vez por mês para cada candidato.
//
// Uso (pasta corrente = automacao; o estado fica em q13-state.json):
//   node 13-quem-me-viu-por-tipo-de-recrutador.mjs candidates   cadastra os 3 candidatos e salva o currículo de cada um
//   node 13-quem-me-viu-por-tipo-de-recrutador.mjs sessions     abre a sessão dos 6 recrutadores (cadastro pelo token do e-mail mock)
//   (rodar SendResumesToRecruiters.java com os 6 recrutadores, ver o roteiro)
//   node 13-quem-me-viu-por-tipo-de-recrutador.mjs links        guarda os links assinados de cada recrutador para cada candidato
//   node 13-quem-me-viu-por-tipo-de-recrutador.mjs views        executa a matriz (inclusive as visualizações repetidas)
//   node 13-quem-me-viu-por-tipo-de-recrutador.mjs check        lê GET /resume/{email}/viewers/{yyyyMM} de cada candidato e compara com o esperado
//   node 13-quem-me-viu-por-tipo-de-recrutador.mjs url <recrutador> <candidato>   link para abrir no Chrome
// Variável D (opcional): sufixo de data das contas, padrão 20261109.
import fs from 'fs';
import path from 'path';
import crypto from 'crypto';

const D = process.env.D || '20261109';
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36';
const PASSWORD = 'Roteiro@2026x';
const TOKEN_TEMPLATE = 'com.jn.business.messages.JnMessages$JnNotifyUserAboutLoginToken.html';
const FREELANCERS = [`rec13free1.${D}@gmail.com`, `rec13free2.${D}@hotmail.com`, `rec13free3.${D}@yahoo.com.br`];
const SAME_DOMAIN = [`rec13a.${D}@empresa13.com.br`, `rec13b.${D}@empresa13.com.br`];
const OTHER_DOMAIN = [`rec13c.${D}@outra13.com.br`];
const RECRUITERS = [...FREELANCERS, ...SAME_DOMAIN, ...OTHER_DOMAIN];
const CAND = { A: `cand13a.${D}@teste.com`, B: `cand13b.${D}@teste.com`, C: `cand13c.${D}@teste.com` };
const [F1, F2, F3] = FREELANCERS;
const [S1, S2] = SAME_DOMAIN;
const [O1] = OTHER_DOMAIN;
// Matriz: [recrutador, candidato]. Repetições de propósito (não podem contar de novo no mesmo mês).
const VIEWS = [
  [F1, 'A'], [F2, 'A'], [S1, 'A'], [S2, 'A'], [O1, 'A'], [F1, 'A'], [S1, 'A'],
  [F1, 'B'], [F2, 'B'], [F3, 'B'], [S1, 'B'], [F3, 'B'],
  [F3, 'C'], [S1, 'C'], [S2, 'C'], [O1, 'C'], [O1, 'C'], [S2, 'C'],
];
// Esperado em Quem me viu (mês corrente): domínio -> visualizações
const EXPECTED = {
  A: { freelancer: 2, 'empresa13.com.br': 2, 'outra13.com.br': 1 },
  B: { freelancer: 3, 'empresa13.com.br': 1 },
  C: { freelancer: 1, 'empresa13.com.br': 2, 'outra13.com.br': 1 },
};
const RESUME = (key) => ({
  ddd: [11], desiredJob: `Programador Java roteiro 13 ${key}`, disponibility: 5, experience: 4, resumeType: 2, temporallyJobTime: 0, pj: 9000,
  linkedinAddress: `https://www.linkedin.com/in/cand13${key.toLowerCase()}${D}`,
  resumeText: 'Desenvolvedor Java com Spring Boot, Elasticsearch, Docker, Kubernetes, SQL, Git, React e TypeScript.',
});
const STATE = 'q13-state.json';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const state = fs.existsSync(STATE) ? JSON.parse(fs.readFileSync(STATE, 'utf8')) : { sessions: {}, links: {} };
const save = () => fs.writeFileSync(STATE, JSON.stringify(state, null, 1));
const month = () => { const n = new Date(); return `${n.getFullYear()}${String(n.getMonth() + 1).padStart(2, '0')}`; };

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
  if (login.status === 200 && login.body.sessionToken) return login.body.sessionToken;
  if (login.status !== 404) { console.log('  login', email, login.status, JSON.stringify(login.body).slice(0, 150)); return ''; }
  await call(8082, 'POST', `/login/${email}/token`);
  await call(8082, 'POST', `/login/${email}/pre-registration`, { channel: 'telegram', goal });
  const since = Date.now();
  await call(8082, 'POST', `/login/${email}/token/language/portuguese`);
  const token = await readToken(email, since);
  const saved = await call(8082, 'POST', `/login/${email}/password`, { password: PASSWORD, confirmPassword: PASSWORD, token });
  await sleep(2500); // a sessão nasce por escrita assíncrona
  if (saved.status !== 200) { console.log('  password', email, saved.status, JSON.stringify(saved.body).slice(0, 150)); return ''; }
  return saved.body.sessionToken || '';
}
const auth = (email) => ({ sessionToken: state.sessions[email], email });
const [, , cmd, a, b] = process.argv;

if (cmd === 'candidates') {
  for (const [key, email] of Object.entries(CAND)) {
    if (!state.sessions[email]) state.sessions[email] = await session(email, 'jobs'); // goal aceito: jobs | recruiting (jobSearch dá 422)
    const saved = await call(8081, 'POST', `/resume/${email}/language/portuguese`, RESUME(key), auth(email));
    console.log(key, email, 'sessão', state.sessions[email] ? 'ok' : 'FALHOU', 'save', saved.status, JSON.stringify(saved.body).slice(0, 200));
    save();
  }
}
if (cmd === 'sessions') {
  for (const r of RECRUITERS) { if (!state.sessions[r]) state.sessions[r] = await session(r, 'recruiting'); console.log(r, state.sessions[r] ? 'ok' : 'FALHOU'); save(); }
}
if (cmd === 'links') {
  for (const r of RECRUITERS) {
    const res = await call(8081, 'GET', `/recruiter/${r}/resumes-of-the-week`, null, auth(r));
    const list = Array.isArray(res.body) ? res.body : (res.body.resumes || res.body.list || Object.values(res.body).find(Array.isArray) || []);
    state.links[r] = {};
    for (const [key, c] of Object.entries(CAND)) { const row = list.find((x) => x.resumeId === hashOf(hashOf(c))); if (row) state.links[r][key] = { email: r, resumeId: row.resumeId, token: row.token }; }
    console.log(r, res.status, 'lista', list.length, 'candidatos do roteiro', Object.keys(state.links[r]).join(',') || 'NENHUM');
  }
  save();
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
if (cmd === 'check') {
  let failures = 0;
  for (const [key, email] of Object.entries(CAND)) {
    const res = await call(8081, 'GET', `/resume/${email}/viewers/${month()}`, null, auth(email));
    const got = {};
    for (const v of res.body.viewers || []) got[v.domain] = v.views;
    const exp = EXPECTED[key];
    const ok = JSON.stringify(Object.entries(got).sort()) === JSON.stringify(Object.entries(exp).sort());
    if (!ok) failures++;
    console.log(key, email, res.status, ok ? 'OK' : 'DIVERGE', 'obtido', JSON.stringify(got), 'esperado', JSON.stringify(exp));
  }
  process.exitCode = failures ? 1 : 0;
}
if (cmd === 'url') {
  const l = state.links[a][b];
  console.log(`http://localhost:3000/recrutador/ver-curriculo?email=${encodeURIComponent(l.email)}&resume=${encodeURIComponent(l.resumeId)}&token=${l.token}`);
}
