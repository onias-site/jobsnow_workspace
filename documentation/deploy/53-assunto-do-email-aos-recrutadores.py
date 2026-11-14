# Novo assunto do e-mail de curriculos aos recrutadores (VisNotifyRecruiterAboutResumes): o total de curriculos, as 5
# habilidades de melhor ranking de todos os curriculos do e-mail e quantas outras habilidades distintas sobram. Os
# placeholders sao resolvidos pelo JnMessageType.email (o assunto passou a ser template, como a mensagem) com os valores
# postos por VisBusinessSendResumesToRecruiters.sendTheEmail. Os textos abaixo sao copia dos de
# VisEntityRecruiterResumes.java; mudou la, muda aqui. Exige o deploy da vis e do cron com o JnMessageType novo: sem ele,
# o assunto sai com as chaves cruas.
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python -X utf8 53-assunto-do-email-aos-recrutadores.py [url]
#      sem url, usa o tunel de producao (http://127.0.0.1:9210); para o local, passe http://localhost:9200
import json
import os
import sys
import urllib.parse
import urllib.request

url = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:9210"
auth = os.environ.get("ES_DESTINO_AUTH", "")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
index = "jn_email_template_message"
template_id = "com.vis.messages.VisMessages$VisNotifyRecruiterAboutResumes"
subjects = {
    "portuguese": "{totalOfResumes} currículos de {topSkills} e mais outras {otherSkills} habilidades gratuitos pra você!!!",
    "english": "{totalOfResumes} resumes of {topSkills} and {otherSkills} other skills for free for you!!!",
}


def call(method, path, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if auth:
        request.add_header("Authorization", auth)
    with opener.open(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


print("cluster:", call("GET", "/")["cluster_name"])
query = {"size": 100, "query": {"term": {"templateId": template_id}}}
hits = call("POST", "/%s/_search" % index, query)["hits"]["hits"]
if not hits:
    hits = [h for h in call("POST", "/%s/_search" % index, {"size": 1000, "query": {"match_all": {}}})["hits"]["hits"]
            if h["_source"].get("templateId") == template_id]
changed = 0
for hit in hits:
    source = hit["_source"]
    language = source.get("language", "")
    if language not in subjects:
        print("idioma desconhecido, ficou como esta:", language)
        continue
    subject = subjects[language]
    if source.get("subject") == subject:
        print("ja tem o assunto novo:", language)
        continue
    document_id = urllib.parse.quote(hit["_id"], safe="")
    call("POST", "/%s/_update/%s?refresh=true" % (index, document_id), {"doc": {"subject": subject}})
    changed += 1
    print("assunto trocado:", language)
print("templates alterados:", changed)
