FROM quay.io/keycloak/keycloak:26.8.2
COPY deploy/keycloak/realm-cfdt.render.json /opt/keycloak/data/import/realm-cfdt.json
ENV KC_HEALTH_ENABLED=true KC_METRICS_ENABLED=true KC_HTTP_ENABLED=true KC_PROXY_HEADERS=xforwarded KC_HOSTNAME_STRICT=true
ENTRYPOINT ["/opt/keycloak/bin/kc.sh"]
CMD ["start","--import-realm"]
