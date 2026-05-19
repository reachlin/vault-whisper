FROM eclipse-temurin:21-jre-alpine

WORKDIR /mc

# Accept EULA at build time so the server starts without manual intervention
RUN echo "eula=true" > eula.txt

EXPOSE 25565

# server.jar is bind-mounted from the host data/ directory at runtime
ENTRYPOINT ["java", "-Xmx2G", "-Xms512M", "-jar", "server-1.21.4.jar", "--nogui"]
