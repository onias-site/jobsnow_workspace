# Imagem do processo diario (Cloud Run Job jobsnow-processo-diario, criado por 32-processo-diario-no-cloud-run.ps1).
# O contexto do build traz so o cron.jar; o comando e o mesmo de 06-rodar-processo-diario.sh, e as propriedades chegam
# pela variavel application_properties (segredo jobsnow-application-properties), como nas APIs.
# Envio de curriculos aos recrutadores liberado em 2026-11-15 (de 2026-11-14 a 2026-11-15 o campo
# "resumesToRecruitersLocked":true na entrada travava o envio e o processo fazia so expurgo e backup).
FROM eclipse-temurin:17-jre
WORKDIR /app
COPY app.jar app.jar
# Desde 2026-11-17 a mesma imagem serve a dois jobs: o processo (a classe) e a entrada JSON vem nos args de cada job
# (32-processo-diario-no-cloud-run.ps1): jobsnow-processo-diario (backup, 00:10) e jobsnow-curriculos-aos-recrutadores
# (e-mail de curriculos aos recrutadores, 10:00).
ENTRYPOINT ["java", "-XX:MaxRAMPercentage=75", "-jar", "app.jar"]
