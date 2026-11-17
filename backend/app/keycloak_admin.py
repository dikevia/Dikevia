"""Minimal Keycloak Admin REST client for invitation provisioning.

Uses a confidential service account with realm-management/manage-users only.
Never exposes admin credentials or tokens to browser clients.
"""
from dataclasses import dataclass
import httpx


class KeycloakAdminError(RuntimeError):
    pass


@dataclass(frozen=True)
class KeycloakAdminConfig:
    base_url: str
    realm: str
    client_id: str
    client_secret: str
    timeout: float = 8.0


class KeycloakAdmin:
    def __init__(self, config: KeycloakAdminConfig):
        self.config = config

    async def _token(self, client: httpx.AsyncClient) -> str:
        url = f"{self.config.base_url.rstrip('/')}/realms/{self.config.realm}/protocol/openid-connect/token"
        try:
            response = await client.post(url, data={
                "grant_type": "client_credentials",
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
            })
            response.raise_for_status()
            token = response.json().get("access_token")
            if not token:
                raise KeycloakAdminError("Jeton de service Keycloak absent.")
            return token
        except (httpx.HTTPError, ValueError) as exc:
            raise KeycloakAdminError("Authentification du service Keycloak impossible.") from exc

    async def ensure_user(self, email: str) -> tuple[str, bool, bool]:
        """Create an enabled Keycloak account if absent; never resets an existing user's password."""
        timeout = httpx.Timeout(self.config.timeout)
        async with httpx.AsyncClient(timeout=timeout) as client:
            token = await self._token(client)
            base = f"{self.config.base_url.rstrip('/')}/admin/realms/{self.config.realm}/users"
            headers = {"Authorization": f"Bearer {token}"}
            try:
                found = await client.get(base, headers=headers, params={"email": email, "exact": "true"})
                found.raise_for_status()
                matches = found.json()
                if len(matches) > 1:
                    raise KeycloakAdminError("Plusieurs comptes Keycloak correspondent à cette adresse.")
                if matches:
                    if not matches[0].get("enabled", True):
                        raise KeycloakAdminError("Le compte Keycloak correspondant est désactivé.")
                    return matches[0]["id"], False, bool(matches[0].get("emailVerified", False))
                created = await client.post(base, headers=headers, json={
                    "username": email, "email": email, "enabled": True,
                    "emailVerified": False, "requiredActions": ["VERIFY_EMAIL", "UPDATE_PASSWORD"],
                })
                if created.status_code == 409:
                    found = await client.get(base, headers=headers, params={"email": email, "exact": "true"})
                    found.raise_for_status()
                    matches = found.json()
                    if len(matches) == 1:
                        return matches[0]["id"], False, bool(matches[0].get("emailVerified", False))
                created.raise_for_status()
                user_id = created.headers.get("Location", "").rstrip("/").split("/")[-1]
                if not user_id:
                    raise KeycloakAdminError("Keycloak n'a pas retourné l'identifiant du compte.")
                return user_id, True, False
            except KeycloakAdminError:
                raise
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                raise KeycloakAdminError("Le provisionnement du compte Keycloak a échoué.") from exc

    async def send_verification(self, user_id: str, redirect_uri: str, is_new_user: bool = False) -> None:
        """Send address verification; request password setup only for newly created accounts."""
        timeout = httpx.Timeout(self.config.timeout)
        async with httpx.AsyncClient(timeout=timeout) as client:
            token = await self._token(client)
            url = (f"{self.config.base_url.rstrip('/')}/admin/realms/{self.config.realm}"
                   f"/users/{user_id}/execute-actions-email")
            try:
                response = await client.put(url, headers={"Authorization": f"Bearer {token}"},
                    params={"client_id": "cfdt-juris-web", "redirect_uri": redirect_uri, "lifespan": "86400"},
                    json=(["VERIFY_EMAIL", "UPDATE_PASSWORD"] if is_new_user else ["VERIFY_EMAIL"]))
                if response.status_code not in (200, 204):
                    response.raise_for_status()
            except httpx.HTTPError as exc:
                raise KeycloakAdminError("L'e-mail de vérification Keycloak n'a pas pu être envoyé.") from exc
