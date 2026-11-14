# Imagem do reenvio diario do token de login (Cloud Run Job jobsnow-reenvio-token-login, criado por
# 54-reenvio-do-token-de-login-no-cloud-run.ps1). Mesmo cron.jar do processo diario, outro processo:
# JsBusinessDailyLoginTokenProcess (JsBusinessResendLoginTokenToUsersWithoutPassword e, logo depois,
# JsBusinessSaveTokensResentWithoutPassword). As propriedades chegam pela variavel application_properties.
FROM eclipse-temurin:17-jre
WORKDIR /app
COPY app.jar app.jar
ENTRYPOINT ["java", "-XX:MaxRAMPercentage=75", "-jar", "app.jar", "com.js.business.login.JsBusinessDailyLoginTokenProcess", "{\"mensageriaReceiver\":\"com.jn.mensageria.JnMensageriaReceiver\",\"operation\":\"\"}"]
