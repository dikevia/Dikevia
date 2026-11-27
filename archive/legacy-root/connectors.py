"""Compatibilité pour les anciens points d'entrée des connecteurs.

Le moteur principal utilise directement `app.legifrance` et `app.local_corpus`.
"""
from datetime import date

from .schemas import AskRequest
from .legal_validation import parse_facts_date
from .local_corpus import search_local_documents


class ConnectorNotConfigured(RuntimeError):
    pass


class LegifranceConnector:
    async def search(self, request: AskRequest) -> list[dict]:
        raise ConnectorNotConfigured(
            "Utiliser le connecteur PISTE stable défini dans app.legifrance."
        )


class LocalCorpusConnector:
    async def search(
        self, request: AskRequest, organization_id: str, conn=None
    ) -> list[dict]:
        if conn is None:
            raise ConnectorNotConfigured(
                "Une connexion PostgreSQL tenant-scoped est requise pour rechercher les documents locaux."
            )
        effective_date = parse_facts_date(request.facts_date) or date.today()
        return await search_local_documents(
            conn, organization_id, request.employer,
            request.question.strip()[:500], effective_date, limit=5,
        )
