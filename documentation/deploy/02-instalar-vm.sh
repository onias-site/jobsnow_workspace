#!/usr/bin/env bash
# Itens B e C do deploy: Java 17, Node, PM2 e Elasticsearch 9.5.5 com seguranca ligada.
# Roda na VM, como root. A senha do usuario elastic chega no arquivo do primeiro argumento, que e apagado no fim.
# A porta 9200 escuta na rede privada e em localhost; quem limita o acesso e o firewall jobsnow-allow-elasticsearch.
# TLS no HTTP fica desligado: o trafego nao sai da VPC, e a aplicacao fala HTTP com Basic Auth.
set -euo pipefail

ES_VERSION=9.5.5
PASSWORD_FILE="$1"
export DEBIAN_FRONTEND=noninteractive

timedatectl set-timezone America/Sao_Paulo

apt-get update -qq
apt-get install -y -qq openjdk-17-jre-headless nodejs npm curl jq
npm install -g pm2 >/dev/null

id jobsnow >/dev/null 2>&1 || useradd --create-home --shell /bin/bash jobsnow
install -d -o jobsnow -g jobsnow /opt/jobsnow /opt/jobsnow/jars /opt/jobsnow/logs

if ! dpkg -s elasticsearch >/dev/null 2>&1; then
	cd /tmp
	curl -fsSLO "https://artifacts.elastic.co/downloads/elasticsearch/elasticsearch-${ES_VERSION}-amd64.deb"
	curl -fsSLO "https://artifacts.elastic.co/downloads/elasticsearch/elasticsearch-${ES_VERSION}-amd64.deb.sha512"
	sha512sum -c "elasticsearch-${ES_VERSION}-amd64.deb.sha512"
	dpkg -i "elasticsearch-${ES_VERSION}-amd64.deb" >/dev/null
	rm -f "elasticsearch-${ES_VERSION}-amd64.deb" "elasticsearch-${ES_VERSION}-amd64.deb.sha512"
fi

cat > /etc/elasticsearch/elasticsearch.yml <<'YML'
cluster.name: jobsnow-prd
node.name: jobsnow-vm
path.data: /var/lib/elasticsearch
path.logs: /var/log/elasticsearch
network.host: [_site_, _local_]
http.port: 9200
discovery.type: single-node
xpack.security.enabled: true
xpack.security.http.ssl.enabled: false
xpack.security.transport.ssl.enabled: false
ingest.geoip.downloader.enabled: false
YML

cat > /etc/elasticsearch/jvm.options.d/heap.options <<'HEAP'
-Xms3g
-Xmx3g
HEAP

# the password is the bootstrap one: it only takes effect before the security index exists
/usr/share/elasticsearch/bin/elasticsearch-keystore add -f -x bootstrap.password < "$PASSWORD_FILE"
for leftover in xpack.security.http.ssl.keystore.secure_password xpack.security.transport.ssl.keystore.secure_password xpack.security.transport.ssl.truststore.secure_password; do
	/usr/share/elasticsearch/bin/elasticsearch-keystore remove "$leftover" 2>/dev/null || true
done

systemctl daemon-reload
systemctl enable elasticsearch >/dev/null
systemctl restart elasticsearch

for attempt in $(seq 1 60); do
	code=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:9200 || true)
	if [ "$code" = "401" ]; then break; fi
	sleep 3
done

echo "sem senha: $(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:9200)"
AUTH_FILE=$(mktemp)
chmod 600 "$AUTH_FILE"
printf 'user = "elastic:%s"\n' "$(cat "$PASSWORD_FILE")" > "$AUTH_FILE"
curl -s --config "$AUTH_FILE" http://127.0.0.1:9200 | jq -r '"com senha: versao " + .version.number + ", cluster " + .cluster_name'
curl -s --config "$AUTH_FILE" http://127.0.0.1:9200/_cluster/health | jq -r '"status: " + .status'
rm -f "$AUTH_FILE"
shred -u "$PASSWORD_FILE"

env PATH="$PATH" pm2 startup systemd -u jobsnow --hp /home/jobsnow >/dev/null
systemctl enable pm2-jobsnow >/dev/null 2>&1 || true

echo "java: $(java -version 2>&1 | head -1)"
echo "pm2: $(pm2 --version)"
echo "fuso: $(timedatectl show -p Timezone --value)"
