// Automação do roteiro 03 (modal de login) contra a API jn local, com vários usuários intercalados.
//
// Faz pela API exatamente as chamadas que o modal faz, alternando três candidatos (A, B e C) a cada passo, para
// provar que tentativas, bloqueios, tokens e sessões de um não vazam para o outro. O papel do operador do suporte
// (/solveLoginTokenTicket) é feito pelo SupportBotCommand.java, sem Telegram.
//
// Pré-requisitos: ES 9200, API jn 8080 (reiniciada depois de recriar os índices) e um executaCcpCreateEntities.bat
// já rodado (ele gera ccp_rest-api-tests_jobsnow/target/create-entities-args.txt, o classpath do SupportBotCommand).
//
// Uso: node documentation/roteiros-de-teste/automacao/03-modal-de-login.mjs
// Sai com código 1 se alguma verificação falhar. Cada execução usa e-mails novos, então não precisa recriar índices
// entre uma execução e outra.

import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const API = { host: 'localhost', port: Number(process.env.JN_PORT || 8080) };
const MAX_ATTEMPTS = 3;
const TOKEN_EMAIL_FILE = 'C:\\logs\\email\\com.jn.business.messages.JnMessages$JnNotifyUserAboutLoginToken.html';
const SUPPORT_CHAT_FILE = 'C:\\logs\\telegram\\support-751717896.txt';
const HERE = path.dirname(fileURLToPath(import.meta.url));
const WORKSPACE = path.resolve(HERE, '..', '..', '..');
const TESTS_PROJECT = path.join(WORKSPACE, 'ccp_rest-api-tests_jobsnow');
const JAVA = 'C:\\Program Files\\Java\\jdk-17\\bin\\java.exe';

const stamp = Date.now().toString(36);
const users = {
    A: { email: `login.a.${stamp}@teste.com`, password: 'Roteiro@2026A' },
    B: { email: `login.b.${stamp}@teste.com`, password: 'Roteiro@2026B' },
    C: { email: `login.c.${stamp}@teste.com`, password: 'Roteiro@2026C' },
};

const results = [];
let currentSection = '';

function section(title) {
    currentSection = title;
    console.log(`\n=== ${title}`);
}

function check(label, ok, detail = '') {
    results.push({ section: currentSection, label, ok, detail });
    console.log(`${ok ? '  ok  ' : '  FALHA'} ${label}${ok || !detail ? '' : `  -> ${detail}`}`);
    return ok;
}

function request(method, uri, body, extraHeaders = {}) {
    const data = body === undefined ? '{}' : JSON.stringify(body);
    const definedExtraHeaders = Object.fromEntries(Object.entries(extraHeaders).filter(([, value]) => value));
    const headers = { 'Content-Type': 'application/json', 'User-Agent': 'roteiro-03-automacao', 'Content-Length': Buffer.byteLength(data), ...definedExtraHeaders };
    const started = Date.now();
    return new Promise((resolve, reject) => {
        const req = http.request({ ...API, method, path: encodeURI(uri), headers }, (res) => {
            let text = '';
            res.setEncoding('utf8');
            res.on('data', (chunk) => (text += chunk));
            res.on('end', () => {
                let json = {};
                try { json = text ? JSON.parse(text) : {}; } catch { json = { raw: text }; }
                resolve({ status: res.statusCode, body: json, ms: Date.now() - started });
            });
        });
        req.on('error', reject);
        req.write(data);
        req.end();
    });
}

// As chamadas do modal (ServerRequests.ts), uma por tela.
const api = {
    checkEmail: (u) => request('HEAD', `/login/${u.email}/token`),
    confirmEmail: (u) => request('POST', `/login/${u.email}/token`),
    answers: (u) => request('POST', `/login/${u.email}/pre-registration`, { channel: 'telegram', goal: 'recruiting' }),
    sendToken: (u) => request('POST', `/login/${u.email}/token/language/portuguese`),
    savePassword: (u, password, token) => request('POST', `/login/${u.email}/password`, { password, confirmPassword: password, token }),
    login: (u, password) => request('POST', `/login/${u.email}`, { password }),
    logout: (u, sessionToken = u.sessionToken) => request('DELETE', `/login/${u.email}/${sessionToken}`, {}, { sessionToken, email: u.email }),
    validateSession: (u, sessionToken) => request('GET', `/login/${u.email}/${sessionToken}`, {}, { sessionToken, email: u.email }),
    requestUnlock: (u) => request('POST', `/login/${u.email}/token/request/unlocking`),
    requestResend: (u) => request('POST', `/login/${u.email}/token/request/resending`),
};

function expectStatus(label, response, expected, extra = () => true, extraDetail = '') {
    const statusOk = response.status === expected;
    const extraOk = statusOk && extra(response.body);
    const detail = `esperado ${expected}${extraDetail ? ` com ${extraDetail}` : ''}, veio ${response.status} ${JSON.stringify(response.body).slice(0, 300)}`;
    return check(`${label} → ${expected} (${response.ms} ms)`, statusOk && extraOk, detail);
}

const attemptsIs = (n) => (body) => Number(body.attempts) === n;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// O arquivo do e-mail é um só para todos os destinatários e é sobrescrito a cada envio: só serve o que foi gravado
// depois do pedido e que menciona o e-mail esperado.
async function readTokenSentTo(u, since) {
    for (let i = 0; i < 60; i++) {
        try {
            const stat = fs.statSync(TOKEN_EMAIL_FILE);
            if (stat.mtimeMs >= since - 50) {
                const html = fs.readFileSync(TOKEN_EMAIL_FILE, 'utf8');
                const match = html.match(/esse token é ([A-Z0-9]{8})/);
                if (html.includes(u.email) && match) {
                    return match[1];
                }
            }
        } catch {}
        await sleep(250);
    }
    return '';
}

function supportChatSince(size) {
    try {
        const buffer = fs.readFileSync(SUPPORT_CHAT_FILE);
        return buffer.subarray(size).toString('utf8');
    } catch {
        return '';
    }
}

function supportChatSize() {
    try { return fs.statSync(SUPPORT_CHAT_FILE).size; } catch { return 0; }
}

function runSupportBotCommand(command) {
    const result = spawnSync(JAVA, ['@target/create-entities-args.txt', path.join(HERE, 'SupportBotCommand.java'), ...command.split(' ')], {
        cwd: TESTS_PROJECT,
        encoding: 'utf8',
        timeout: 180000,
    });
    const ok = result.status === 0 && result.stdout.includes('OK ');
    if (!ok) {
        console.log(result.stdout.slice(-2000), result.stderr.slice(-3000));
    }
    return ok;
}

async function firstAccess(u, name) {
    expectStatus(`${name}: verificação do e-mail novo`, await api.checkEmail(u), 404);
}

async function main() {
    console.log(`API jn em ${API.host}:${API.port} — candidatos:`);
    for (const [name, u] of Object.entries(users)) console.log(`  ${name} = ${u.email}`);

    section('L1 — primeiro acesso dos três, intercalado');
    for (const name of ['A', 'B', 'C']) await firstAccess(users[name], name);
    for (const name of ['B', 'C', 'A']) expectStatus(`${name}: confirmação do e-mail (cadastra e pede as preferências)`, await api.confirmEmail(users[name]), 201);
    for (const name of ['C', 'A', 'B']) expectStatus(`${name}: verificação do e-mail sem preferências`, await api.checkEmail(users[name]), 201);
    for (const name of ['A', 'C', 'B']) expectStatus(`${name}: preferências (pede a senha)`, await api.answers(users[name]), 202);
    for (const name of ['B', 'A', 'C']) expectStatus(`${name}: verificação do e-mail sem senha`, await api.checkEmail(users[name]), 202);

    for (const name of ['A', 'B', 'C']) {
        const u = users[name];
        const since = Date.now();
        expectStatus(`${name}: envio do token`, await api.sendToken(u), 200);
        u.token = await readTokenSentTo(u, since);
        check(`${name}: token chegou no e-mail de ${name}`, !!u.token, 'o arquivo do e-mail não ganhou um token para este destinatário');
    }
    check('os três tokens são diferentes', new Set([users.A.token, users.B.token, users.C.token]).size === 3, JSON.stringify([users.A.token, users.B.token, users.C.token]));
    expectStatus('A: segundo envio do token (já enviado)', await api.sendToken(users.A), 429, (b) => !!b.expirationDate, 'expirationDate');

    section('L1/L7 — token errado intercalado: A bloqueia na 3ª, B acerta na 2ª, C acerta de primeira');
    const { A, B, C } = users;
    expectStatus('A: token errado nº 1', await api.savePassword(A, A.password, 'ZZZZZZZ1'), 427, attemptsIs(1), 'attempts=1');
    expectStatus('B: token errado nº 1 (contador do B começa do zero)', await api.savePassword(B, B.password, 'ZZZZZZZ1'), 427, attemptsIs(1), 'attempts=1');
    expectStatus('A: token errado nº 2', await api.savePassword(A, A.password, 'ZZZZZZZ2'), 427, attemptsIs(2), 'attempts=2');
    // o token de outro candidato também é token errado
    expectStatus('B: token do A (errado para o B) nº 2', await api.savePassword(B, B.password, A.token), 427, attemptsIs(2), 'attempts=2');
    const savedB = await api.savePassword(B, B.password, B.token);
    expectStatus('B: token certo na 3ª chance (cria a senha e loga)', savedB, 200, (b) => !!b.sessionToken, 'sessionToken');
    B.sessionToken = savedB.body.sessionToken;
    expectStatus('A: token errado nº 3 (bloqueia o token)', await api.savePassword(A, A.password, 'ZZZZZZZ3'), 429);
    expectStatus('A: token CERTO depois do bloqueio continua recusado', await api.savePassword(A, A.password, A.token), 403);
    expectStatus('A: verificação do e-mail com o token bloqueado', await api.checkEmail(A), 403);
    expectStatus('A: login com o token bloqueado', await api.login(A, A.password), 403);
    expectStatus('B: verificação do e-mail não foi afetada pelo bloqueio do A', await api.checkEmail(B), 409);
    const savedC = await api.savePassword(C, C.password, C.token);
    expectStatus('C: token certo de primeira', savedC, 200, (b) => !!b.sessionToken, 'sessionToken');
    C.sessionToken = savedC.body.sessionToken;
    expectStatus('B: sessão válida', await api.validateSession(B, B.sessionToken), 200);
    expectStatus('C: sessão válida', await api.validateSession(C, C.sessionToken), 200);

    section('L3 — sair do sistema (B e C)');
    expectStatus('B: sair', await api.logout(B), 200);
    expectStatus('C: sair', await api.logout(C), 200);
    expectStatus('B: sair de novo (já saiu)', await api.logout(B), 404);
    expectStatus('B: verificação do e-mail de quem já tem senha', await api.checkEmail(B), 200);

    section('L4 — senha errada intercalada: B bloqueia na 3ª, C acerta na 2ª');
    expectStatus('B: senha errada nº 1', await api.login(B, 'Errada@111'), 427, attemptsIs(1), 'attempts=1');
    expectStatus('C: senha errada nº 1 (contador do C começa do zero)', await api.login(C, 'Errada@111'), 427, attemptsIs(1), 'attempts=1');
    expectStatus('B: senha errada nº 2', await api.login(B, 'Errada@222'), 427, attemptsIs(2), 'attempts=2');
    // a senha de outro candidato também é senha errada
    expectStatus('C: senha do B (errada para o C) nº 2', await api.login(C, B.password), 427, attemptsIs(2), 'attempts=2');
    const loginC = await api.login(C, C.password);
    expectStatus('C: senha certa na 3ª chance', loginC, 200, (b) => !!b.sessionToken, 'sessionToken');
    C.sessionToken = loginC.body.sessionToken;
    expectStatus('B: senha errada nº 3 (bloqueia a senha)', await api.login(B, 'Errada@333'), 429);
    expectStatus('B: senha CERTA depois do bloqueio continua recusada', await api.login(B, B.password), 423);
    // senha bloqueada é 423 em todo endpoint desde 2026-10-15 (até então a verificação do e-mail respondia 427)
    expectStatus('B: verificação do e-mail com a senha bloqueada', await api.checkEmail(B), 423);
    expectStatus('C: sair', await api.logout(C), 200);
    expectStatus('C: senha errada depois do acerto conta do zero de novo', await api.login(C, 'Errada@444'), 427, attemptsIs(1), 'attempts=1');
    const loginC2 = await api.login(C, C.password);
    expectStatus('C: senha certa', loginC2, 200);
    C.sessionToken = loginC2.body.sessionToken;

    section('L4 — B desbloqueia a senha com o token e entra com a senha nova');
    const oldPasswordB = B.password;
    B.password = 'Roteiro@2027B';
    const unlockedB = await api.savePassword(B, B.password, B.token);
    expectStatus('B: senha nova + token (desbloqueia e loga)', unlockedB, 200);
    B.sessionToken = unlockedB.body.sessionToken;
    expectStatus('B: sair', await api.logout(B), 200);
    expectStatus('B: senha antiga não vale mais (conta do zero: o desbloqueio zerou as tentativas)', await api.login(B, oldPasswordB), 427, attemptsIs(1), 'attempts=1');
    const loginB = await api.login(B, B.password);
    expectStatus('B: senha nova', loginB, 200);
    B.sessionToken = loginB.body.sessionToken;

    section('Pedidos simultâneos de candidatos diferentes');
    expectStatus('B: sair', await api.logout(B), 200);
    expectStatus('C: sair', await api.logout(C), 200);
    const [wrongB, wrongC] = await Promise.all([api.login(B, 'Errada@555'), api.login(C, 'Errada@555')]);
    expectStatus('B: senha errada (simultânea com o C)', wrongB, 427, attemptsIs(1), 'attempts=1');
    expectStatus('C: senha errada (simultânea com o B)', wrongC, 427, attemptsIs(1), 'attempts=1');
    const [rightB, rightC] = await Promise.all([api.login(B, B.password), api.login(C, C.password)]);
    expectStatus('B: senha certa (simultânea com o C)', rightB, 200);
    expectStatus('C: senha certa (simultânea com o B)', rightC, 200);
    B.sessionToken = rightB.body.sessionToken;
    C.sessionToken = rightC.body.sessionToken;
    check('as sessões de B e C são diferentes', B.sessionToken && C.sessionToken && B.sessionToken !== C.sessionToken, `${B.sessionToken} x ${C.sessionToken}`);
    expectStatus('B: sessão do C não vale para o B', await api.validateSession(B, C.sessionToken), 401);

    section('L7 — desbloqueio do token do A pelo suporte (B pede junto e recebe "não está bloqueado")');
    expectStatus('A: pedir desbloqueio', await api.requestUnlock(A), 200);
    expectStatus('B: pedir desbloqueio de um token que não está bloqueado', await api.requestUnlock(B), 404);
    expectStatus('A: pedir desbloqueio de novo (já pedido)', await api.requestUnlock(A), 409, (b) => !!b.expirationDate, 'expirationDate');
    const chatSize = supportChatSize();
    const sinceUnlock = Date.now();
    check('operador: /solveLoginTokenTicket unlockToken A', runSupportBotCommand(`/solveLoginTokenTicket unlockToken ${A.email}`), 'o SupportBotCommand falhou');
    const chatUnlock = supportChatSince(chatSize);
    const newTokenA = await readTokenSentTo(A, sinceUnlock);
    check('A: token novo chegou por e-mail', !!newTokenA && newTokenA !== A.token, `novo=${newTokenA} antigo=${A.token}`);
    check('o bot respondeu ao operador com o mesmo token', !!newTokenA && chatUnlock.includes(newTokenA), chatUnlock.slice(-400));
    expectStatus('A: pedir desbloqueio depois de resolvido (o token não está mais bloqueado)', await api.requestUnlock(A), 404);
    expectStatus('A: verificação do e-mail com o token desbloqueado', await api.checkEmail(A), 202);
    expectStatus('A: token antigo depois do desbloqueio (tentativas zeradas)', await api.savePassword(A, A.password, A.token), 427, attemptsIs(1), 'attempts=1');
    A.token = newTokenA;
    const savedA = await api.savePassword(A, A.password, A.token);
    expectStatus('A: token novo cria a senha e loga', savedA, 200);
    A.sessionToken = savedA.body.sessionToken;
    expectStatus('A: sessão válida', await api.validateSession(A, A.sessionToken), 200);

    section('L7 — um desbloqueio por dia: o A bloqueia o token de novo e o segundo pedido no mesmo dia é recusado');
    expectStatus('A: token errado nº 1 (depois do desbloqueio)', await api.savePassword(A, A.password, 'YYYYYYY1'), 427, attemptsIs(1), 'attempts=1');
    expectStatus('B: token errado nº 1 no meio (não interfere no A)', await api.savePassword(B, B.password, 'YYYYYYY1'), 427, attemptsIs(1), 'attempts=1');
    expectStatus('A: token errado nº 2', await api.savePassword(A, A.password, 'YYYYYYY2'), 427, attemptsIs(2), 'attempts=2');
    expectStatus('A: token errado nº 3 (bloqueia de novo)', await api.savePassword(A, A.password, 'YYYYYYY3'), 429);
    expectStatus('A: pedir desbloqueio pela 2ª vez no mesmo dia', await api.requestUnlock(A), 429, (b) => !!b.expirationDate, 'expirationDate');
    expectStatus('A: com o token bloqueado nem a senha certa entra', await api.login(A, A.password), 403);
    const savedB2 = await api.savePassword(B, B.password, B.token);
    expectStatus('B: token certo (a tentativa errada do B no meio é zerada)', savedB2, 200);
    B.sessionToken = savedB2.body.sessionToken;

    section('L8 — reenvio do token do C pelo suporte');
    expectStatus('C: pedir reenvio', await api.requestResend(C), 200);
    expectStatus('C: pedir reenvio de novo (já pedido)', await api.requestResend(C), 409);
    const sinceResend = Date.now();
    check('operador: /solveLoginTokenTicket resendToken C', runSupportBotCommand(`/solveLoginTokenTicket resendToken ${C.email}`), 'o SupportBotCommand falhou');
    const newTokenC = await readTokenSentTo(C, sinceResend);
    check('C: token novo chegou por e-mail', !!newTokenC && newTokenC !== C.token, `novo=${newTokenC} antigo=${C.token}`);
    expectStatus('C: pedir reenvio depois de resolvido', await api.requestResend(C), 429);
    expectStatus('C: token anterior deixou de valer', await api.savePassword(C, C.password, C.token), 427, attemptsIs(1), 'attempts=1');
    C.token = newTokenC;
    const savedC2 = await api.savePassword(C, C.password, C.token);
    expectStatus('C: token reenviado vale', savedC2, 200);
    const sessionBeforeResendC = C.sessionToken;
    C.sessionToken = savedC2.body.sessionToken;

    section('L5 — login concorrente');
    // a sessão aberta do C veio de uma gravação de senha (L8)
    expectStatus('C: login com outra sessão aberta, criada pela gravação da senha', await api.login(C, C.password), 409);
    for (const sessionToken of [sessionBeforeResendC, C.sessionToken]) await api.logout(C, sessionToken);
    const firstLoginC = await api.login(C, C.password);
    expectStatus('C: login sem sessão aberta', firstLoginC, 200);
    const firstSessionC = firstLoginC.body.sessionToken;
    expectStatus('A: login no meio (o token do A segue bloqueado)', await api.login(A, A.password), 403);
    expectStatus('C: login com outra sessão aberta, criada por login com senha ("Desbloqueie seu login")', await api.login(C, C.password), 409);
    const conflictC = await api.savePassword(C, C.password, C.token);
    expectStatus('C: desfazer o outro login (senha + confirmação + token)', conflictC, 200);
    C.sessionToken = conflictC.body.sessionToken;
    expectStatus('C: sessão nova válida', await api.validateSession(C, C.sessionToken), 200);
    expectStatus('C: login logo depois de desfazer o outro login (a sessão nova é o login corrente)', await api.login(C, C.password), 409);

    section('Sessões antigas (bug 3)');
    expectStatus('C: a sessão que foi "desfeita" deixou de valer', await api.validateSession(C, firstSessionC), 401);
    for (let i = 2; i <= MAX_ATTEMPTS + 1; i++) await api.validateSession(C, firstSessionC);
    expectStatus(`C: usar a sessão derrubada ${MAX_ATTEMPTS + 1} vezes não bloqueia a senha (segue como login corrente)`, await api.checkEmail(C), 409);
    expectStatus('C: sair pela sessão derrubada responde "não está logado"', await api.logout(C, firstSessionC), 404);
    expectStatus('C: ... e não derruba a sessão corrente', await api.validateSession(C, C.sessionToken), 200);
    const sessionBeforePasswordChangeC = C.sessionToken;
    C.password = 'Roteiro@2027C';
    const changedC = await api.savePassword(C, C.password, C.token);
    expectStatus('C: trocar a senha estando logado', changedC, 200);
    C.sessionToken = changedC.body.sessionToken;
    expectStatus('C: a troca de senha derrubou a sessão anterior', await api.validateSession(C, sessionBeforePasswordChangeC), 401);
    expectStatus('C: a sessão aberta pela troca de senha vale', await api.validateSession(C, C.sessionToken), 200);
    expectStatus('C: sair pela sessão corrente', await api.logout(C), 200);
    const newLoginC = await api.login(C, C.password);
    expectStatus('C: sem sessão corrente, login com a senha nova entra', newLoginC, 200);
    C.sessionToken = newLoginC.body.sessionToken;
    expectStatus('A: sessão do A continua válida (não é afetada pelo C)', await api.validateSession(A, A.sessionToken), 200);
    expectStatus('B: sessão do B continua válida (não é afetada pelo C)', await api.validateSession(B, B.sessionToken), 200);

    section('L10 — sessão vinda de outro navegador e login recusado sem sessionToken (desde 2026-10-15)');
    const otherClient = { 'User-Agent': 'outro-navegador' };
    for (let i = 1; i <= MAX_ATTEMPTS + 1; i++) {
        const stolen = await request('GET', `/login/${C.email}/${C.sessionToken}`, {}, { sessionToken: C.sessionToken, email: C.email, ...otherClient });
        expectStatus(`C: token da sessão corrente vindo de outro User-Agent (${i}ª vez)`, stolen, 401);
    }
    expectStatus('C: no navegador original a sessão segue valendo', await api.validateSession(C, C.sessionToken), 200);
    const refusedLoginC = await api.login(C, C.password);
    expectStatus('C: login de novo responde "Desbloqueie seu login", e não senha bloqueada', refusedLoginC, 409, (body) => !body.sessionToken, 'sem sessionToken');
    const wrongPasswordC = await api.login(C, 'Errada@999');
    expectStatus('C: login com senha errada não devolve sessionToken', wrongPasswordC, wrongPasswordC.status, (body) => !body.sessionToken, 'sem sessionToken');

    const failures = results.filter((r) => !r.ok);
    console.log(`\n${results.length - failures.length}/${results.length} verificações ok`);
    for (const f of failures) console.log(`  FALHA [${f.section}] ${f.label}\n        ${f.detail}`);
    process.exit(failures.length ? 1 : 0);
}

main().catch((e) => {
    console.error(e);
    process.exit(2);
});
