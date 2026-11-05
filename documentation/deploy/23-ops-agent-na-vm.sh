#!/bin/bash
# Instala (ou reconfigura) o Ops Agent na jobsnow-vm: logs do Elasticsearch e dos consumidores do PM2 no Cloud Logging,
# alem das metricas da VM (memoria, disco, processos) no Cloud Monitoring. Pode rodar de novo.
# Roda na VM, como usuario com sudo. Daqui:
#   gcloud compute scp 23-ops-agent-na-vm.sh jobsnow-vm:/tmp/ --zone southamerica-east1-a --project jobsnow-prd --tunnel-through-iap
#   gcloud compute ssh jobsnow-vm --zone southamerica-east1-a --project jobsnow-prd --tunnel-through-iap --command "bash /tmp/23-ops-agent-na-vm.sh"
# Permissoes da conta da VM (jobsnow-vm@): roles/logging.logWriter para os logs e roles/monitoring.metricWriter para as
# metricas (concessao feita pelo administrador).
# Desde 2026-11-04 tambem o log mensagens: uma linha JSON por mensagem processada pelos consumidores
# (/opt/jobsnow/logs/mensagens.jsonl, gravada por CcpPubSubWriteMessageLog), enviada como campos (jsonPayload) e lida
# pelo painel 31-mensagens-das-filas.py. O logrotate guarda 4 semanas dela na VM.
# Desde 2026-11-05 os slowlogs do Elasticsearch saem do log elasticsearch para o log elasticsearch_slowlog, com cada
# linha JSON enviada como campos (jsonPayload."trace.id", jsonPayload."elasticsearch.slowlog.id", took etc.), lidos
# pelos paineis 27 e 29 para medir cada query por dentro do Elasticsearch. O slowlog so registra todas as queries
# enquanto o 33-slowlog-de-todas-as-queries.py estiver ligado.
set -euo pipefail

if ! systemctl list-unit-files | grep -q '^google-cloud-ops-agent.service'; then
	cd /tmp
	curl -sSfO https://dl.google.com/cloudagents/add-google-cloud-ops-agent-repo.sh
	sudo bash add-google-cloud-ops-agent-repo.sh --also-install
fi

# O gc.log do Elasticsearch fica de fora: e grande e so interessa numa investigacao de memoria, feita na propria VM.
sudo tee /etc/google-cloud-ops-agent/config.yaml > /dev/null <<'EOF'
logging:
  receivers:
    elasticsearch:
      type: files
      include_paths:
      - /var/log/elasticsearch/jobsnow-prd.log
      - /var/log/elasticsearch/jobsnow-prd_deprecation.json
    elasticsearch_slowlog:
      type: files
      include_paths:
      - /var/log/elasticsearch/jobsnow-prd_index_search_slowlog.json
      - /var/log/elasticsearch/jobsnow-prd_index_indexing_slowlog.json
    consumidores:
      type: files
      include_paths:
      - /opt/jobsnow/logs/*.log
    mensagens:
      type: files
      include_paths:
      - /opt/jobsnow/logs/mensagens.jsonl
  processors:
    pilhas_java:
      type: parse_multiline
      match_any:
      - type: language_exceptions
        language: java
    linha_json:
      type: parse_json
  service:
    pipelines:
      elasticsearch:
        receivers: [elasticsearch]
        processors: [pilhas_java]
      elasticsearch_slowlog:
        receivers: [elasticsearch_slowlog]
        processors: [linha_json]
      consumidores:
        receivers: [consumidores]
        processors: [pilhas_java]
      mensagens:
        receivers: [mensagens]
        processors: [linha_json]
EOF

sudo tee /etc/logrotate.d/jobsnow-mensagens > /dev/null <<'EOF'
/opt/jobsnow/logs/mensagens.jsonl {
	weekly
	rotate 4
	compress
	missingok
	notifempty
	copytruncate
}
EOF

sudo systemctl restart google-cloud-ops-agent
sleep 5
systemctl is-active google-cloud-ops-agent google-cloud-ops-agent-fluent-bit google-cloud-ops-agent-opentelemetry-collector
free -m | head -2
