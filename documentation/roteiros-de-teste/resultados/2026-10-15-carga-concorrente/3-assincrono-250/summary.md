# Carga concorrente sobre os currículos

Níveis pedidos: 250 clientes simultâneos. Requisições: 4932.

| Clientes | Endpoint | API | Req. | Erros | Status | Causa dos status 0 | Entrada méd. (B) | Saída méd. (B) | Em voo méd. | Em voo máx. | p50 (ms) | p95 (ms) | Heap méd. (MB) | Heap máx. (MB) | Heap total (MB) |
|--:|---|---|--:|--:|---|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 250 | `DELETE /login/{email}/{sessionToken}` | jn | 541 | 0 | 200 |  | 2 | 0 | 192 | 250 | 5136 | 11412 | 207 | 292 | 352 |
| 250 | `DELETE /resume/{email}/language/{language}` | vis | 538 | 0 | 200 |  | 2 | 36 | 192 | 250 | 6696 | 36547 | 1327 | 1827 | 2080 |
| 250 | `DELETE /resume/{email}/language/{language}/status` | vis | 1076 | 96 | 0 200 | ECONNRESET:89 timeout:7 | 2 | 33 | 192 | 250 | 9028 | 81373 | 968 | 1802 | 2080 |
| 250 | `GET /resume/{email}` | vis | 541 | 0 | 200 |  | 0 | 3969 | 192 | 250 | 2131 | 3883 | 937 | 1329 | 1832 |
| 250 | `HEAD /login/{email}/token` | jn | 541 | 0 | 200 409 |  | 0 | 0 | 192 | 250 | 3341 | 10122 | 176 | 283 | 352 |
| 250 | `POST /login/{email}` | jn | 541 | 0 | 200 409 |  | 34 | 186 | 248 | 250 | 31242 | 44095 | 205 | 290 | 352 |
| 250 | `POST /login/{email}/password` | jn | 58 | 0 | 200 |  | 93 | 192 | 250 | 250 | 33905 | 48977 | 211 | 287 | 352 |
| 250 | `POST /login/{email}/token/language/{language}` | jn | 58 | 0 | 429 |  | 2 | 211 | 250 | 250 | 5579 | 18800 | 201 | 288 | 352 |
| 250 | `POST /resume/{email}/language/{language}` | vis | 538 | 0 | 200 |  | 3926 | 3983 | 192 | 250 | 7001 | 19538 | 1632 | 2109 | 2552 |
| 250 | `POST /skills/fromText` | vis | 500 | 0 | 200 |  | 4556 | 3584 | 188 | 250 | 2921 | 9581 | 1848 | 2246 | 2552 |

## Espera da escrita assíncrona

Tempo entre o fim de uma fase (todas as respostas recebidas) e o ES mostrar o que ela gravou.

| Clientes | Depois de | Itens | Espera (ms) | Convergiu |
|--:|---|--:|--:|---|
| 250 | login | 541 | 11141 | sim |
| 250 | inativar | 538 | 9360 | sim |
| 250 | reativar | 538 | 180208 | não |
| 250 | excluir | 538 | 31636 | sim |
| 250 | reinserir | 538 | 51664 | sim |