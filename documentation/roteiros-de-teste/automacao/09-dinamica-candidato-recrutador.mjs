// Dinâmica candidato/recrutador (2026-11-03): sessões dos recrutadores, lista da semana e visualizações pela API do vis.
// Uso (roteiro 09): node 09-dinamica-candidato-recrutador.mjs sessions | links | view <recrutador> <candidato> [apelido] | url <recrutador> <candidato>
// As sessões são abertas em localhost: a sessão vale para o IP e o User-Agent de quem a abriu, e o Chrome chega por ::1.
// O resumeId é sha1(sha1(email)) com sinal; o caminho das APIs leva o e-mail cru (com %40 o vis responde 422).
// O estado (sessões e links assinados) fica em dyn-state.json, na pasta corrente.
import fs from 'fs';
import path from 'path';
import crypto from 'crypto';
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36';
const PASSWORD = 'Roteiro@2026x';
const TOKEN_TEMPLATE = 'com.jn.business.messages.JnMessages$JnNotifyUserAboutLoginToken.html';
const RECRUITERS = ['recrutadora.20261103@gmail.com', 'recrutadorb.20261103@gmail.com', 'recrutador1.20261103@empresa09.com.br',
  'recrutador2.20261103@empresa09.com.br', 'recrutador.20261103@consultoria09.com.br'];
const CANDIDATES = ['roteiro01b', 'roteiro04a', 'roteiro04b', 'roteiro04c', 'roteiro04f', 'roteiro04g'].map((c) => c + '.20261103@teste.com');
const STATE = 'dyn-state.json';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const state = fs.existsSync(STATE) ? JSON.parse(fs.readFileSync(STATE, 'utf8')) : { sessions: {}, links: {} };
const save = () => fs.writeFileSync(STATE, JSON.stringify(state, null, 1));
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
async function session(email) {
  const login = await call(8082, 'POST', `/login/${email}`, { password: PASSWORD });
  if (login.status === 200 && login.body.sessionToken) return login.body.sessionToken;
  if (login.status !== 404) return '';
  await call(8082, 'POST', `/login/${email}/token`);
  await call(8082, 'POST', `/login/${email}/pre-registration`, { channel: 'telegram', goal: 'recruiting' });
  const since = Date.now();
  await call(8082, 'POST', `/login/${email}/token/language/portuguese`);
  const token = await readToken(email, since);
  const saved = await call(8082, 'POST', `/login/${email}/password`, { password: PASSWORD, confirmPassword: PASSWORD, token });
  return saved.body.sessionToken || '';
}
const [, , cmd, a, b, alias] = process.argv;
if (cmd === 'sessions') {
  for (const r of RECRUITERS) { if (!state.sessions[r]) state.sessions[r] = await session(r); console.log(r, state.sessions[r] ? 'ok' : 'FALHOU'); save(); }
}
if (cmd === 'links') {
  await sleep(3000);
  for (const r of RECRUITERS) {
    const res = await call(8081, 'GET', `/recruiter/${r}/resumes-of-the-week`, null, { sessionToken: state.sessions[r], email: r });
    const list = Array.isArray(res.body) ? res.body : (res.body.resumes || res.body.list || Object.values(res.body).find(Array.isArray) || []);
    state.links[r] = {};
    for (const c of CANDIDATES) { const row = list.find((x) => x.resumeId === hashOf(hashOf(c))); if (row) state.links[r][c] = { email: r, resume: row.resumeId, token: row.token }; }
    console.log(r, res.status, 'lista', list.length, 'candidatos de teste', Object.keys(state.links[r]).length, Object.keys(res.body).slice(0, 5).join(','));
  }
  save();
}
if (cmd === 'view') {
  const l0 = state.links[a][b]; const link = { email: l0.email, resumeId: l0.resume, token: l0.token };
  const v = await call(8081, 'POST', '/recruiter-email-link/view-resume', link);
  console.log('view', a, b, v.status, JSON.stringify(v.body).slice(0, 200));
  if (alias) { const s = await call(8081, 'POST', '/recruiter-email-link/alias', { ...link, alias }); console.log('alias', s.status, JSON.stringify(s.body).slice(0, 150)); }
}
if (cmd === 'url') {
  const l = state.links[a][b];
  console.log(`http://localhost:3000/recrutador/ver-curriculo?email=${encodeURIComponent(l.email)}&resume=${encodeURIComponent(l.resume)}&token=${l.token}`);
}
