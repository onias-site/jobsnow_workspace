# Carga concorrente sobre os currículos

Níveis pedidos: 10, 50, 100, 250, 500, 1000 clientes simultâneos. Requisições: 3099.

| Clientes | Endpoint | API | Req. | Erros | Status | Causa dos status 0 | Entrada méd. (B) | Saída méd. (B) | Em voo méd. | Em voo máx. | p50 (ms) | p95 (ms) | Heap méd. (MB) | Heap máx. (MB) | Heap total (MB) |
|--:|---|---|--:|--:|---|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 10 | `DELETE /login/{email}/{sessionToken}` | jn | 22 | 0 | 200 |  | 2 | 0 | 8 | 10 | 143 | 213 | 150 | 154 | 292 |
| 10 | `DELETE /resume/{email}/language/{language}` | vis | 22 | 0 | 200 |  | 2 | 37 | 8 | 10 | 654 | 802 | 274 | 408 | 736 |
| 10 | `DELETE /resume/{email}/language/{language}/status` | vis | 44 | 0 | 200 |  | 2 | 37 | 8 | 10 | 299 | 546 | 224 | 471 | 736 |
| 10 | `GET /resume/{email}` | vis | 22 | 0 | 200 |  | 0 | 2006 | 8 | 10 | 97 | 145 | 93 | 93 | 736 |
| 10 | `HEAD /login/{email}/token` | jn | 22 | 0 | 200 |  | 0 | 0 | 8 | 10 | 77 | 108 | 114 | 190 | 292 |
| 10 | `POST /login/{email}` | jn | 22 | 0 | 200 |  | 34 | 193 | 10 | 10 | 1355 | 1954 | 119 | 190 | 292 |
| 10 | `POST /resume/{email}/language/{language}` | vis | 22 | 0 | 200 |  | 1935 | 1999 | 8 | 10 | 525 | 1312 | 355 | 471 | 736 |
| 10 | `POST /skills/fromText` | vis | 22 | 0 | 200 |  | 1949 | 1282 | 8 | 10 | 511 | 1278 | 317 | 397 | 736 |
| 50 | `DELETE /login/{email}/{sessionToken}` | jn | 108 | 0 | 200 |  | 2 | 0 | 39 | 50 | 1056 | 2412 | 111 | 171 | 292 |
| 50 | `DELETE /resume/{email}/language/{language}` | vis | 106 | 0 | 200 |  | 2 | 36 | 38 | 50 | 5525 | 13466 | 474 | 750 | 1280 |
| 50 | `DELETE /resume/{email}/language/{language}/status` | vis | 212 | 0 | 200 |  | 2 | 36 | 38 | 50 | 1415 | 5161 | 370 | 646 | 1064 |
| 50 | `GET /resume/{email}` | vis | 108 | 0 | 200 |  | 0 | 3553 | 39 | 50 | 880 | 1775 | 249 | 470 | 736 |
| 50 | `HEAD /login/{email}/token` | jn | 108 | 0 | 200 |  | 0 | 0 | 39 | 50 | 666 | 6708 | 120 | 206 | 292 |
| 50 | `POST /login/{email}` | jn | 108 | 0 | 200 |  | 34 | 192 | 50 | 50 | 8585 | 15091 | 140 | 206 | 292 |
| 50 | `POST /resume/{email}/language/{language}` | vis | 106 | 0 | 200 |  | 3556 | 3612 | 38 | 50 | 2468 | 4225 | 377 | 649 | 1280 |
| 50 | `POST /skills/fromText` | vis | 106 | 0 | 200 |  | 4159 | 2929 | 38 | 50 | 1963 | 4131 | 599 | 831 | 1280 |
| 100 | `DELETE /login/{email}/{sessionToken}` | jn | 216 | 61 | 0 200 | ECONNREFUSED:61 | 2 | 0 | 77 | 100 | 641 | 8138 | 158 | 219 | 292 |
| 100 | `DELETE /resume/{email}/language/{language}` | vis | 215 | 0 | 200 |  | 2 | 35 | 77 | 100 | 11628 | 34276 | 706 | 1347 | 1832 |
| 100 | `DELETE /resume/{email}/language/{language}/status` | vis | 430 | 0 | 200 |  | 2 | 35 | 77 | 100 | 3185 | 15464 | 656 | 1286 | 1832 |
| 100 | `GET /resume/{email}` | vis | 216 | 0 | 200 |  | 0 | 5069 | 77 | 100 | 973 | 2231 | 540 | 814 | 1280 |
| 100 | `HEAD /login/{email}/token` | jn | 216 | 0 | 200 |  | 0 | 0 | 77 | 100 | 1609 | 9160 | 123 | 214 | 292 |
| 100 | `POST /login/{email}` | jn | 216 | 0 | 200 |  | 34 | 191 | 100 | 100 | 19034 | 27892 | 130 | 218 | 292 |
| 100 | `POST /resume/{email}/language/{language}` | vis | 215 | 0 | 200 |  | 5047 | 5085 | 77 | 100 | 4243 | 8295 | 826 | 1357 | 1832 |
| 100 | `POST /skills/fromText` | vis | 215 | 133 | 0 200 | ECONNREFUSED:133 | 5037 | 1874 | 77 | 100 | 119 | 8117 | 1152 | 1401 | 1832 |

## Espera da escrita assíncrona

Tempo entre o fim de uma fase (todas as respostas recebidas) e o ES mostrar o que ela gravou.

| Clientes | Depois de | Itens | Espera (ms) | Convergiu |
|--:|---|--:|--:|---|
| 10 | login | 22 | 2159 | sim |
| 10 | inativar | 22 | 2747 | sim |
| 10 | reativar | 22 | 2789 | sim |
| 10 | excluir | 22 | 3777 | sim |
| 10 | reinserir | 22 | 2534 | sim |
| 50 | login | 108 | 1306 | sim |
| 50 | inativar | 106 | 10465 | sim |
| 50 | reativar | 106 | 15437 | sim |
| 50 | excluir | 106 | 15158 | sim |
| 50 | reinserir | 106 | 8136 | sim |
| 100 | login | 216 | 4714 | sim |
| 100 | inativar | 215 | 50654 | sim |
| 100 | reativar | 215 | 14858 | sim |
| 100 | excluir | 215 | 35320 | sim |
| 100 | reinserir | 215 | 39311 | sim |