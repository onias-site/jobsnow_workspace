# Imagem das APIs vis e js no Cloud Run. O contexto do build traz so o jar, gerado antes por mvn install.
FROM eclipse-temurin:17-jre
WORKDIR /app
COPY app.jar app.jar
ENTRYPOINT ["java", "-XX:MaxRAMPercentage=75", "-Dspring.devtools.restart.enabled=false", "-jar", "app.jar"]
