#!/usr/bin/env bash
# Itens D, F e G do deploy: instala em /opt/jobsnow o que 07-publicar-na-vm.ps1 enviou e reinicia os consumidores.
# Roda na VM, como root. O primeiro argumento e a pasta temporaria do envio, apagada no fim. Sem jars na pasta, ficam os atuais.
set -euo pipefail

SOURCE="$1"
HOME_DIR=/opt/jobsnow

install -o jobsnow -g jobsnow -m 600 "$SOURCE/producao.json" "$HOME_DIR/application_properties.json"
install -o jobsnow -g jobsnow -m 640 "$SOURCE/ambiente.sh" "$HOME_DIR/ambiente.sh"
install -o jobsnow -g jobsnow -m 640 "$SOURCE/topicos.tsv" "$HOME_DIR/topicos.tsv"
install -o jobsnow -g jobsnow -m 640 "$SOURCE/05-consumidores.config.js" "$HOME_DIR/ecosystem.config.js"
install -o jobsnow -g jobsnow -m 750 "$SOURCE/05-iniciar-consumidores.sh" "$HOME_DIR/iniciar-consumidores.sh"
install -o jobsnow -g jobsnow -m 750 "$SOURCE/06-rodar-processo-diario.sh" "$HOME_DIR/rodar-processo-diario.sh"

for jar in consumidores cron; do
	if [ -f "$SOURCE/$jar.jar" ]; then
		install -o jobsnow -g jobsnow -m 640 "$SOURCE/$jar.jar" "$HOME_DIR/jars/$jar.jar"
	fi
done

shred -u "$SOURCE/producao.json"
rm -rf "$SOURCE"

sudo -u jobsnow -H env PM2_HOME=/home/jobsnow/.pm2 bash -c 'cd /opt/jobsnow && pm2 startOrRestart ecosystem.config.js >/dev/null && pm2 save >/dev/null'
sleep 40
sudo -u jobsnow -H env PM2_HOME=/home/jobsnow/.pm2 pm2 jlist | jq -r '.[] | "\(.name): \(.pm2_env.status), reinicios \(.pm2_env.restart_time)"'
