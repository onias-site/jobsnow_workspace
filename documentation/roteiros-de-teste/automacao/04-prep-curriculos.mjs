// Prepara a carga de currículos a partir do índice legado profissionais2 (ES 9200): monta, para cada candidato, o corpo
// que a tela SubMenuMyResume enviaria ao salvar. Ordem de cada campo: dado do índice, senão inferido do texto do
// currículo, senão inventado (sorteio com semente fixa). Cerca de 5% dos currículos recebem valores nos limites das
// regras, de propósito, para achar incoerências entre front e back.
//
// Uso: node 04-prep-curriculos.mjs <pasta de saída> [semente=20261014]
// Saída: curriculos.jsonl ({id, resume, meta}), prep-invalidos.jsonl e reservados.txt (um e-mail por caso da tela)
import fs from 'fs';
import http from 'http';
import path from 'path';

const [, , outputDir, seedArg] = process.argv;
const SEED = Number(seedArg || 20261014);
const CURRENT_YEAR = 2026;

// mesmo gerador para a mesma semente: a carga pode ser refeita igual
let seedState = SEED >>> 0;
const random = () => {
    seedState = (seedState + 0x6d2b79f5) >>> 0;
    let t = seedState;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
};
const chance = (p) => random() < p;
const between = (min, max) => min + Math.floor(random() * (max - min + 1));
const pick = (list) => list[Math.floor(random() * list.length)];
const shuffle = (list) => {
    const copy = [...list];
    for (let i = copy.length - 1; i > 0; i--) {
        const j = Math.floor(random() * (i + 1));
        [copy[i], copy[j]] = [copy[j], copy[i]];
    }
    return copy;
};

// RegioesComponent.tsx: 67 regiões metropolitanas (sem 0 = qualquer estado e sem 10 = home office)
const REGIONS = [11, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 24, 27, 28, 31, 32, 33, 34, 35, 37, 38, 41, 42, 43, 44, 45, 46, 47, 48, 49, 51, 53, 54, 55,
    61, 62, 63, 64, 65, 66, 67, 68, 69, 71, 73, 74, 75, 77, 79, 81, 82, 83, 84, 85, 86, 87, 88, 89, 91, 92, 93, 94, 95, 96, 97, 98, 99];
const HOME_OFFICE = 10;

// ChooserLanguages.tsx: nome e id como a tela envia; patterns para achar o idioma no texto
const LANGUAGES = [
    { name: 'Inglês', id: 0, patterns: [/ingl[eê]s/i, /english/i], weight: 10 },
    { name: 'Espanhol', id: 3, patterns: [/espanhol/i, /spanish/i, /castelhano/i], weight: 6 },
    { name: 'Francês', id: 4, patterns: [/franc[eê]s/i, /french/i], weight: 2 },
    { name: 'Alemão', id: 11, patterns: [/alem[aã]o/i, /german/i], weight: 2 },
    { name: 'Italiano', id: 20, patterns: [/italiano/i, /italian/i], weight: 2 },
    { name: 'Japonês', id: 12, patterns: [/japon[eê]s/i, /japanese/i], weight: 1 },
    { name: 'Mandarim (Chinês)', id: 1, patterns: [/mandarim/i, /chin[eê]s/i, /chinese/i], weight: 1 },
    { name: 'Russo', id: 8, patterns: [/\brusso\b/i, /russian/i], weight: 1 },
    { name: 'Coreano', id: 18, patterns: [/coreano/i, /korean/i], weight: 1 },
    { name: 'Árabe', id: 5, patterns: [/[aá]rabe/i, /arabic/i], weight: 1 },
    { name: 'Hebraico', id: 44, patterns: [/hebraico/i, /hebrew/i], weight: 1 },
    { name: 'Polonês', id: 23, patterns: [/polon[eê]s/i, /polish/i], weight: 1 },
    { name: 'Holandês', id: 31, patterns: [/holand[eê]s/i, /dutch/i], weight: 1 },
    { name: 'Sueco', id: 40, patterns: [/sueco/i, /swedish/i], weight: 1 },
    { name: 'Turco', id: 16, patterns: [/\bturco\b/i, /turkish/i], weight: 1 },
    { name: 'Grego', id: 36, patterns: [/\bgrego\b/i, /greek/i], weight: 1 },
];
const FLUENT = /(fluente|fluência|fluencia|avançado|avancado|fluent|advanced|nativo|native|proficiente)/i;

const JOBS_BY_TYPE = {
    1: ['Desenvolvedor Java', 'Analista de Sistemas', 'Engenheiro de Dados', 'Desenvolvedor Front-end', 'Analista de Suporte', 'DevOps', 'Arquiteto de Software',
        'Analista de QA', 'Cientista de Dados', 'Desenvolvedor Full Stack', 'Analista de Infraestrutura', 'Scrum Master', 'Desenvolvedor Mobile', 'DBA', 'Analista de Segurança da Informação'],
    2: ['Analista de Recrutamento', 'Tech Recruiter', 'Assistente de RH', 'Business Partner de RH', 'Consultora de Seleção', 'Hunter', 'Coordenador de Talentos'],
    3: ['Contador', 'Engenheiro Civil', 'Advogado', 'Enfermeira', 'Administrador', 'Economista', 'Arquiteta', 'Psicólogo', 'Analista Financeiro', 'Professor'],
    4: ['Auxiliar Administrativo', 'Operador de Caixa', 'Motorista', 'Atendente', 'Recepcionista', 'Estoquista', 'Auxiliar de Produção', 'Vendedor', 'Porteiro'],
};
const COMPANIES = ['Accenture', 'Stefanini', 'TOTVS', 'Itaú', 'Bradesco', 'Santander', 'Ambev', 'Natura', 'Magalu', 'Nubank', 'iFood', 'Globo', 'Vivo', 'Claro',
    'Embraer', 'Petrobras', 'Capgemini', 'CI&T', 'Zup', 'Locaweb', 'Méliuz', 'Sicredi', 'Ânima', 'Grupo Pão de Açúcar', 'B3'];
const TECH_FILLERS = ['JAVA', 'PYTHON', 'REACT', 'ANGULAR', 'SQL', 'DOCKER', 'KUBERNETES', 'AWS', 'AZURE', 'LINUX', 'GIT', 'NODEJS', 'TYPESCRIPT', 'PHP', 'C#', 'SCRUM'];

const cleanText = (text) => String(text || '').replace(/\s+/g, ' ').trim();
const cut = (text, max) => cleanText(text).slice(0, max).trim();
const toNumber = (value) => {
    const number = Number(String(value === null || value === undefined ? '' : value).replace(',', '.'));
    return Number.isFinite(number) ? number : NaN;
};

function esRequest(method, uri, body) {
    const data = body ? JSON.stringify(body) : '';
    return new Promise((resolve, reject) => {
        const req = http.request({ host: 'localhost', port: 9200, method, path: uri, headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(data) } }, (res) => {
            let text = '';
            res.setEncoding('utf8');
            res.on('data', (c) => (text += c));
            res.on('end', () => resolve(JSON.parse(text)));
        });
        req.on('error', reject);
        req.write(data);
        req.end();
    });
}

function visRequest(uri, body) {
    const data = JSON.stringify(body);
    const started = Date.now();
    return new Promise((resolve) => {
        const req = http.request({ host: 'localhost', port: 8081, method: 'POST', path: uri, timeout: 120000, headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(data) } }, (res) => {
            let text = '';
            res.setEncoding('utf8');
            res.on('data', (c) => (text += c));
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

async function readLegacyResumes() {
    const includes = ['profissaoDesejada', 'ultimaProfissao', 'tipoVaga', 'ddd', 'homeoffice', 'mudanca', 'pcd', 'experiencia', 'senioridade', 'disponibilidade',
        'pretensaoClt', 'pretensaoPj', 'bitcoin', 'pretensaoNegociavel', 'emailParaExcessao', 'especialidades', 'requisitos', 'keywords', 'status', 'curriculo.t'];
    let page = await esRequest('POST', '/profissionais2/_search?scroll=2m', { size: 500, sort: ['_doc'], _source: { includes } });
    const all = [];
    while (page.hits && page.hits.hits.length) {
        all.push(...page.hits.hits.map((hit) => ({ id: hit._id, ...hit._source })));
        page = await esRequest('POST', '/_search/scroll', { scroll: '2m', scroll_id: page._scroll_id });
    }
    return all;
}

// ---------- campos ----------

function resolveResumeType(legacy, meta) {
    const type = Math.round(toNumber(legacy.tipoVaga));
    if ([1, 2, 3, 4].includes(type)) { meta.resumeType = 'index'; return type; }
    meta.resumeType = 'invented';
    return between(1, 4);
}

function inferJobFromText(text) {
    const lines = String(text || '').split(/\n/).map(cleanText).filter(Boolean).slice(0, 8);
    const candidate = lines.slice(1).find((line) => line.length >= 3 && line.length <= 50 && !/[@\d:\/]/.test(line) && /[a-z]/.test(line));
    return candidate || '';
}

function resolveDesiredJob(legacy, resumeType, text, meta) {
    const fromIndex = cut(legacy.profissaoDesejada, 50);
    if (fromIndex.length >= 2) { meta.desiredJob = 'index'; return fromIndex; }
    const inferred = cut(inferJobFromText(text) || legacy.ultimaProfissao, 50);
    if (inferred.length >= 2) { meta.desiredJob = 'inferred'; return inferred; }
    meta.desiredJob = 'invented';
    return pick(JOBS_BY_TYPE[resumeType]);
}

function resolveLastJob(legacy, resumeType, meta) {
    const fromIndex = cut(legacy.ultimaProfissao, 50);
    if (fromIndex.length >= 2) { meta.lastJob = 'index'; return fromIndex; }
    if (chance(0.3)) { meta.lastJob = 'omitted'; return ''; }
    meta.lastJob = 'invented';
    return pick(JOBS_BY_TYPE[resumeType]);
}

function resolveLinkedin(email, text, meta) {
    // o PDF do LinkedIn quebra a linha no hífen antes do código final do perfil ("israel-lacerda-" e "b68489186 (LinkedIn)"
    // na linha seguinte): o perfil terminado em hífen continua na próxima linha
    const match = String(text || '').match(/linkedin\.com\/in\/([A-Za-z0-9\-_%]+)(?:\s*\n\s*([A-Za-z0-9\-_%]+))?/i);
    if (match) {
        meta.linkedinAddress = 'inferred';
        const cutAtTheHyphen = match[1].endsWith('-') && match[2];
        const profile = cutAtTheHyphen ? match[1] + match[2] : match[1];
        return `https://www.linkedin.com/in/${profile}`;
    }
    meta.linkedinAddress = 'invented';
    const slug = email.split('@')[0].replace(/[^a-zA-Z0-9\-_]/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '') || 'candidato';
    const suffix = chance(0.5) ? `-${between(100, 99999).toString(36)}` : '';
    const host = chance(0.6) ? 'https://www.linkedin.com' : 'https://linkedin.com';
    const slash = chance(0.3) ? '/' : '';
    return `${host}/in/${slug}${suffix}${slash}`;
}

function resolveNotAllowedCompany(legacy, meta) {
    const raw = String(legacy.emailParaExcessao || '');
    const fromIndex = raw.split(/[,;\/]| e /).map((company) => cut(company, 20)).filter((company) => company.length >= 2);
    if (fromIndex.length) { meta.notAllowedCompany = 'index'; return [...new Set(fromIndex)]; }
    if (chance(0.6)) { meta.notAllowedCompany = 'empty'; return []; }
    meta.notAllowedCompany = 'invented';
    return shuffle(COMPANIES).slice(0, between(1, 3)).map((company) => cut(company, 20));
}

function resolveResumeText(legacy, meta) {
    const text = String((legacy.curriculo && legacy.curriculo.t) || '');
    if (cleanText(text).length >= 50) { meta.resumeText = 'index'; return text; }
    const words = [...(legacy.especialidades || []), ...(legacy.requisitos || []), ...(legacy.keywords || [])];
    if (words.length) { meta.resumeText = 'inferred'; return `Profissional com conhecimento em ${[...new Set(words)].join(', ')}.`; }
    meta.resumeText = 'invented';
    return `Profissional de tecnologia com experiência em ${shuffle(TECH_FILLERS).slice(0, between(3, 8)).join(', ')}.`;
}

function resolveLanguages(legacy, text, meta) {
    const found = [];
    for (const language of LANGUAGES) {
        const pattern = language.patterns.find((p) => p.test(text));
        if (!pattern) continue;
        const index = text.search(pattern);
        const around = text.slice(Math.max(0, index - 60), index + 80);
        found.push({ name: language.name, id: language.id, level: FLUENT.test(around) ? 2 : 1 });
    }
    const hasEnglishSkill = (legacy.especialidades || []).includes('INGLES');
    if (hasEnglishSkill && !found.some((l) => l.id === 0)) found.push({ name: 'Inglês', id: 0, level: 1 });
    if (found.length) { meta.spokenLanguage = 'inferred'; return found; }
    if (chance(0.45)) { meta.spokenLanguage = 'none'; return []; }
    meta.spokenLanguage = 'invented';
    const weighted = LANGUAGES.flatMap((l) => Array(l.weight).fill(l));
    const chosen = new Map();
    const count = between(1, 3);
    while (chosen.size < count) {
        const language = pick(weighted);
        chosen.set(language.id, { name: language.name, id: language.id, level: between(1, 2) });
    }
    return [...chosen.values()];
}

function randomRegionCount() {
    const roll = random();
    if (roll < 0.6) return between(1, 3);
    if (roll < 0.9) return between(4, 15);
    return between(16, 66);
}

function resolveDdd(legacy, meta) {
    const ddd = Math.round(toNumber(legacy.ddd));
    const hasFlags = legacy.homeoffice !== undefined || legacy.mudanca !== undefined;
    let mode;
    if (legacy.homeoffice === true && ddd === 0) mode = 'homeOffice';
    else if (legacy.mudanca === true) mode = 'anyRegion';
    else if (hasFlags || ddd > 0) mode = 'some';
    else { const roll = random(); mode = roll < 0.15 ? 'homeOffice' : roll < 0.3 ? 'anyRegion' : 'some'; }
    meta.regionMode = mode;
    meta.ddd = hasFlags ? 'index' : 'invented';
    if (mode === 'homeOffice') return [HOME_OFFICE];
    if (mode === 'anyRegion') return [...REGIONS];
    const total = randomRegionCount();
    const chosen = new Set(REGIONS.includes(ddd) ? [ddd] : []);
    for (const region of shuffle(REGIONS)) {
        if (chosen.size >= total) break;
        chosen.add(region);
    }
    return [...chosen];
}

function resolveExperience(legacy, text, meta) {
    const year = Math.round(toNumber(legacy.experiencia));
    if (year > 1900) { meta.experience = 'index'; return Math.min(70, Math.max(0, CURRENT_YEAR - year)); }
    const match = String(text).match(/(\d{1,2})\s*(\+\s*)?anos de experi[eê]ncia/i);
    if (match) { meta.experience = 'inferred'; return Math.min(70, Number(match[1])); }
    meta.experience = 'invented';
    const ranges = { 0: [0, 1], 1: [1, 3], 2: [3, 5], 3: [5, 9], 4: [9, 25] };
    const seniority = Math.round(toNumber(legacy.senioridade));
    const [min, max] = ranges[seniority] || [0, 20];
    return between(min, max);
}

function resolveDisponibility(legacy, text, meta) {
    const value = Math.round(toNumber(legacy.disponibilidade));
    if (Number.isFinite(value) && value >= 0) { meta.disponibility = 'index'; return Math.min(30, value); }
    if (/disponibilidade imediata/i.test(text)) { meta.disponibility = 'inferred'; return 0; }
    meta.disponibility = 'invented';
    return chance(0.5) ? 0 : between(1, 30);
}

function resolveTravel(text, meta) {
    if (/(disponibilidade|dispon[ií]vel) (para|pra) viag/i.test(text)) { meta.travel = 'inferred'; return true; }
    meta.travel = 'invented';
    return chance(0.3);
}

function resolveSalary(value) {
    const number = Math.round(toNumber(value));
    if (!Number.isFinite(number) || number <= 0) return 0;
    return Math.min(100000, Math.max(1000, number));
}

function resolveSalaries(legacy, experience, meta) {
    let clt = resolveSalary(legacy.pretensaoClt);
    let pj = resolveSalary(legacy.pretensaoPj);
    meta.salaries = clt || pj ? 'index' : 'invented';
    if (!clt && !pj) {
        const base = 1500 + experience * between(400, 1200);
        const roll = random();
        if (roll < 0.4) clt = Math.min(30000, base);
        else if (roll < 0.7) pj = Math.min(30000, Math.round(base * 1.4));
        else { clt = Math.min(30000, base); pj = Math.min(30000, Math.round(base * 1.4)); }
    }
    let btc = resolveSalary(legacy.bitcoin);
    meta.btc = btc ? 'index' : 'invented';
    if (!btc && chance(0.15)) btc = between(1000, 20000);
    return { clt, pj, btc };
}

// ---------- habilidades (como getSkillsContext em TabSkills.tsx) ----------

const toResumeSkill = (item, type, category) => {
    const resumeSkill = { skill: item.skill, word: item.word || item.skill, type, category };
    const parent = item.parent || [];
    if (parent.length) resumeSkill.parent = parent;
    const associated = item.associated || '';
    if (associated.length >= 2 && associated.length <= 50) resumeSkill.associated = associated;
    return resumeSkill;
};

function getImplicitSkills(list) {
    const skills = list.map((item) => item.skill);
    const parents = new Set(list.flatMap((item) => item.parent || []).filter((parent) => !skills.includes(parent)));
    return [...parents].map((skill) => ({ skill }));
}

function buildSkills(response, meta) {
    let main = response.skill || [];
    let excluded = response.excludedSkill || [];
    if (main.length > 3 && chance(0.2)) {
        const moved = shuffle(main).slice(0, between(1, 3));
        excluded = [...excluded, ...moved];
        main = main.filter((item) => !moved.includes(item));
        meta.excludedSkillsMoved = moved.length;
    }
    const result = [];
    for (const [type, items] of Object.entries(response.discardedSkills || {})) {
        for (const item of items) result.push(toResumeSkill(item, type, 'discardedSkills'));
    }
    for (const item of excluded) result.push(toResumeSkill(item, 'excludedSkills', 'excludedSkills'));
    for (const item of main) result.push(toResumeSkill(item, 'skillsFromResume', 'skillsFromText'));
    for (const item of getImplicitSkills(main)) result.push(toResumeSkill(item, 'parent', 'parent'));
    meta.skillCount = main.length;
    return result;
}

// ---------- validação como a tela faz (frontAceita) ----------

const linkedinRegex = /^https:\/\/(www\.)?linkedin\.com\/in\/[a-zA-Z0-9-_%]*[a-zA-Z0-9_%]\/?$/;
const outOfLength = (text, min, max) => typeof text !== 'string' || text.length < min || text.length > max;
const twoNonBlank = /\S.*\S/s;

function frontErrors(resume, resumeText) {
    const errors = [];
    if (outOfLength(resume.desiredJob, 2, 50)) errors.push('desiredJob');
    if (resume.lastJob !== undefined && outOfLength(resume.lastJob, 2, 50)) errors.push('lastJob');
    if (!linkedinRegex.test(resume.linkedinAddress || '')) errors.push('linkedinAddress');
    if (resume.notAllowedCompany.some((c) => outOfLength(c, 2, 20))) errors.push('notAllowedCompany');
    if (![1, 2, 3, 4].includes(resume.resumeType)) errors.push('resumeType');
    if (resume.resumeType === 1 && !resumeText) errors.push('resumeText');
    if (resume.spokenLanguage.some((l) => outOfLength(l.name, 3, 20) || ![1, 2].includes(l.level))) errors.push('spokenLanguage');
    const regions = resume.ddd;
    if (!regions.length || regions.length > 67) errors.push('ddd');
    const intOut = (v, max) => !Number.isInteger(v) || v < 0 || v > max;
    if (intOut(resume.experience, 70)) errors.push('experience');
    if (intOut(resume.disponibility, 30)) errors.push('disponibility');
    if (intOut(resume.temporallyJobTime, 12)) errors.push('temporallyJobTime');
    if (!resume.clt && !resume.pj) errors.push('clt|pj');
    for (const salary of ['clt', 'pj', 'btc']) {
        const value = resume[salary];
        if (value !== undefined && (value < 1000 || value > 100000)) errors.push(salary);
    }
    for (const skill of resume.skill) {
        if (outOfLength(skill.skill, 2, 50) || !twoNonBlank.test(skill.skill)) errors.push(`skill.skill:${skill.skill}`);
        if (outOfLength(skill.word, 2, 50) || !twoNonBlank.test(skill.word)) errors.push(`skill.word:${skill.word}`);
        if (outOfLength(skill.type, 2, 20)) errors.push(`skill.type:${skill.type}`);
        if (outOfLength(skill.category, 2, 20)) errors.push(`skill.category:${skill.category}`);
        if ((skill.parent || []).some((p) => outOfLength(p, 2, 50) || !twoNonBlank.test(p))) errors.push(`skill.parent:${skill.skill}`);
    }
    return [...new Set(errors)];
}

// ---------- valores nos limites (cerca de 5%) ----------

const EDGE_CASES = [
    ['desiredJob com 2 caracteres', (r) => { r.desiredJob = 'TI'; }],
    ['desiredJob com 50 caracteres', (r) => { r.desiredJob = 'Desenvolvedor de software sênior com foco em Java!'.padEnd(50, 'x').slice(0, 50); }],
    ['lastJob com 50 caracteres e acentos', (r) => { r.lastJob = 'Coordenação de Operações Logísticas e Expedição já'.slice(0, 50); }],
    ['1 região', (r) => { r.ddd = [pick(REGIONS)]; }],
    ['66 regiões', (r) => { r.ddd = shuffle(REGIONS).slice(0, 66); }],
    ['experiência 0', (r) => { r.experience = 0; }],
    ['experiência 70', (r) => { r.experience = 70; }],
    ['pretensões mínimas', (r) => { r.clt = 1000; r.pj = 1000; r.btc = 1000; }],
    ['pretensões máximas', (r) => { r.clt = 100000; r.pj = 100000; r.btc = 100000; }],
    ['disponibilidade 30 e temporário 12', (r) => { r.disponibility = 30; r.temporallyJobTime = 12; }],
    ['empresa com acento e símbolo', (r) => { r.notAllowedCompany = ['Itaú Unibanco', 'C&A', 'Ânima & Cia', 'B3']; }],
    ['empresa com 20 caracteres', (r) => { r.notAllowedCompany = ['Empresa Vinte Chars!'.slice(0, 20)]; }],
    ['linkedin com %', (r) => { r.linkedinAddress = 'https://www.linkedin.com/in/jo%C3%A3o-silva-123/'; }],
    ['todos os idiomas fluentes', (r) => { r.spokenLanguage = LANGUAGES.map((l) => ({ name: l.name, id: l.id, level: 2 })); }],
    ['só bitcoin além de pj', (r) => { delete r.clt; r.pj = 1000; r.btc = 50000; }],
    ['nada negociável, pcd e viagem', (r) => { r.negotiableClaim = false; r.pcd = true; r.travel = true; }],
];

// ---------- principal ----------

async function main() {
    fs.mkdirSync(outputDir, { recursive: true });
    const legacyResumes = await readLegacyResumes();
    console.log(`lidos ${legacyResumes.length} currículos do profissionais2`);
    const validStream = fs.createWriteStream(path.join(outputDir, 'curriculos.jsonl'));
    const invalidStream = fs.createWriteStream(path.join(outputDir, 'prep-invalidos.jsonl'));
    const skillsStream = fs.createWriteStream(path.join(outputDir, 'skills-fromText-falhas.jsonl'));
    const reserved = {};
    const lines = [];

    // as decisões aleatórias são tomadas em sequência (determinísticas); só as chamadas de habilidades são paralelas
    const prepared = legacyResumes.map((legacy) => {
        const meta = { legacyStatus: Math.round(toNumber(legacy.status)) };
        const text = String((legacy.curriculo && legacy.curriculo.t) || '');
        const resumeType = resolveResumeType(legacy, meta);
        const resume = {
            ddd: resolveDdd(legacy, meta),
            desiredJob: resolveDesiredJob(legacy, resumeType, text, meta),
            disponibility: resolveDisponibility(legacy, text, meta),
            email: legacy.id,
            resumeType,
            skill: [],
            experience: resolveExperience(legacy, text, meta),
            spokenLanguage: resolveLanguages(legacy, text, meta),
            linkedinAddress: resolveLinkedin(legacy.id, text, meta),
            negotiableClaim: legacy.pretensaoNegociavel === undefined ? chance(0.6) : !!legacy.pretensaoNegociavel,
            notAllowedCompany: resolveNotAllowedCompany(legacy, meta),
            pcd: legacy.pcd === undefined ? chance(0.03) : !!legacy.pcd,
            temporallyJobTime: chance(0.5) ? 0 : between(1, 12),
            travel: resolveTravel(text, meta),
        };
        const lastJob = resolveLastJob(legacy, resumeType, meta);
        if (lastJob) resume.lastJob = lastJob;
        const { clt, pj, btc } = resolveSalaries(legacy, resume.experience, meta);
        if (clt) resume.clt = clt;
        if (pj) resume.pj = pj;
        if (btc) resume.btc = btc;
        if (chance(0.05)) {
            const [label, apply] = pick(EDGE_CASES);
            apply(resume);
            meta.edgeCase = label;
        }
        const resumeText = resumeType === 1 ? resolveResumeText(legacy, meta) : '';
        const excludedRoll = random();
        return { legacy, resume, meta, resumeText, excludedRoll };
    });

    let next = 0;
    async function worker() {
        while (next < prepared.length) {
            const item = prepared[next++];
            if (item.resume.resumeType === 1) {
                const response = await visRequest('/skills/fromText', { text: item.resumeText, excludedSkill: [] });
                item.meta.fromTextMs = response.ms;
                if (response.status !== 200) {
                    skillsStream.write(JSON.stringify({ id: item.legacy.id, status: response.status, body: response.body, textLength: item.resumeText.length }) + '\n');
                    item.meta.fromTextStatus = response.status;
                } else {
                    item.resume.skill = buildSkills(response.body, item.meta);
                }
            }
        }
    }
    await Promise.all(Array.from({ length: 8 }, () => worker()));

    for (const { legacy, resume, meta, resumeText } of prepared) {
        meta.resumeTextLength = resumeText.length;
        const errors = frontErrors(resume, resumeText);
        meta.frontAceita = errors.length === 0;
        if (errors.length) meta.frontErrors = errors;
        const line = JSON.stringify({ id: legacy.id, resume, meta, resumeText }) + '\n';
        (meta.frontAceita ? validStream : invalidStream).write(line);
        // os recusados pela tela vão à carga num passo à parte: o backend também precisa recusá-los
        meta.frontAceita && lines.push(legacy.id);
        const caseKey = resume.resumeType === 1 && meta.regionMode === 'homeOffice' ? 'homeOffice'
            : meta.regionMode === 'anyRegion' && resume.resumeType === 2 ? 'anyRegion'
            : `type${resume.resumeType}`;
        if (meta.frontAceita && !meta.edgeCase && !reserved[caseKey] && legacy.status !== 0 && (resume.resumeType !== 1 || resume.skill.length >= 3)) reserved[caseKey] = legacy.id;
    }
    validStream.end();
    invalidStream.end();
    skillsStream.end();
    fs.writeFileSync(path.join(outputDir, 'reservados.txt'), Object.values(reserved).join('\n') + '\n');
    fs.writeFileSync(path.join(outputDir, 'reservados.json'), JSON.stringify(reserved, null, 2));
    console.log(JSON.stringify({ total: prepared.length, frontAceita: lines.length, frontRecusa: prepared.length - lines.length, reservados: reserved }));
}

main();
