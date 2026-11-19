"""Monta a abertura do e-mail (HTML) a partir do texto da vaga: a frase fixa e, abaixo, a vaga com as quebras de linha.
Uso: python -X utf8 -I montar-abertura.py <arquivo da vaga> <arquivo html de saida>
"""
import html
import sys

with open(sys.argv[1], encoding="utf-8-sig") as file:
    job = file.read().strip()
job_html = "<br/>".join(html.escape(line) for line in job.splitlines())
intro = "<p>Boa tarde, abaixo a lista de curriculos para a vaga que você me enviou a pouco <br/>" + job_html + "</p>"
with open(sys.argv[2], "w", encoding="utf-8") as file:
    file.write(intro)
print("abertura:", len(intro), "caracteres")
