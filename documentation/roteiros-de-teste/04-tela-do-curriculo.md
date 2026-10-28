# Roteiro 04 — Tela do currículo (Ver meu currículo)

**Pré-requisito:** [00-preparacao-do-ambiente.md](00-preparacao-do-ambiente.md) até o item 4 (ambiente no ar e login).

> **Criado e executado em 2026-10-15**, pela automação no Chrome, com 36 currículos (30 já carregados do `profissionais2` e 6 novos), de C1 a C8. Resultado em `resultados/2026-10-14-profissionais2/achados.md`, seção "Madrugada de 2026-10-15".

> **Executado de novo em 2026-10-26**, à mão no Chrome (a amostra da automação depende da carga `profissionais2`, que o reset do vis apagou: a base tinha só 2 currículos). Tela em `/meus-dados/sobre-mim`. C1 pela tela com um currículo de TI (`roteiro03.20261026@teste.com`); um operacional (tipo 4) foi salvo pela API com a sessão de `roteiro01b.20261026@teste.com` para o C6 e o 4.2. Tudo conferiu; os avisos ao operador do C6 vão para o Telegram real (a API do vis não usa o arquivo local) e não foram vistos. Notas em [Observações da execução (2026-10-26)](#observações-da-execução-2026-10-26).

## Como a tela funciona (resumo)

1. Abas, nesta ordem: **Currículo**, **Idiomas**, **N Habilidades** (só no tipo 1, Tecnologia da Informação, depois de ler o texto colado), **Opções** e **Salários**. O botão de cada aba avança para a próxima e fica desabilitado enquanto houver pendência; o da última é **Salvar dados**. Clicar no título de uma aba distante anda **uma aba por vez** na direção dela (de Currículo, um clique em Salários leva a Idiomas); para chegar, clique de novo.
2. Ao abrir, a tela lê o currículo gravado (`GET /resume/{email}`) e preenche as abas. A faixa do topo mostra a situação: "Você ainda não tem currículo salvo", "Currículo ativo: visível para os recrutadores" ou "Currículo inativo: oculto dos recrutadores". Sem login, não mostra nada e não abre o modal de login.
3. O texto do currículo não é gravado (LGPD). O TI já salvo dispensa o texto; colar um texto novo refaz a lista de habilidades (`POST skills/fromText`).
4. Na faixa de situação, no topo e visíveis em todas as abas (desde 2026-10-15; antes só ao lado de **Salvar dados**, na última aba): **Inativar** (ativo), **Reativar** (inativo) e **Excluir**, cada um com confirmação. Excluir apaga de vez e limpa o formulário.
5. Regras de campo (as mesmas no back e no front):
   - LinkedIn no formato `https://www.linkedin.com/in/perfil`, sem hífen no fim do perfil (`/` final aceito);
   - empresas de 2 a 50 caracteres (eram 20 até 2026-10-15), pelo autocomplete (3 letras) ou digitadas + Enter;
   - de 1 a 67 regiões; home office (10) sozinho: marcar uma região desmarca o home office, e o contrário, com um aviso dizendo o que foi desmarcado (desde 2026-10-15);
   - experiência de 0 a 70 anos (grava o ano de início; 70 vira "especialista" no agrupador), disponibilidade de 0 a 30 dias, temporário de 0 a 12 meses;
   - CLT ou PJ obrigatório (1.000 a 100.000); bitcoin opcional.
6. Salvar grava em `vis_resume` (reativa o inativo), recalcula os agrupadores (`jn_grouper`, sem o DDD no hash) e acrescenta o e-mail (hash) à lista `emails` do LinkedIn em `vis_resume_linkedin`. Quando a lista fica com mais de um e-mail, o currículo salva assim mesmo e o operador do suporte é avisado no Telegram. Trocar de LinkedIn ou excluir tira só o próprio e-mail da lista; o registro some com o último.

## Automação

| Arquivo | Para quê |
|---|---|
| `automacao/07-amostra-para-tela.mjs` | escolhe a amostra (por tipo) e cria candidatos novos; abre a sessão de cada um com o User-Agent do Chrome (a sessão só vale para o cliente que a abriu) e grava `amostra.json` |
| `automacao/08-servidor-da-amostra.mjs` | serve, em `127.0.0.1:3999`, a amostra e o helper, e grava cada verificação em `resultados-tela.jsonl` |
| `automacao/08-tela-curriculo-helper.js` | roda na página: `T.stepA(i)` confere a recarga do candidato anterior, roda o ciclo de vida dele e troca para o candidato `i`; `T.stepB(i)` preenche as abas, salva e recarrega |
| `automacao/09-conferir-tela-x-es.mjs` | compara cada currículo da amostra com o gravado no ES e confere que os excluídos sumiram |

Na página, cada passo é: `eval(await fetch('http://127.0.0.1:3999/helper.js').then(r => r.text())); await T.stepA(i)` e depois o mesmo com `T.stepB(i)`.

---

## C1 — Salvar pela tela, nos 4 tipos

- [ ] 1.1 Para cada tipo (TI, recrutamento, superior, operacional): preencha função buscada, última função, LinkedIn, empresas (uma pelo autocomplete, uma digitada + Enter), tipo e, no TI, o texto do currículo. Avance.
- [ ] 1.2 Idiomas: marque "Tenho conhecimento em outro(s) idioma(s)", escolha os idiomas e o nível de cada um. Avance (no TI, a aba Habilidades mostra a contagem lida do texto).
- [ ] 1.3 Opções: regiões, PCD, viagens, experiência, disponibilidade, temporário. Salários: CLT, PJ, bitcoin, negociável. **Salvar dados**.
  > Os campos numéricos aparecem ao **desmarcar** as caixas: "Estou pleiteando meu primeiro emprego" → **Anos de experiência**; "Tenho disponibilidade imediata" → **Dias necessários**; "Não aceito empregos temporários" → **Total mínimo de duração (em meses)**; "Não aceito empregos CLT/PJ" → a pretensão de cada um. Todas começam marcadas, exceto PCD e viagens.
- [ ] 1.4 Esperado: toast "Currículo salvo com sucesso", com o detalhe "Seu currículo está ativo e visível para os recrutadores." (sem repetir o título: achado 29), e a faixa "Currículo ativo", com **Inativar** e **Excluir**; `vis_resume` com os campos enviados (experiência como ano de início) e `vis_resume_linkedin` com o endereço e o hash do e-mail em `emails`.

## C2 — Recarga (GET /resume)

- [ ] 2.1 Recarregue a página. Esperado: as abas voltam preenchidas com o que foi salvo, inclusive empresas, idiomas, regiões (67 regiões → "qualquer estado / cidade") e, no TI, a aba **N Habilidades** com as habilidades gravadas.
  > **Corrigido em 2026-10-15:** o TI salvo com uma habilidade sem conhecimento implícito quebrava a recarga (`item.parent is not iterable`) e a aba Habilidades sumia.

## C3 — Inativar e reativar

- [ ] 3.1 Na primeira aba, sem avançar: **Inativar** na faixa → "Sim, inativar". Esperado: faixa "Currículo inativo", agora com **Reativar** e **Excluir**; registro em `vis_inactive_resume` e grupos em `jn_inactive_grouper`.
- [ ] 3.2 **Reativar** na faixa → "Sim, reativar". Esperado: faixa "Currículo ativo", de volta a `vis_resume` e `jn_grouper`.
- [ ] 3.3 Avance até a última aba. Esperado: ao lado de **Salvar dados** não há mais Inativar, Reativar nem Excluir (ficam só na faixa).

## C4 — Excluir (ativo e inativo)

- [ ] 4.1 **Excluir** na faixa → "Sim, excluir". Esperado: toast "Currículo excluído", faixa "Você ainda não tem currículo salvo" (sem botões), formulário vazio e nada em `vis_resume` nem em `vis_inactive_resume`; o e-mail sai da lista do endereço em `vis_resume_linkedin` (o registro some se era o único).
- [ ] 4.2 Repita com um currículo inativo (inativar e depois excluir).

## C5 — Validações da tela

- [ ] 5.1 LinkedIn `https://www.linkedin.com/in/fulano-` → o avançar da aba Currículo fica desabilitado, com "O endereço do linkedin deve ter o formato ...".
- [ ] 5.2 Empresa com mais de 50 caracteres → "Cada empresa / consultoria deve ter de 2 a 50 caracteres".
  > **Visto em 2026-10-26:** enquanto se digita o nome longo, o autocomplete consulta o servidor com o texto inteiro, e a recusa dele aparece como aviso cru, em inglês: "search — The field search has a value ... that is a string whith a length 62 that is greater than specified value 50". Ver observação 1.
- [ ] 5.2b Autocomplete: digite `Tra` e escolha "Transportadoraaricanduva" (24 caracteres). Esperado: a empresa entra e o avançar continua habilitado (achado 23, corrigido em 2026-10-15 subindo o limite para 50).
- [ ] 5.3 Experiência 71 → "Os anos de experiência devem estar entre 1 e 70" e o avançar desabilitado; 70 salva.
- [ ] 5.4 Home office e depois uma região. Esperado: só a região fica marcada, com o aviso "Home office desmarcado — Ao escolher uma região, o home office foi desmarcado: os dois não podem ficar juntos." O mesmo ao marcar "qualquer estado / cidade" com o home office marcado.
- [ ] 5.5 Três regiões e depois home office. Esperado: só o home office fica marcado, com o aviso "Regiões desmarcadas — Home office não combina com regiões: as 3 regiões escolhidas foram desmarcadas." Com uma região só: "a região escolhida foi desmarcada". Sem nenhuma região antes, nenhum aviso (achado 28).

## C6 — LinkedIn de outro e-mail

- [ ] 6.1 Salve o candidato B com o LinkedIn do candidato A. Esperado: salva; em `vis_resume_linkedin` o endereço tem os dois e-mails em `emails`; o operador recebe no Telegram "O LinkedIn ... já estava no currículo de outro e-mail e acaba de ser salvo no currículo de ...".
- [ ] 6.2 B volta ao seu próprio LinkedIn. Esperado: o endereço de A fica só com o e-mail de A (antes de 2026-10-15 o registro sumia: achado 24), e o de B tem o e-mail de B.
- [ ] 6.3 Um terceiro candidato salva com o LinkedIn de A. Esperado: novo aviso ao operador.

## C7 — Sem login

- [ ] 7.1 Console: `sessionStorage.removeItem('login'); localStorage.removeItem('logins')` e recarregue. Esperado: sem faixa de situação, formulário vazio, nenhum modal.

## C8 — Limite diário das sugestões, a partir desta tela

- [ ] 8.1 Siga o S10 do roteiro 01 e o H12 do roteiro 02 com um currículo de TI recarregado.
- [ ] 8.2 (Executado em 2026-10-26: confere.) Sem colar o texto do currículo depois de recarregar, abra "Deixamos de listar alguma habilidade?". Esperado: aviso "Para sugerir uma habilidade, cole o texto do seu currículo na aba Currículo..." no topo do modal, campo da habilidade bloqueado e **Enviar** desabilitado (achado 26, corrigido em 2026-10-15). Cole o texto e reabra: o campo libera.

## Observações da execução (2026-10-26)

| # | O que se viu | Situação |
|---|---|---|
| 1 | O autocomplete de empresas manda ao servidor o texto digitado mesmo com mais de 50 caracteres; o 422 da validação vira um aviso cru, em inglês, com o nome técnico do campo (`search`). | **Corrigido em 2026-10-26** (`NotAllowedCompany.tsx` não consulta acima de 50 caracteres; conferido no Chrome: 3 e 50 consultam, 51 não, sem aviso) |
| 2 | Clicar no título de uma aba distante anda uma aba por vez. | **a avaliar**; o roteiro descreve o comportamento |
| 3 | C1 a C5, C7 e o 8.2 pela tela; 4.2 e C6 pela API (2 contas). Pretensões, idiomas, regiões (DDD 11 e 19), experiência gravada como ano de início (12 anos → 2014) e empresas conferidos no `vis_resume`. | ok |
| 4 | Excluir o único dono de um LinkedIn apaga o registro de `vis_resume_linkedin`; com dois donos, a saída de um deixa só o outro. | ok |
| 5 | Os avisos ao operador do C6 saem pelo Telegram real da API do vis; não há como conferir no arquivo local. | ambiente |
