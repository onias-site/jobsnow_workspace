# Ligar o domínio da KingHost ao GCP

Roteiro escrito em 2026-11-01. Troque `seudominio.com.br` pelo domínio real.

O domínio continua na KingHost: não é preciso transferi-lo nem trocar os nameservers. Basta criar registros DNS lá apontando para um IP fixo do GCP. Assim, o e-mail e os outros registros do domínio continuam funcionando.

**Decisão: usar um Application Load Balancer externo global, não o domain mapping do Cloud Run.** O domain mapping é mais simples, mas está em preview, a própria documentação diz que não é pronto para produção, e São Paulo (`southamerica-east1`) não está na lista de regiões dele. O load balancer tem custo mensal fixo, mesmo sem tráfego; confira o valor na calculadora do GCP.

## Passo a passo

Os comandos supõem que o front (`jobsnow-front`) também rode no Cloud Run; se ele ficar em outro lugar, retire-o do roteiro.

**1. Publique os serviços no Cloud Run.** Repita para `jobsnow-vis` e `jobsnow-js` (porta 8082), com a imagem de cada um:

```powershell
gcloud run deploy jobsnow-vis --image=IMAGEM --region=southamerica-east1 --port=8081 --allow-unauthenticated --ingress=internal-and-cloud-load-balancing
```

**2. Reserve o IP fixo e anote o endereço:**

```powershell
gcloud compute addresses create jobsnow-ip --global --ip-version=IPV4
gcloud compute addresses describe jobsnow-ip --global --format="value(address)"
```

**3. Crie o NEG e o backend.** Repita para cada um dos três serviços (`front`, `vis` e `js`):

```powershell
gcloud compute network-endpoint-groups create jobsnow-vis-neg --region=southamerica-east1 --network-endpoint-type=serverless --cloud-run-service=jobsnow-vis
gcloud compute backend-services create jobsnow-vis-bs --global --load-balancing-scheme=EXTERNAL_MANAGED
gcloud compute backend-services add-backend jobsnow-vis-bs --global --network-endpoint-group=jobsnow-vis-neg --network-endpoint-group-region=southamerica-east1
```

**4. Crie o roteamento por subdomínio:**

```powershell
gcloud compute url-maps create jobsnow-lb --default-service=jobsnow-front-bs
gcloud compute url-maps add-path-matcher jobsnow-lb --path-matcher-name=vis --default-service=jobsnow-vis-bs --new-hosts=api.seudominio.com.br
gcloud compute url-maps add-path-matcher jobsnow-lb --path-matcher-name=js --default-service=jobsnow-js-bs --new-hosts=login.seudominio.com.br
```

**5. Crie o certificado gerenciado e a entrada HTTPS:**

```powershell
gcloud compute ssl-certificates create jobsnow-cert --global --domains=seudominio.com.br,www.seudominio.com.br,api.seudominio.com.br,login.seudominio.com.br
gcloud compute target-https-proxies create jobsnow-proxy --url-map=jobsnow-lb --ssl-certificates=jobsnow-cert
gcloud compute forwarding-rules create jobsnow-https --global --load-balancing-scheme=EXTERNAL_MANAGED --address=jobsnow-ip --target-https-proxy=jobsnow-proxy --ports=443
```

**6. Crie os registros na zona DNS da KingHost:**

| Tipo | Nome | Valor |
|---|---|---|
| A | `@` (raiz do domínio) | IP do passo 2 |
| A | `www` | IP do passo 2 |
| A | `api` | IP do passo 2 |
| A | `login` | IP do passo 2 |

Se já existir um registro A para esses nomes, substitua-o. Não mexa nos registros MX nem nos TXT. A documentação da KingHost não foi encontrada, então o caminho exato no painel não está confirmado; procure por "Zona DNS" ou "Editar DNS".

**7. Aguarde o certificado.** Ele só é emitido depois que o DNS estiver apontando para o IP, e isso pode levar de minutos a horas. Acompanhe até aparecer `ACTIVE`:

```powershell
gcloud compute ssl-certificates describe jobsnow-cert --global --format="value(managed.status,managed.domainStatus)"
```

**8. Redirecione HTTP para HTTPS.** Esse redirecionamento precisa de um url-map, um proxy HTTP e uma regra na porta 80, todos separados. Sem eles, `http://seudominio.com.br` não responde.

## O que falta no projeto

- **Imagens:** não há Dockerfile para as APIs Java, e o do front (`jn_frontend_calistrato-react/Dockerfile`) sobe um PostgreSQL, não o Next.js.
- **URLs fixas no front:** há `http://localhost:8081` e `8082` no código, como em `app/JnAjax.js:510` e `presentation/pages/recrutador/ViewResumeFromEmail.tsx:65`. Elas precisam passar para `api.` e `login.`.
- **CORS:** front e APIs ficarão em subdomínios diferentes, então os dois domínios de API precisam aceitar a origem do site. A configuração atual de CORS ainda não foi verificada.
- **Elasticsearch:** hoje ele é local, e o Cloud Run precisa alcançá-lo em um servidor próprio ou gerenciado, de preferência em São Paulo.
- **Arquivos em `c:/logs`:** logs e marcas de cache e mensageria são gravados lá. O disco do Cloud Run é temporário e não é compartilhado entre instâncias, então as marcas de cache e mensageria precisam de outra solução.
- **Região de São Paulo:** a documentação lista São Paulo como região do Cloud Run, mas não foi encontrada confirmação explícita dela com NEG serverless. O passo 3 mostra isso: se a região não for aceita, o comando falha logo.
- **Processo diário:** o `VisBusinessDailyScheduledProcess` precisa rodar uma vez por dia fora da máquina local, e pode usar o Cloud Scheduler nessa mesma estrutura.

## Fontes

- [Map custom domains – Cloud Run](https://docs.cloud.google.com/run/docs/mapping-custom-domains)
- [Cloud Run locations](https://docs.cloud.google.com/run/docs/locations)
- [Cloud Run known issues](https://docs.cloud.google.com/run/docs/known-issues)
- [Global external Application Load Balancer com Cloud Run](https://docs.cloud.google.com/load-balancing/docs/https/setup-global-ext-https-serverless)
