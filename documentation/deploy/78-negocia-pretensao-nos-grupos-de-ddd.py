# Pizza "Negocia pretensao salarial" da tela estatisticas/ofertaXdemanda (2026-11-14): o campo negotiableClaim entrou
# no child dos grupos de ddd dos curriculos (vis_virtual_ddd_grouper, jn_grouper e jn_inactive_grouper) e das
# visualizacoes (vis_virtual_viewed_resume_ddd_grouper, jn_grouper). Depois do deploy da vis e dos consumidores, cada
# escrita ja grava o campo; os children ja gravados so o ganham por esta carga, que roda de novo os scripts 57 e 58
# (idempotentes: recalculam cada grupo do zero a partir de vis_resume / vis_inactive_resume / vis_viewed_resume, agora
# com negotiableClaim em CHILD_FIELDS). Sem a carga, os curriculos antigos caem na fatia "Nao informado".
# Rodar logo depois do deploy da vis e dos consumidores.
# Uso: powershell -File com-tunel-de-producao.ps1 -Script 78-negocia-pretensao-nos-grupos-de-ddd.py
#      ou: ES_DESTINO_AUTH=<valor> python 78-negocia-pretensao-nos-grupos-de-ddd.py [destino]
# Imprime so contagens (as dos scripts 57 e 58).
import os
import runpy
import sys

folder = os.path.dirname(os.path.abspath(__file__))
failures = 0
for script in ["57-grupos-de-ddd-dos-curriculos.py", "58-grupos-de-ddd-das-visualizacoes.py"]:
    print("==", script)
    try:
        runpy.run_path(os.path.join(folder, script), run_name="__main__")
    except SystemExit as exit_status:
        if exit_status.code not in (0, None):
            failures += 1
            print("falhou:", script, exit_status.code)

print("OK" if failures == 0 else f"FALHAS: {failures}")
sys.exit(0 if failures == 0 else 1)
