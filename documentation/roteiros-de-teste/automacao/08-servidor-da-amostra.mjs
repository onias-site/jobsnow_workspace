// Servidor local da automação pela tela (roteiro 04), só em 127.0.0.1:3999:
//   GET /          a amostra (amostra.json da pasta indicada)
//   GET /helper.js o helper que a página carrega (08-tela-curriculo-helper.js)
//   POST /         acrescenta o corpo (uma verificação) em resultados-tela.jsonl da mesma pasta
// Uso: node 08-servidor-da-amostra.mjs <pasta com amostra.json>
import fs from 'fs';
import http from 'http';
import path from 'path';
import { fileURLToPath } from 'url';

const dir = process.argv[2];
const helper = path.join(path.dirname(fileURLToPath(import.meta.url)), '08-tela-curriculo-helper.js');

http.createServer((request, response) => {
    response.setHeader('Access-Control-Allow-Origin', '*');
    response.setHeader('Access-Control-Allow-Headers', '*');
    response.setHeader('Access-Control-Allow-Methods', 'GET,POST,OPTIONS');
    if (request.method === 'OPTIONS') return response.end();
    if (request.method === 'POST') {
        let body = '';
        request.on('data', (chunk) => (body += chunk));
        request.on('end', () => {
            fs.appendFileSync(path.join(dir, 'resultados-tela.jsonl'), body + '\n');
            response.end('ok');
        });
        return;
    }
    if (request.url.startsWith('/helper.js')) {
        response.setHeader('Content-Type', 'application/javascript');
        return response.end(fs.readFileSync(helper));
    }
    response.setHeader('Content-Type', 'application/json');
    response.end(fs.readFileSync(path.join(dir, 'amostra.json')));
}).listen(3999, '127.0.0.1');
