# Carga concorrente sobre os currículos

Níveis pedidos: 10, 50, 100, 250, 500, 1000 clientes simultâneos. Requisições: 7559.

| Clientes | Endpoint | API | Req. | Erros | Status | Entrada méd. (B) | Saída méd. (B) | Em voo méd. | Em voo máx. | p50 (ms) | p95 (ms) | Heap méd. (MB) | Heap máx. (MB) | Heap total (MB) |
|--:|---|---|--:|--:|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 1 | `HEAD /login/{email}/token` | jn | 6 | 0 | 200 | 0 | 0 | 1 | 1 | 31 | 38 | 205 | 235 | 452 |
| 1 | `POST /login/{email}` | jn | 6 | 0 | 200 | 34 | 194 | 1 | 1 | 1544 | 1577 | 218 | 243 | 452 |
| 1 | `POST /resume/{email}/language/{language}` | vis | 6 | 0 | 200 | 4081 | 4144 | 1 | 1 | 1525 | 2803 | 1320 | 1738 | 2220 |
| 10 | `DELETE /login/{email}/{sessionToken}` | jn | 22 | 0 | 200 | 2 | 0 | 8 | 10 | 348 | 358 | 42 | 46 | 80 |
| 10 | `DELETE /resume/{email}/language/{language}` | vis | 22 | 0 | 200 | 2 | 37 | 8 | 10 | 1246 | 2882 | 118 | 204 | 292 |
| 10 | `DELETE /resume/{email}/language/{language}/status` | vis | 44 | 0 | 200 | 2 | 37 | 8 | 10 | 1865 | 3837 | 112 | 200 | 292 |
| 10 | `GET /resume/{email}` | vis | 22 | 0 | 200 | 0 | 2006 | 8 | 10 | 508 | 952 | 129 | 140 | 292 |
| 10 | `HEAD /login/{email}/token` | jn | 22 | 0 | 200 | 0 | 0 | 8 | 10 | 84 | 119 | 40 | 58 | 80 |
| 10 | `POST /login/{email}` | jn | 22 | 0 | 200 | 34 | 193 | 10 | 10 | 1506 | 2678 | 45 | 58 | 80 |
| 10 | `POST /resume/{email}/language/{language}` | vis | 22 | 0 | 200 | 1935 | 1999 | 8 | 10 | 1548 | 2802 | 122 | 186 | 292 |
| 10 | `POST /skills/fromText` | vis | 22 | 0 | 200 | 1949 | 1282 | 8 | 10 | 150 | 342 | 60 | 85 | 292 |
| 50 | `DELETE /login/{email}/{sessionToken}` | jn | 108 | 0 | 200 | 2 | 0 | 39 | 50 | 788 | 1462 | 113 | 184 | 312 |
| 50 | `DELETE /resume/{email}/language/{language}` | vis | 106 | 0 | 200 | 2 | 36 | 38 | 50 | 5015 | 7134 | 380 | 697 | 1144 |
| 50 | `DELETE /resume/{email}/language/{language}/status` | vis | 212 | 0 | 200 | 2 | 36 | 38 | 50 | 7407 | 13793 | 272 | 726 | 1144 |
| 50 | `GET /resume/{email}` | vis | 108 | 0 | 200 | 0 | 3553 | 39 | 50 | 788 | 1159 | 97 | 141 | 292 |
| 50 | `HEAD /login/{email}/token` | jn | 108 | 0 | 200 | 0 | 0 | 39 | 50 | 619 | 1321 | 63 | 92 | 116 |
| 50 | `POST /login/{email}` | jn | 108 | 0 | 200 | 34 | 192 | 49 | 50 | 7415 | 11778 | 71 | 96 | 116 |
| 50 | `POST /resume/{email}/language/{language}` | vis | 106 | 0 | 200 | 3556 | 3612 | 38 | 50 | 6797 | 9717 | 511 | 735 | 1144 |
| 50 | `POST /skills/fromText` | vis | 106 | 0 | 200 | 4159 | 2929 | 38 | 50 | 773 | 1588 | 432 | 639 | 1144 |
| 100 | `DELETE /login/{email}/{sessionToken}` | jn | 216 | 0 | 200 | 2 | 0 | 77 | 100 | 1320 | 2542 | 176 | 231 | 312 |
| 100 | `DELETE /resume/{email}/language/{language}` | vis | 215 | 0 | 200 | 2 | 35 | 77 | 100 | 20587 | 34967 | 891 | 1493 | 2220 |
| 100 | `DELETE /resume/{email}/language/{language}/status` | vis | 430 | 0 | 200 | 2 | 35 | 77 | 100 | 32429 | 60934 | 779 | 1458 | 2220 |
| 100 | `GET /resume/{email}` | vis | 216 | 0 | 200 | 0 | 5069 | 77 | 100 | 1051 | 1785 | 419 | 617 | 1144 |
| 100 | `HEAD /login/{email}/token` | jn | 216 | 0 | 200 | 0 | 0 | 77 | 100 | 1396 | 2854 | 116 | 238 | 312 |
| 100 | `POST /login/{email}` | jn | 216 | 0 | 200 | 34 | 191 | 99 | 100 | 14901 | 19050 | 169 | 238 | 312 |
| 100 | `POST /resume/{email}/language/{language}` | vis | 215 | 0 | 200 | 5047 | 5085 | 77 | 100 | 26826 | 47543 | 885 | 1526 | 2220 |
| 100 | `POST /skills/fromText` | vis | 215 | 0 | 200 | 5037 | 4541 | 77 | 100 | 1813 | 4746 | 903 | 1458 | 2220 |
| 250 | `DELETE /login/{email}/{sessionToken}` | jn | 457 | 0 | 200 | 2 | 0 | 182 | 250 | 3556 | 7148 | 220 | 317 | 452 |
| 250 | `DELETE /resume/{email}/language/{language}` | vis | 455 | 39 | 0 200 | 2 | 33 | 182 | 250 | 28508 | 44876 | 1014 | 1658 | 2220 |
| 250 | `DELETE /resume/{email}/language/{language}/status` | vis | 910 | 49 | 0 200 | 2 | 34 | 182 | 250 | 37458 | 74830 | 944 | 1643 | 2220 |
| 250 | `GET /resume/{email}` | vis | 457 | 0 | 200 | 0 | 3366 | 182 | 250 | 2199 | 3827 | 739 | 1472 | 2220 |
| 250 | `HEAD /login/{email}/token` | jn | 541 | 113 | 0 200 | 0 | 0 | 173 | 250 | 1651 | 7640 | 187 | 261 | 312 |
| 250 | `POST /login/{email}` | jn | 541 | 113 | 0 200 | 34 | 152 | 222 | 250 | 36216 | 47506 | 189 | 301 | 376 |
| 250 | `POST /login/{email}/password` | jn | 113 | 4 | 0 200 422 | 87 | 2144 | 213 | 250 | 9487 | 56072 | 215 | 255 | 312 |
| 250 | `POST /login/{email}/token/language/{language}` | jn | 113 | 80 | 0 429 | 2 | 62 | 250 | 250 | 2151 | 2593 | 184 | 228 | 312 |
| 250 | `POST /resume/{email}/language/{language}` | vis | 497 | 48 | 0 200 | 3323 | 3039 | 187 | 250 | 42326 | 78125 | 1065 | 1724 | 2220 |
| 250 | `POST /skills/fromText` | vis | 358 | 104 | 0 200 | 4396 | 2213 | 163 | 250 | 1975 | 3865 | 1076 | 1709 | 2220 |