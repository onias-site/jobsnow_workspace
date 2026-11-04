# Roteiro 05 — execução de 2026-11-03 (local, Chrome com automação, e-mail mock)

Contas: `roteiro01b.20261103@teste.com` (TI, pela tela, junto com o roteiro 04) e `roteiro05a.20261103@teste.com` (tipo 4, sessão aberta pela API js com o User-Agent do Chrome e posta no `sessionStorage`, senha de teste `Roteiro@2026x`). LinkedIn compartilhado e exclusões também pelas contas `roteiro04*` do roteiro 04.

| Passo | Resultado | Observação |
|---|---|---|
| 1.1 | ✔ | roteiro 04, C7 |
| 1.2 | ✔ | `sessionToken` inventado: `GET` 401 em silêncio, sem faixa e sem modal |
| 1.3 | ✔ | faixa "Você ainda não tem currículo salvo", sem botões |
| 1.4, 1.5 | ✔ | roteiro 04, C2 e C3 |
| 1.6 | ✔ | `GET` só com campos do currículo (sem `sessionToken`, `ip`, `userAgent`, `hash`, `email`) |
| 2.1 a 2.3 | ✔ | roteiro 04, C1 |
| 2.4 | parcial | tipo 4 pela API; tipos 2 e 3 não repetidos |
| 2.5 + 2.6 | ✔ | inativo, sessão encerrada no servidor, **Salvar dados** → modal → senha → salvar refeito → "Currículo salvo com sucesso" e faixa verde |
| 2.7, 2.8 | ✔ | roteiro 04, C5 (temporário 13 e sem CLT/PJ não repetidos) |
| 2.9, 2.10 | ✔ | roteiro 04, C6; aviso ao operador agora também no arquivo local do Telegram |
| 3.1, 3.2 | ✔ | toasts e e-mails `DeactivatedResume` / `ReactivatedResume` |
| 3.3, 4.3 | ✔ | "Não" não muda nada |
| 3.4 | ✔ | excluído na 2ª aba; na 1ª, Inativar → 404, aviso "Currículo não encontrado — Seu currículo não existe mais: ele foi excluído em outra janela." e faixa cinza |
| 3.5 | ✔ | 401 → modal → senha → inativação refeita |
| 4.1, 4.2 | ✔ | pela tela (4.1) e pela API (4.2); e-mail `DeletedResume`; LinkedIn removido com o único dono |
| 4.4 | ✔ | depois de excluir, avançar desabilitado |
| 4.5 | ✔ | 401 → modal → senha → exclusão refeita, "Currículo excluído" e formulário vazio |

Nenhum defeito novo.
