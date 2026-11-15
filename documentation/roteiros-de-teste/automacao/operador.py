"""Operador do bot de suporte no ambiente local, pelo caminho da produção (desde 2026-11-15).

Monta um update do Telegram com o texto pedido, entrega no webhook da API js local
(POST http://localhost:8082/telegram-webhook/<bot>, com o header do segredo do bot lido da variável
application_properties, sem exibi-lo), espera a fila terminar (marcas em c:/logs/mensageria/running,
que o consumidor push da porta 8083 remove ao acabar) e mostra o que o bot respondeu no "Telegram" local
(c:/logs/telegram/<bot>-<chat>.txt).

Precisa no ar: Elasticsearch local, API js (8082) e consumidor push (8083).

Uso: python -X utf8 operador.py "/pendingTickets" [--bot support] [--chat 751717896]

No Git Bash, prefixe com MSYS_NO_PATHCONV=1: sem isso o "/pendingTickets" chega como
"C:/Program Files/Git/pendingTickets" e o bot responde só a lista de comandos.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

RUNNING_FOLDER = "c:/logs/mensageria/running"
TELEGRAM_FOLDER = "c:/logs/telegram"
WEBHOOK_URL = "http://localhost:8082/telegram-webhook/"
OPERATOR_CHAT = 751717896
WAIT_SECONDS = 60


def secret_of(bot):
    properties = json.loads(os.environ["application_properties"])
    return properties["telegramWebhookSecrets"][bot]


def telegram_update(text, chat):
    now = int(time.time())
    return {
        "update_id": now,
        "message": {
            "message_id": now,
            "date": now,
            "text": text,
            "from": {"id": chat, "is_bot": False, "first_name": "Operador", "language_code": "pt-br"},
            "chat": {"id": chat, "type": "private", "first_name": "Operador"},
        },
    }


def running_after(start_millis):
    if not os.path.isdir(RUNNING_FOLDER):
        return False
    for name in os.listdir(RUNNING_FOLDER):
        published = name.split("-", 1)[0]
        if published.isdigit() and int(published) >= start_millis:
            return True
    return False


def size_of(path):
    return os.path.getsize(path) if os.path.exists(path) else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("text")
    parser.add_argument("--bot", default="support")
    parser.add_argument("--chat", type=int, default=OPERATOR_CHAT)
    args = parser.parse_args()

    answers_file = f"{TELEGRAM_FOLDER}/{args.bot}-{args.chat}.txt"
    size_before = size_of(answers_file)
    start_millis = int(time.time() * 1000)

    body = json.dumps(telegram_update(args.text, args.chat)).encode("utf-8")
    request = urllib.request.Request(WEBHOOK_URL + args.bot, data=body, method="POST")
    request.add_header("Content-Type", "application/json")
    request.add_header("X-Telegram-Bot-Api-Secret-Token", secret_of(args.bot))
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            print(f"webhook: HTTP {response.status}")
    except urllib.error.HTTPError as error:
        print(f"webhook: HTTP {error.code} {error.read().decode('utf-8', 'replace')[:500]}")
        sys.exit(1)

    time.sleep(1)
    deadline = time.time() + WAIT_SECONDS
    while running_after(start_millis) and time.time() < deadline:
        time.sleep(0.5)
    if running_after(start_millis):
        print(f"a fila ainda roda depois de {WAIT_SECONDS} s")

    with open(answers_file, encoding="utf-8", errors="replace") as answers:
        answers.seek(size_before)
        reply = answers.read().strip()
    print("resposta do bot:")
    print(reply if reply else "(nenhuma)")


if __name__ == "__main__":
    main()
