# Keycloak administrator recovery

## Current deployment facts

- The deployed Keycloak version is 26.8.2.
- The Render service uses a persistent PostgreSQL database and the `master` realm has already been initialized.
- `KC_BOOTSTRAP_ADMIN_USERNAME` and `KC_BOOTSTRAP_ADMIN_PASSWORD` are first-start bootstrap settings. They do **not** recreate an administrator in an already initialized `master` realm.
- The runtime entrypoint must not claim that a permanent Dikévia administrator exists unless that has been verified against the live realm.

## Supported recovery mechanism

Keycloak 26 provides the dedicated `bootstrap-admin user` recovery command. It creates a **temporary** administrator in the `master` realm. It is not a permanent founder-account provisioning mechanism.

Important safety requirements from the Keycloak recovery guide:

1. Stop **all** Keycloak nodes connected to this database before running the recovery command. Do not run it concurrently with a live Keycloak node.
2. Run it in a controlled one-off maintenance environment using the same Keycloak version and the same database configuration as the service.
3. Supply a one-time recovery username and password through protected environment variables. Never put secrets in shell history, source files, CI logs, or chat.
4. Use the optimized server configuration when invoking the recovery command.
5. Start Keycloak again and verify that the temporary account can access the `master` Admin Console.
6. Create and test the intended permanent administrator using a Dikévia-neutral username. Grant only the administration privileges required for the deployment.
7. Remove the temporary recovery administrator after the permanent account has been tested. Remove the one-time recovery secrets from the maintenance environment.

The command shape documented by Keycloak is:

```bash
/opt/keycloak/bin/kc.sh bootstrap-admin user --optimized \
  --username:env DIKEVIA_RECOVERY_ADMIN_USERNAME \
  --password:env DIKEVIA_RECOVERY_ADMIN_PASSWORD \
  --no-prompt
```

The maintenance environment must also receive the service's database connection settings (without copying their values into this repository). Confirm that the deployed image accepts this exact command before using it operationally.

## Do not

- Do not reset, drop, or recreate the Keycloak database/schema.
- Do not assume the generated `KC_BOOTSTRAP_ADMIN_PASSWORD` can recover an already initialized realm.
- Do not enable automatic recovery on every normal application startup.
- Do not leave the temporary recovery administrator or its secret in place after recovery.
- Do not deploy this recovery operation to production until the maintenance execution method, outage window, and rollback plan have been reviewed.

## Verification checklist

- [ ] Confirm no Keycloak instance is connected to the database during the recovery command.
- [ ] Confirm the command exits successfully without printing credentials.
- [ ] Confirm the temporary administrator appears in the `master` realm.
- [ ] Confirm the permanent Dikévia administrator can sign in and has the intended permissions.
- [ ] Remove the temporary administrator and recovery secrets.
- [ ] Confirm Keycloak readiness and OIDC discovery/JWKS endpoints after restart.
