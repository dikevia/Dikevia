"""Recherche de jurisprudence administrative via le fonds CETAT de Légifrance.

Le parcours utilisé par l'orchestrateur conserve les identifiants, métadonnées et
éventuels extraits de recherche officiels ; il ne les présente jamais comme des
décisions intégrales. Une méthode de consultation expérimentale est conservée,
mais elle n'est pas appelée par l'orchestrateur tant que son contrat de production
n'a pas été validé avec les accès PISTE réels.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any

from .legifrance import LegifranceConnector, LegifranceUnavailable

DECISION_ID_RE = re.compile(r"^CETATEXT\d{12}$")


class AdministrativeCaseLawConnector:
    def __init__(self, api: LegifranceConnector):
        self.api = api

    @staticmethod
    def search_payload(query: str, effective_date: date) -> dict:
        return {
            "fond": "CETAT",
            "recherche": {
                "champs": [{
                    "criteres": [{
                        "valeur": query[:250],
                        "proximite": 2,
                        "operateur": "ET",
                        "typeRecherche": "UN_DES_MOTS",
                    }],
                    "operateur": "ET",
                    "typeChamp": "ALL",
                }],
                "filtres": [{
                    "facette": "DATE_DECISION",
                    "dates": {"start": "1900-01-01", "end": effective_date.isoformat()},
                }],
                "fromAdvancedRecherche": False,
                "pageSize": 10,
                "operateur": "ET",
                "typePagination": "DEFAUT",
                "pageNumber": 1,
                "sort": "PERTINENCE",
                "secondSort": "DATE_DESC",
            },
        }

    @staticmethod
    def _records(payload: Any) -> list[dict]:
        records: list[dict] = []
        def walk(node: Any) -> None:
            if isinstance(node, dict):
                identifier = node.get("id") or node.get("idTexte") or node.get("id_text")
                if isinstance(identifier, str) and DECISION_ID_RE.fullmatch(identifier):
                    records.append(node)
                    return
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)
        walk(payload)
        # Keep first occurrence of each official decision ID.
        unique: dict[str, dict] = {}
        for record in records:
            identifier = record.get("id") or record.get("idTexte") or record.get("id_text")
            unique.setdefault(identifier, record)
        return list(unique.values())[:10]

    @staticmethod
    def _first_string(record: dict, keys: tuple[str, ...], limit: int) -> str | None:
        for key in keys:
            value = record.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()[:limit]
        return None

    async def search(self, query: str, effective_date: date) -> list[dict]:
        if not isinstance(query, str) or len(query.strip()) < 2 or len(query) > 500:
            raise ValueError("La recherche de jurisprudence doit contenir entre 2 et 500 caractères.")
        response = await self.api._request(
            "POST", "/search",
            json_body=self.search_payload(query.strip(), effective_date),
        )
        results = []
        for record in self._records(response):
            decision_id = record.get("id") or record.get("idTexte") or record.get("id_text")
            title = self._first_string(record, ("titre", "title", "intitule", "libelle"), 500)
            decision_date = self._first_string(
                record, ("dateDecision", "date_decision", "decisionDate", "date"), 40
            )
            number = self._first_string(
                record, ("numero", "number", "numeroAffaire", "numAffaire"), 100
            )
            # Search-hit text is an excerpt only. Do not treat it as the full judgment.
            excerpt = self._first_string(
                record, ("texte", "text", "extrait", "excerpt", "resume"), 3000
            )
            results.append({
                "source_type": "LEGIFRANCE_CETAT_SEARCH",
                "source_id": decision_id,
                "title": title or f"Décision de jurisprudence administrative — {decision_id}",
                "decision_date": decision_date,
                "case_number": number,
                "excerpt": excerpt,
                "text": excerpt or "",
                "full_text_retrieved": False,
                "official_source": True,
                "source_url": f"https://www.legifrance.gouv.fr/search/cetat?tab_selection=cetat&searchField=ALL&query={decision_id}",
                "effective_date_requested": effective_date.isoformat(),
                "source_status": "OFFICIAL_SEARCH_METADATA_ONLY",
            })
        return results

    @staticmethod
    def _find_decision_id(payload: Any) -> str | None:
        found: list[str] = []
        def walk(node: Any) -> None:
            if isinstance(node, dict):
                for key, value in node.items():
                    if key.lower() in {"id", "textid", "idtexte", "id_text"} and isinstance(value, str) and DECISION_ID_RE.fullmatch(value):
                        found.append(value)
                    else:
                        walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)
        walk(payload)
        return found[0] if found else None

    @staticmethod
    def _extract_full_text(payload: Any) -> str | None:
        candidates: list[str] = []
        text_keys = {"texte", "text", "contenu", "content", "textehtml", "texthtml", "contenuhtml"}
        def walk(node: Any) -> None:
            if isinstance(node, dict):
                for key, value in node.items():
                    if key.lower() in text_keys and isinstance(value, str) and len(value.strip()) > 80:
                        candidates.append(value)
                    else:
                        walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)
        walk(payload)
        if not candidates:
            return None
        raw = max(candidates, key=len)
        raw = re.sub(r"<br\s*/?>", "\n", raw, flags=re.I)
        raw = re.sub(r"</(?:p|div|li|h[1-6])\s*>", "\n", raw, flags=re.I)
        raw = re.sub(r"<[^>]+>", " ", raw)
        raw = (raw.replace("&nbsp;", " ").replace("&amp;", "&")
                  .replace("&lt;", "<").replace("&gt;", ">")
                  .replace("&quot;", '"').replace("&#39;", "'"))
        cleaned = re.sub(r"[ \t]+", " ", raw)
        cleaned = re.sub(r"\n\s*\n+", "\n\n", cleaned).strip()
        return cleaned[:100000] if len(cleaned) >= 80 else None

    async def consult(self, decision_id: str) -> dict:
        """Fetch and validate the official full text for one decision identifier.

        Experimental route: the public FAQ documents CETAT search, but the
        /consult/juri full-text contract must still be validated against the
        organization's PISTE sandbox. The ingestion endpoint is feature-flagged
        off by default. Returned identifier and substantial text must match.
        """
        if not isinstance(decision_id, str) or not DECISION_ID_RE.fullmatch(decision_id):
            raise ValueError("Identifiant de décision administrative invalide.")
        payload = await self.api._request(
            "POST", "/consult/juri", json_body={"textId": decision_id}
        )
        returned_id = self._find_decision_id(payload)
        full_text = self._extract_full_text(payload)
        if returned_id != decision_id or not full_text:
            raise LegifranceUnavailable(
                "La consultation officielle n'a pas retourné un texte intégral vérifiable pour cet identifiant."
            )
        record = payload.get("text") if isinstance(payload.get("text"), dict) else payload
        def field(*keys: str, limit: int = 500) -> str | None:
            for key in keys:
                value = record.get(key) if isinstance(record, dict) else None
                if isinstance(value, str) and value.strip():
                    return value.strip()[:limit]
            return None
        return {
            "source_type": "LEGIFRANCE_CETAT_FULL_TEXT",
            "source_id": decision_id,
            "title": field("titre", "title", "intitule") or f"Décision administrative {decision_id}",
            "decision_date": field("dateDecision", "date_decision", "decisionDate", "date", limit=40),
            "case_number": field("numero", "number", "numeroAffaire", "numAffaire", limit=100),
            "jurisdiction": field("juridiction", "jurisdiction", "formation", limit=250),
            "text": full_text,
            "full_text_retrieved": True,
            "official_source": True,
            "source_status": "OFFICIAL_FULL_TEXT_ID_MATCHED",
            "source_url": f"https://www.legifrance.gouv.fr/search/cetat?tab_selection=cetat&searchField=ALL&query={decision_id}",
        }


