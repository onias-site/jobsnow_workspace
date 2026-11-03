// Itens B e F do deploy: o PM2 mantem os consumidores pull no ar. Copiado para /opt/jobsnow/ecosystem.config.js.
// application_properties vem de /opt/jobsnow/ambiente.sh, carregado por iniciar-consumidores.sh, e nao entra no ambiente guardado pelo PM2.
module.exports = {
	apps: [
		{
			name: 'jobsnow-consumidores',
			script: '/opt/jobsnow/iniciar-consumidores.sh',
			interpreter: '/bin/bash',
			cwd: '/opt/jobsnow',
			autorestart: true,
			restart_delay: 10000,
			out_file: '/opt/jobsnow/logs/consumidores-out.log',
			error_file: '/opt/jobsnow/logs/consumidores-err.log',
		},
	],
};
