FROM quay.io/keycloak/keycloak:26.8.2

COPY deploy/keycloak/realm-cfdt.render.json /opt/keycloak/data/import/realm-cfdt.json

ENV KC_DB=postgres \
    KC_HEALTH_ENABLED=true \
    KC_METRICS_ENABLED=true \
    KC_HTTP_ENABLED=true \
    KC_PROXY_HEADERS=xforwarded \
    KC_HOSTNAME_STRICT=true \
    JAVA_OPTS_KC_HEAP="-XX:MaxRAMPercentage=40 -XX:InitialRAMPercentage=20"

# Build the optimized server image once, rather than augmenting it at every boot.
RUN /opt/keycloak/bin/kc.sh build --db=postgres --health-enabled=true --metrics-enabled=true --http-enabled=true --proxy-headers=xforwarded

ENTRYPOINT ["/opt/keycloak/bin/kc.sh"]
CMD ["start", "--optimized", "--import-realm"]
