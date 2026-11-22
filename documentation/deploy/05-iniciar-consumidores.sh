#!/usr/bin/env bash
# Itens B e F do deploy: o processo que o PM2 mantem no ar. Copiado para /opt/jobsnow/iniciar-consumidores.sh.
set -euo pipefail
source /opt/jobsnow/ambiente.sh
exec java -Xms512m -Xmx1536m -XX:+ExitOnOutOfMemoryError -jar /opt/jobsnow/jars/consumidores.jar /opt/jobsnow/topicos.tsv
