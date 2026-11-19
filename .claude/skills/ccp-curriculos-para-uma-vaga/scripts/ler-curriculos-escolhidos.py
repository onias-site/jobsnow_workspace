"""So leitura: roda o ler-curriculos-de-producao.py do repositorio (o mesmo do e-mail a um recrutador) trocando so o
filtro dos curriculos: em vez de tirar restritos e LinkedIn invalido, ficam os curriculos cujo linkedinAddress esta no
arquivo de LinkedIns (um por linha). Assim os dados lidos seguem sempre os do leitor oficial.
Rodar por com-tunel-de-producao.ps1: -Script este -Argumentos <arquivo de LinkedIns>,<arquivo de saida>
"""
import sys

READER = r"C:\eclipse-workspaces\ccp\documentation\roteiros-de-teste\automacao\ler-curriculos-de-producao.py"
OLD_FILTER = """resumes = [resume for resume in resumes
           if resume.get("email") not in restricted_emails and resume.get("invalidLinkedinAddress") is not True]"""
NEW_FILTER = """resumes = [resume for resume in resumes if (resume.get("linkedinAddress") or "").strip() in CHOSEN]"""

with open(sys.argv[1], encoding="utf-8-sig") as file:
    chosen = {line.strip() for line in file if line.strip()}
with open(READER, encoding="utf-8") as file:
    source = file.read()
if source.count(OLD_FILTER) != 1:
    raise SystemExit("o filtro do ler-curriculos-de-producao.py mudou: atualize ler-curriculos-escolhidos.py")
sys.argv = [READER, sys.argv[2]]
exec(compile(source.replace(OLD_FILTER, NEW_FILTER), READER, "exec"), {"__name__": "__main__", "CHOSEN": chosen})
