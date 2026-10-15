// Amostra de currículos para a automação pela tela (roteiro 04): escolhe currículos já carregados de cada tipo e cria
// alguns candidatos novos (e-mail e LinkedIn inventados, para o salvar ser inclusão), abre a sessão de cada um pela API
// jn com o User-Agent do navegador (a sessão só vale para o cliente que a abriu) e grava amostra.json, que a página lê.
//
// Uso: node 07-amostra-para-tela.mjs <curriculos.jsonl> <saída.json> "<User-Agent do Chrome>" [por tipo=12,6,6,6] [novos=6]
import fs from 'fs';
import path from 'path';

const [, , inputFile, outputFile, userAgent, perTypeArg, newOnesArg] = process.argv;
const PER_TYPE = (perTypeArg || '12,6,6,6').split(',').map(Number);
const NEW_ONES = Number(newOnesArg || 6);
const PASSWORD = 'Carga@2026Curriculo';
const TOKEN_TEMPLATE = 'com.jn.business.messages.JnMessages$JnNotifyUserAboutLoginToken.html';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function jn(method, uri, body) {
    const response = await fetch(`http://localhost:8080${uri}`, {
        method, headers: { 'Content-Type': 'application/json', 'User-Agent': userAgent }, body: JSON.stringify(body || {}),
    });
    const text = await response.text();
    let json = {};
    try { json = text ? JSON.parse(text) : {}; } catch { json = { raw: text.slice(0, 300) }; }
    return { status: response.status, body: json };
}

async function readToken(email, since) {
    const file = path.join('c:\\logs\\email', email, TOKEN_TEMPLATE);
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

// loga com a senha da carga; candidato novo faz o cadastro completo do modal
async function openSession(email) {
    const login = await jn('POST', `/login/${email}`, { password: PASSWORD });
    if (login.status === 200 && login.body.sessionToken) return { sessionToken: login.body.sessionToken };
    if (login.status !== 404) return { error: `login ${login.status} ${JSON.stringify(login.body).slice(0, 200)}` };
    const confirm = await jn('POST', `/login/${email}/token`);
    const answers = await jn('POST', `/login/${email}/pre-registration`, { channel: 'telegram', goal: 'recruiting' });
    const since = Date.now();
    const send = await jn('POST', `/login/${email}/token/language/portuguese`);
    const token = await readToken(email, since);
    if (!token) return { error: `token não chegou (${confirm.status}/${answers.status}/${send.status})` };
    const saved = await jn('POST', `/login/${email}/password`, { password: PASSWORD, confirmPassword: PASSWORD, token });
    if (!saved.body.sessionToken) return { error: `senha ${saved.status}` };
    return { sessionToken: saved.body.sessionToken };
}

const lines = fs.readFileSync(inputFile, 'utf8').trim().split('\n').map((line) => JSON.parse(line));
// variedade: região "todas", algumas regiões ou nenhuma; com e sem idiomas; pretensões diferentes
const byType = [1, 2, 3, 4].map((type) => lines.filter((line) => line.resume.resumeType === type));
const sample = [];
byType.forEach((candidates, index) => {
    const wanted = PER_TYPE[index];
    const step = Math.max(1, Math.floor(candidates.length / wanted));
    for (let i = 0; i < wanted && i * step < candidates.length; i++) sample.push({ ...candidates[i * step], kind: 'existente' });
});
const stamp = Date.now();
for (let i = 0; i < NEW_ONES; i++) {
    const candidates = byType[i % 4];
    const model = candidates[(50 + i) % candidates.length];
    const email = `tela.${stamp}.${i}@teste.com`;
    const resume = { ...model.resume, email, linkedinAddress: `https://www.linkedin.com/in/tela-${stamp}-${i}` };
    sample.push({ ...model, id: email, resume, kind: 'novo' });
}

const result = [];
for (const item of sample) {
    const session = await openSession(item.id);
    result.push({ email: item.id, kind: item.kind, resume: item.resume, resumeText: item.resumeText || '', ...session });
    console.log(item.kind, item.resume.resumeType, item.id, session.error || 'sessão ok');
}
fs.writeFileSync(outputFile, JSON.stringify(result));
console.log('sessões', result.filter((r) => r.sessionToken).length, 'de', result.length);
