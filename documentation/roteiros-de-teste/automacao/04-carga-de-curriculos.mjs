// Carga de currículos pelo endpoint de salvamento (POST /resume/{email}/language/portuguese na API vis 8081), com
// sessão válida de cada candidato: cadastra (ou loga) o candidato pela API jn 8080, como o modal de login faz, e salva
// o currículo montado pelo formulário simulado. Grava um resultado por currículo e um arquivo só com as falhas.
//
// Uso: node 04-carga-de-curriculos.mjs <curriculos.jsonl> <pasta de saída> [trabalhadores=8] [reservados.txt]
//   curriculos.jsonl: uma linha por currículo, {"id": e-mail, "resume": json do formulário} (saída do prep.js)
//   reservados.txt: e-mails que ficam para a automação pelas telas (um por linha), pulados aqui
//
// O token de login é lido de c:\logs\email\<e-mail>\<template>.html: a implementação local de e-mail grava uma cópia
// por destinatário (desde 2026-10-12), então vários cadastros em paralelo não leem o token um do outro.
import fs from 'fs';
import http from 'http';
import path from 'path';

const [, , inputFile, outputDir, workersArg, reservedFile] = process.argv;
const WORKERS = Number(workersArg || 8);
const PASSWORD = 'Carga@2026Curriculo';
const TOKEN_TEMPLATE = 'com.jn.business.messages.JnMessages$JnNotifyUserAboutLoginToken.html';
const JN = { host: 'localhost', port: 8080 };
const VIS = { host: 'localhost', port: 8081 };

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function request(server, method, uri, body, extraHeaders = {}) {
    const data = body === undefined ? '{}' : JSON.stringify(body);
    const definedExtraHeaders = Object.fromEntries(Object.entries(extraHeaders).filter(([, value]) => value));
    const headers = { 'Content-Type': 'application/json', 'User-Agent': 'roteiro-04-carga', 'Content-Length': Buffer.byteLength(data), ...definedExtraHeaders };
    const started = Date.now();
    return new Promise((resolve) => {
        const req = http.request({ ...server, method, path: encodeURI(uri), headers, timeout: 600000 }, (res) => {
            let text = '';
            res.setEncoding('utf8');
            res.on('data', (chunk) => (text += chunk));
            res.on('end', () => {
                let json = {};
                try { json = text ? JSON.parse(text) : {}; } catch { json = { raw: text.slice(0, 500) }; }
                resolve({ status: res.statusCode, body: json, ms: Date.now() - started });
            });
        });
        req.on('timeout', () => req.destroy(new Error('timeout')));
        req.on('error', (e) => resolve({ status: 0, body: { error: String(e) }, ms: Date.now() - started }));
        req.write(data);
        req.end();
    });
}

const ok = (r) => r.status >= 200 && r.status < 300;

async function readToken(email, since) {
    const file = path.join('c:\\logs\\email', email, TOKEN_TEMPLATE);
    for (let i = 0; i < 80; i++) {
        try {
            const stat = fs.statSync(file);
            if (stat.mtimeMs >= since - 50) {
                const match = fs.readFileSync(file, 'utf8').match(/esse token é ([A-Z0-9]{8})/);
                if (match) return match[1];
            }
        } catch {}
        await sleep(250);
    }
    return '';
}

// loga com a senha da carga; se o candidato ainda não existe, faz o cadastro completo do modal
async function getSession(email) {
    const login = await request(JN, 'POST', `/login/${email}`, { password: PASSWORD });
    if (ok(login) && login.body.sessionToken) return { sessionToken: login.body.sessionToken };

    const confirm = await request(JN, 'POST', `/login/${email}/token`);
    if (!ok(confirm)) return { step: 'confirmar e-mail', response: confirm };
    const answers = await request(JN, 'POST', `/login/${email}/pre-registration`, { channel: 'telegram', goal: 'recruiting' });
    if (!ok(answers)) return { step: 'pré-cadastro', response: answers };
    const since = Date.now();
    const send = await request(JN, 'POST', `/login/${email}/token/language/portuguese`);
    if (!ok(send)) return { step: 'envio do token', response: send };
    const token = await readToken(email, since);
    if (!token) return { step: 'leitura do token', response: { status: 0, body: { error: 'o e-mail do token não chegou' } } };
    const saved = await request(JN, 'POST', `/login/${email}/password`, { password: PASSWORD, confirmPassword: PASSWORD, token });
    if (!ok(saved) || !saved.body.sessionToken) return { step: 'senha', response: saved };
    return { sessionToken: saved.body.sessionToken };
}

async function main() {
    fs.mkdirSync(outputDir, { recursive: true });
    const reserved = new Set(reservedFile ? fs.readFileSync(reservedFile, 'utf8').split(/\r?\n/).filter(Boolean) : []);
    const entries = fs.readFileSync(inputFile, 'utf8').split('\n').filter((l) => l.trim()).map((l) => JSON.parse(l)).filter((e) => !reserved.has(e.id));
    const resultsStream = fs.createWriteStream(path.join(outputDir, 'resultados.jsonl'), { flags: 'a' });
    const failuresStream = fs.createWriteStream(path.join(outputDir, 'falhas.jsonl'), { flags: 'a' });
    let next = 0, done = 0, saved = 0, failed = 0;
    const started = Date.now();

    async function worker() {
        while (next < entries.length) {
            const entry = entries[next++];
            const email = entry.id;
            const t0 = Date.now();
            let result;
            const session = await getSession(email);
            if (!session.sessionToken) {
                result = { email, ok: false, step: session.step, status: session.response.status, body: session.response.body };
            } else {
                const save = await request(VIS, 'POST', `/resume/${email}/language/portuguese`, entry.resume, { sessionToken: session.sessionToken, email });
                result = ok(save) ? { email, ok: true, status: save.status, saveMs: save.ms } : { email, ok: false, step: 'salvar currículo', status: save.status, body: save.body };
            }
            result.ms = Date.now() - t0;
            resultsStream.write(JSON.stringify(result) + '\n');
            if (result.ok) saved++; else { failed++; failuresStream.write(JSON.stringify(result) + '\n'); }
            done++;
            if (done % 25 === 0 || done === entries.length) {
                const seconds = (Date.now() - started) / 1000;
                console.log(`${done}/${entries.length} | salvos ${saved} | falhas ${failed} | ${(done / seconds).toFixed(2)} por segundo`);
            }
        }
    }
    await Promise.all(Array.from({ length: WORKERS }, () => worker()));
    resultsStream.end();
    failuresStream.end();
    console.log(JSON.stringify({ total: entries.length, saved, failed, seconds: Math.round((Date.now() - started) / 1000) }));
}

main();
