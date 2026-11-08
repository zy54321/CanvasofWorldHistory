# Runtime image from an existing signed/hashed Release JAR only. No credentials.
FROM eclipse-temurin:25-jre
USER root
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates && rm -rf /var/lib/apt/lists/* \
    && groupadd -g 10001 canvas && useradd --no-log-init -u 10001 -g 10001 -d /app -s /usr/sbin/nologin canvas
WORKDIR /app
COPY --chown=10001:10001 canvas-history-api.jar /app/app.jar
RUN mkdir -p /app/web && chown -R 10001:10001 /app/web
USER 10001:10001
EXPOSE 5180
HEALTHCHECK --interval=10s --timeout=5s --start-period=60s --retries=8 \
    CMD curl -fsS http://127.0.0.1:5180/api/v1/meta/health >/dev/null || exit 1
ENTRYPOINT ["java","-jar","/app/app.jar","--server.address=0.0.0.0","--server.port=5180","--spring.web.resources.static-locations=file:/app/web/,classpath:/static/"]
