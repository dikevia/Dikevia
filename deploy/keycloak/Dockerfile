FROM quay.io/keycloak/keycloak:26.8.2

COPY deploy/keycloak/realm-cfdt.render.json /opt/keycloak/data/import/realm-cfdt.json
COPY --chmod=0755 deploy/keycloak/dikevia-entrypoint.sh /opt/keycloak/dikevia-entrypoint.sh

ENV KC_DB=postgres \
    KC_FEATURES=stateless \
    KC_CACHE_EMBEDDED_CLUSTER_NAME=dikevia-build \
    KC_HEALTH_ENABLED=true \
    KC_METRICS_ENABLED=true \
    KC_HTTP_ENABLED=true \
    KC_PROXY_HEADERS=xforwarded \
    KC_HOSTNAME_STRICT=true \
    JAVA_OPTS_KC_HEAP="-XX:MaxRAMPercentage=30 -XX:InitialRAMPercentage=15"

# Build the optimized server image once, rather than augmenting it at every boot.
RUN /opt/keycloak/bin/kc.sh build --db=postgres --health-enabled=true --metrics-enabled=true --http-enabled=true --proxy-headers=xforwarded --http-management-health-enabled=false --features=stateless --cache-embedded-cluster-name=dikevia-build

EXPOSE 10000

ENTRYPOINT ["/opt/keycloak/dikevia-entrypoint.sh"]
CMD ["start", "--optimized", "--import-realm"]
