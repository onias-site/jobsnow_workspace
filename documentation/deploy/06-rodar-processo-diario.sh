#!/usr/bin/env bash
# Item G do deploy: roda o unico processo agendado. Copiado para /opt/jobsnow/rodar-processo-diario.sh.
set -euo pipefail
source /opt/jobsnow/ambiente.sh
exec java -Xms128m -Xmx512m -jar /opt/jobsnow/jars/cron.jar \
	com.vis.business.scheduled.VisBusinessDailyScheduledProcess \
	'{"mensageriaReceiver":"com.jn.mensageria.JnMensageriaReceiver","operation":""}'
