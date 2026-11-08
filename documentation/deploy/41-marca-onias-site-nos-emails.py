# Marca "Onias.Site" no lugar de "JobsNow" nos e-mails aos usuarios: troca o texto do assunto e do corpo dos templates ja
# gravados em jn_email_template_message (token de login, curriculo salvo/desativado/reativado/excluido, e-mail aos
# recrutadores, convite aos candidatos legados e o rodape de JnEmailFooter). As mesmas trocas foram feitas nas sementes
# (JnEntityEmailTemplateMessage, VisEntityResume, VisEntityRecruiterResumes, JnEmailFooter), que so valem num reset.
# O convite aos legados diz "O JobsNow foi refeito e agora se chama Onias.Site": esse "JobsNow" fica. Varre todos os
# templates; o que nao tem "JobsNow" fica como esta, e rodar de novo nao muda nada. O cache das entidades (1 hora)
# segura o texto antigo ate expirar ou ate as APIs e os consumidores reiniciarem.
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python -X utf8 41-marca-onias-site-nos-emails.py [url]
#      sem url, usa o tunel de producao (http://127.0.0.1:9210); para o local, passe http://localhost:9200
import json
import os
import re
import sys
import urllib.parse
import urllib.request

BRAND = "Onias.Site"
# as frases que nao saem bem com a troca simples, antes da troca geral
SPECIFIC_REPLACEMENTS = (
    ("O JobsNow foi refeito, e o seu cadastro antigo", "O JobsNow foi refeito e agora se chama " + BRAND + ". O seu cadastro antigo"),
    ("JobsNow was rebuilt, and your old registration", "JobsNow was rebuilt and is now called " + BRAND + ". Your old registration"),
    ("cadastrado no site do JobsNow", "cadastrado no " + BRAND),
    ("registered on the JobsNow website", "registered on " + BRAND),
    ("acesso ao sistema JobsNow", "acesso ao " + BRAND),
    ("Token to access the JobsNow system", "Token to access " + BRAND),
    ("access the <a href='{accessLink}' target = '_blank'>JobsNow</a> system", "access <a href='{accessLink}' target = '_blank'>" + BRAND + "</a>"),
)
# o "JobsNow" que o convite aos legados mantem nao entra na troca geral
GENERAL_PATTERN = re.compile(r"JobsNow(?! foi refeito e agora| was rebuilt and is now)")


def rebrand(text):
    for old, new in SPECIFIC_REPLACEMENTS:
        text = text.replace(old, new)
    return GENERAL_PATTERN.sub(BRAND, text)


def main():
    url = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:9210"
    auth = os.environ.get("ES_DESTINO_AUTH", "")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    index = "jn_email_template_message"

    def call(method, path, body=None):
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(url + path, data=data, method=method)
        request.add_header("Content-Type", "application/json")
        if auth:
            request.add_header("Authorization", auth)
        with opener.open(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))

    print("cluster:", call("GET", "/")["cluster_name"])
    hits = call("POST", "/%s/_search" % index, {"size": 1000, "query": {"match_all": {}}})["hits"]["hits"]
    changed = 0
    for hit in hits:
        source = hit["_source"]
        changes = {}
        for field in ("subject", "message"):
            value = source.get(field)
            if not isinstance(value, str):
                continue
            new_value = rebrand(value)
            if new_value != value:
                changes[field] = new_value
        if not changes:
            continue
        name = "%s (%s)" % (source.get("templateId", "").rsplit("$", 1)[-1], source.get("language", ""))
        document_id = urllib.parse.quote(hit["_id"], safe="")
        call("POST", "/%s/_update/%s?refresh=true" % (index, document_id), {"doc": changes})
        changed += 1
        print("marca trocada:", name, sorted(changes))
    print("templates alterados:", changed)


if __name__ == "__main__":
    main()
