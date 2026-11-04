# Roteiro 04 — execução de 2026-11-03 (local, Chrome com automação, e-mail mock)

Tela pela conta `roteiro01b.20261103@teste.com` (currículo TI, 110 habilidades). C4 e C6 pela API (vis 8081, sessão aberta na js 8082) com contas novas `roteiro04a` a `roteiro04l.20261103@teste.com`, currículo operacional (tipo 4); script em `C:\Users\Hp Elitebook\.claude\jobs\271268fc\tmp\c4c.mjs` (temporário).

| Cenário | Resultado | Observação |
|---|---|---|
| C1 salvar (TI) | ok | toast "Currículo salvo com sucesso" + "Seu currículo está ativo e visível para os recrutadores."; `vis_resume` com CLT 9500, DDD 11, 12 anos → `experience` 2014, empresa proibida, tipo 1; `vis_resume_linkedin` com o hash do e-mail |
| C2 recarga | ok | abas preenchidas, "110 Habilidades" de volta |
| C3 inativar / reativar | ok | toasts "Currículo inativado" / "Currículo reativado"; registro foi a `vis_inactive_resume` e voltou |
| C4 excluir ativo e inativo | ok | 4.1 e 4.2 pela API; GET devolve os dois vazios; o registro do LinkedIn some com o único dono, e com dois donos a exclusão de um deixa o outro |
| C5 validações | ok | 5.1 mensagem do formato e avançar desabilitado; 5.2 "de 2 a 50 caracteres" sem aviso cru do autocomplete; 5.2b com "Trabalhandocomacomgas" (o "Transportadoraaricanduva" não existe mais na base); 5.3 "entre 1 e 70" e 70 aceito; 5.4 e 5.5 (uma região) com os avisos esperados |
| C6 LinkedIn de outro e-mail | ok | 6.1 dois e-mails no endereço; 6.2 B volta ao seu e A fica só com o dele; 6.3 C entra com A. **Os dois avisos ao operador agora saem no arquivo local** `C:\logs\telegram\support-751717896.txt` (em 26/10 iam só ao Telegram real) |
| C7 sem login | ok | sem faixa, formulário vazio, nenhum modal |
| C8 limite diário | coberto | pelo S10 do roteiro 01 (vale o defeito D2, bloqueio de 48 h) |

**Armadilhas da automação pela API** (não são defeitos):
- logo após criar a sessão, o vis responde 401 `invalidSession` por ~2 s (escrita assíncrona local; ver `waitForTheAsynchronousWrites`);
- um segundo `POST /login/{email}` com sessão aberta dá 409 (sessão única por e-mail): guarde o token da primeira execução;
- no Node 18, `localhost:9200` resolve para `::1` e o ES recusa; use `127.0.0.1`.
