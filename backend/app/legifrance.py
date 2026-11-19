"""Connecteur PISTE/Légifrance fondé sur les exemples officiels de la FAQ DILA.

Les secrets restent côté serveur. Les réponses non conformes au contrat attendu
sont refusées : aucune structure supposée n'est transformée en citation juridique.
"""
from __future__ import annotations

import re
import time
from datetime import date, datetime, timezone
from typing import Any
from urllib.parse import urljoin

import httpx
import json
import logging

from .config import settings

TOKEN_TTL_SAFETY_SECONDS = 60
ARTICLE_ID_RE = re.compile(r"^LEGIARTI\d{12}$")
logger = logging.getLogger("dikevia.legifrance")


class LegifranceUnavailable(RuntimeError):
    """PISTE non configuré, inaccessible ou réponse inexploitable."""


class LegifranceConnector:
    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None):
        self.transport = transport
        self._token: str | None = None
        self._token_expires_at = 0.0

    @property
    def configured(self) -> bool:
        return bool(settings.legifrance_client_id and settings.legifrance_client_secret)

    @property
    def environment(self) -> str:
        return settings.legifrance_environment

    @property
    def api_base(self) -> str:
        if self.environment == "production":
            return "https://api.piste.gouv.fr/dila/legifrance/lf-engine-app/"
        return "https://sandbox-api.piste.gouv.fr/dila/legifrance/lf-engine-app/"

    @property
    def token_url(self) -> str:
        if self.environment == "production":
            return "https://oauth.piste.gouv.fr/api/oauth/token"
        return "https://sandbox-oauth.piste.gouv.fr/api/oauth/token"

    async def _get_token(self) -> str:
        if not self.configured:
            raise LegifranceUnavailable("Identifiants PISTE non configurés.")
        if self._token and time.monotonic() < self._token_expires_at - TOKEN_TTL_SAFETY_SECONDS:
            return self._token
        try:
            async with httpx.AsyncClient(timeout=settings.legifrance_timeout_seconds,
                                         transport=self.transport) as client:
                response = await client.post(
                    self.token_url,
                    data={"grant_type": "client_credentials", "client_id": settings.legifrance_client_id,
                          "client_secret": settings.legifrance_client_secret, "scope": settings.legifrance_scope},
                    headers={"Accept": "application/json"},
                )
                response.raise_for_status()
                data = response.json()
            token = data.get("access_token")
            expires = int(data.get("expires_in", 0))
            if not isinstance(token, str) or not token or expires < 1:
                raise LegifranceUnavailable("Réponse OAuth PISTE incomplète.")
            self._token = token
            self._token_expires_at = time.monotonic() + expires
            return token
        except httpx.HTTPStatusError as exc:
            # Log only the HTTP status; never expose OAuth response bodies or credentials.
            raise LegifranceUnavailable(
                f"Refus OAuth PISTE (HTTP {exc.response.status_code})."
            ) from exc
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise LegifranceUnavailable("Échec réseau ou réponse OAuth PISTE invalide.") from exc

    async def _request(self, method: str, path: str, *, json_body: dict | None = None) -> dict:
        token = await self._get_token()
        url = urljoin(self.api_base, path.lstrip("/"))
        try:
            async with httpx.AsyncClient(timeout=settings.legifrance_timeout_seconds,
                                         transport=self.transport) as client:
                response = await client.request(method, url, json=json_body,
                    headers={"Authorization": f"Bearer {token}", "Accept": "application/json",
                             "Content-Type": "application/json"})
                if path.lstrip("/") == "consult/getArticle":
                    logger.warning(
                        "DIKEVIA_DIAGNOSTIC PISTE_GET_ARTICLE_HTTP status=%d content_type=%s",
                        response.status_code, response.headers.get("content-type", "unknown"),
                    )
                response.raise_for_status()
                data = response.json()
                if path.lstrip("/") == "consult/getArticle":
                    logger.warning(
                        "DIKEVIA_DIAGNOSTIC PISTE_GET_ARTICLE_RESPONSE top_keys=%s",
                        sorted(data.keys()) if isinstance(data, dict) else type(data).__name__,
                    )
            if not isinstance(data, dict):
                raise LegifranceUnavailable("Réponse Légifrance non conforme : objet JSON attendu.")
            return data
        except httpx.HTTPStatusError as exc:
            # Keep OAuth/API secrets and response bodies out of logs.
            raise LegifranceUnavailable(
                f"Refus API Légifrance (HTTP {exc.response.status_code}) sur {path}."
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise LegifranceUnavailable("Erreur réseau ou réponse API Légifrance invalide.") from exc

    async def ping_diagnostics(self) -> dict[str, int | str]:
        """Test each documented ping route independently using a fresh OAuth token."""
        token = await self._get_token()
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        results: dict[str, int | str] = {}
        async with httpx.AsyncClient(timeout=settings.legifrance_timeout_seconds,
                                     transport=self.transport) as client:
            for path in ("search/ping", "consult/ping", "list/ping"):
                try:
                    response = await client.get(urljoin(self.api_base, path), headers=headers)
                    results[path] = response.status_code
                    if response.status_code >= 500:
                        logger.warning("DIKEVIA_DIAGNOSTIC PISTE_PING_UPSTREAM route=%s status=%d body_preview=%s",
                                       path, response.status_code, response.text[:500])
                except httpx.HTTPError:
                    results[path] = "NETWORK_ERROR"
        return results

    async def ping(self) -> bool:
        """Check the documented Légifrance ping endpoint, with guide-compatible fallback.

        The DILA FAQ documents /list/ping; the PISTE user guide also exposes
        /consult/ping. Only a missing-route response triggers the fallback:
        authentication and server errors remain visible as connection failures.
        """
        token = await self._get_token()
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        async with httpx.AsyncClient(timeout=settings.legifrance_timeout_seconds,
                                     transport=self.transport) as client:
            for path in ("list/ping", "consult/ping"):
                try:
                    response = await client.get(urljoin(self.api_base, path), headers=headers)
                    response.raise_for_status()
                    return True
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code in {404, 405} and path == "list/ping":
                        continue
                    raise LegifranceUnavailable(
                        f"Refus du point de contrôle PISTE {path} (HTTP {exc.response.status_code})."
                    ) from exc
                except httpx.HTTPError as exc:
                    raise LegifranceUnavailable(f"Erreur réseau sur le point de contrôle PISTE {path}.") from exc
        raise LegifranceUnavailable("Aucun point de contrôle Légifrance disponible.")

    @staticmethod
    def _date_epoch_ms(value: date) -> int:
        return int(datetime(value.year, value.month, value.day, tzinfo=timezone.utc).timestamp() * 1000)

    def _search_payload(self, query: str, effective_date: date, code_name: str | None = None) -> dict:
        ref = re.search(r"\b([LDR]\.\s*\d+(?:-\d+)*|[LDR]\s*\d+(?:-\d+)*)\b", query, re.I)
        if ref is None:
            ref = re.search(r"\barticle\s+(\d+(?:-\d+)*)\b", query, re.I)
        if ref:
            field = {"typeChamp": "NUM_ARTICLE", "criteres": [{
                "typeRecherche": "EXACTE", "valeur": re.sub(r"[.\s]+", "", ref.group(1)).upper(), "operateur": "ET"}], "operateur": "ET"}
        else:
            field = {"typeChamp": "ARTICLE", "criteres": [{
                "typeRecherche": "UN_DES_MOTS", "valeur": query[:250], "operateur": "ET"}], "operateur": "ET"}
        return {"fond": "CODE_DATE", "recherche": {
            "champs": [field],
            "filtres": [
                {"facette": "NOM_CODE", "valeurs": [code_name or settings.legifrance_code_name]},
                {"facette": "DATE_VERSION", "singleDate": effective_date.isoformat()},
            ],
            "pageNumber": 1, "pageSize": 10, "operateur": "ET", "sort": "PERTINENCE",
            "typePagination": "DEFAUT",
        }}

    @staticmethod
    def _find_article_ids(value: Any) -> list[str]:
        found: list[str] = []
        def walk(node: Any):
            if isinstance(node, dict):
                for key, child in node.items():
                    if key.lower() in {"id", "idarticle", "id_article", "cid"} and isinstance(child, str) and ARTICLE_ID_RE.fullmatch(child):
                        found.append(child)
                    else:
                        walk(child)
            elif isinstance(node, list):
                for child in node:
                    walk(child)
        walk(value)
        return list(dict.fromkeys(found))[:5]

    @staticmethod
    def _relevant_excerpt(text: str, query: str, max_chars: int = 1800) -> str:
        """Select query-relevant sentences from a long official text, preserving order."""
        if len(text) <= max_chars:
            return text
        stopwords = {
            "dans", "avec", "pour", "sans", "sous", "entre", "chez", "être", "avoir",
            "quel", "quelle", "quels", "quelles", "comment", "quand", "est", "sont",
            "les", "des", "une", "un", "du", "de", "la", "le", "et", "ou", "sur",
            "aux", "par", "qui", "que", "quoi", "dont", "leur", "leurs", "ses",
            "son", "sa", "ce", "cet", "cette", "ces", "agent", "agents",
        }
        terms = {
            token.casefold() for token in re.findall(r"[A-Za-zÀ-ÿ0-9]{3,}", query)
            if token.casefold() not in stopwords
        }
        if not terms:
            return text[:max_chars]
        sentences = [
            part.strip() for part in re.split(r"(?<=[.!?;])\s+|\n+", text)
            if part.strip()
        ]
        ranked = []
        for index, sentence in enumerate(sentences):
            folded = sentence.casefold()
            score = sum(1 for term in terms if term in folded)
            if score:
                ranked.append((score, index, sentence))
        if not ranked:
            return text[:max_chars]
        ranked.sort(key=lambda item: (-item[0], item[1]))
        chosen = []
        used = 0
        for _, index, sentence in ranked:
            if used + len(sentence) + 1 > max_chars:
                continue
            chosen.append((index, sentence))
            used += len(sentence) + 1
        if not chosen:
            return text[:max_chars]
        chosen.sort(key=lambda item: item[0])
        return " … ".join(sentence for _, sentence in chosen)[:max_chars]

    @staticmethod
    def _extract_text(value: Any) -> str:
        candidates: list[str] = []
        keys = {"texte", "text", "contenu", "content", "textehtml", "textHtml".lower(), "contenuhtml"}
        def walk(node: Any):
            if isinstance(node, dict):
                for key, child in node.items():
                    if key.lower() in keys and isinstance(child, str) and child.strip():
                        candidates.append(child)
                    else:
                        walk(child)
            elif isinstance(node, list):
                for child in node:
                    walk(child)
        walk(value)
        if not candidates:
            return ""
        # Prefer the longest text-like field; HTML remains source text and is not rendered as HTML.
        raw = max(candidates, key=len)
        raw = re.sub(r"<br\s*/?>", "\n", raw, flags=re.I)
        raw = re.sub(r"<li\b[^>]*>", "\n- ", raw, flags=re.I)
        raw = re.sub(r"</li\s*>", "\n", raw, flags=re.I)
        raw = re.sub(r"</(?:p|div|h[1-6]|ul|ol)\s*>", "\n", raw, flags=re.I)
        raw = re.sub(r"<(?:p|div|ul|ol)\b[^>]*>", "\n", raw, flags=re.I)
        raw = re.sub(r"<[^>]+>", " ", raw)
        raw = re.sub(r"&nbsp;", " ", raw, flags=re.I)
        raw = re.sub(r"&amp;", "&", raw, flags=re.I)
        raw = re.sub(r"&lt;", "<", raw, flags=re.I)
        raw = re.sub(r"&gt;", ">", raw, flags=re.I)
        raw = re.sub(r"&quot;", '"', raw, flags=re.I)
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in raw.splitlines()]
        return "\n".join(line for line in lines if line).strip()


    @staticmethod
    def _walk_dicts(value: Any):
        if isinstance(value, dict):
            yield value
            for child in value.values():
                yield from LegifranceConnector._walk_dicts(child)
        elif isinstance(value, list):
            for child in value:
                yield from LegifranceConnector._walk_dicts(child)

    @staticmethod
    def _first_value(record: dict, keys: tuple[str, ...]):
        for key in keys:
            value = record.get(key)
            if isinstance(value, (str, int, float)) and str(value).strip():
                return str(value).strip()
        return None

    @staticmethod
    def _iso_date(value: str | None):
        if not value:
            return None
        from datetime import date, datetime, timezone
        try:
            if value.isdigit() and len(value) >= 10:
                stamp = int(value)
                if stamp > 10_000_000_000:
                    stamp //= 1000
                return datetime.fromtimestamp(stamp, tz=timezone.utc).date()
            return date.fromisoformat(value[:10])
        except (ValueError, OverflowError, OSError):
            return None

    async def search_regulatory_texts(self, query: str, effective_date: date, limit: int = 10) -> list[dict]:
        """Search official consolidated laws/regulations (LODA_DATE) and consult each text.

        The API's /search -> /consult/legiPart workflow follows the DILA FAQ.
        Only LEGITEXT identifiers with a returned matching identifier and substantial
        text are stored as full text; otherwise no content is fabricated.
        """
        if not isinstance(query, str) or len(query.strip()) < 2 or len(query) > 500:
            raise ValueError("La recherche réglementaire doit contenir entre 2 et 500 caractères.")
        if not 1 <= limit <= 20:
            raise ValueError("La limite réglementaire doit être comprise entre 1 et 20.")
        stamp = self._date_epoch_ms(effective_date)
        number_match = re.search(r"\b(?:décret|decret|arrêté|arrete|loi|ordonnance)\s*(?:n[°ºo]?\s*)?(\d{4}-\d{1,4})\b", query, re.I)
        if number_match:
            search_field = {
                "typeChamp": "NUM",
                "criteres": [{
                    "typeRecherche": "EXACTE",
                    "valeur": number_match.group(1),
                    "operateur": "ET",
                }],
                "operateur": "ET",
            }
        else:
            search_field = {
                "typeChamp": "ALL",
                "criteres": [{
                    "typeRecherche": "UN_DES_MOTS",
                    "valeur": query.strip()[:250],
                    "proximite": 5,
                    "operateur": "ET",
                }],
                "operateur": "ET",
            }
        payload = {"fond": "LODA_DATE", "recherche": {
            "champs": [search_field],
            "filtres": [{"facette": "DATE_VERSION", "singleDate": stamp}],
            "fromAdvancedRecherche": False, "pageSize": limit, "pageNumber": 1,
            "operateur": "ET", "sort": "PERTINENCE", "secondSort": "SIGNATURE_DATE_DESC",
            "typePagination": "DEFAUT"}}
        found = await self._request("POST", "/search", json_body=payload)
        nodes = list(self._walk_dicts(found))
        records: list[dict] = []
        seen: set[str] = set()
        for record in nodes:
            identifier = self._first_value(record, ("id", "idTexte", "id_text", "textId"))
            if identifier and re.fullmatch(r"LEGITEXT\d{12}", identifier) and identifier not in seen:
                records.append(record)
                seen.add(identifier)
            if len(records) >= limit:
                break
        top_keys = list(found.keys())[:20] if isinstance(found, dict) else []
        result_count = (
            len(found.get("results") or [])
            if isinstance(found, dict) and isinstance(found.get("results"), list)
            else -1
        )
        sample_keys = (
            list(found["results"][0].keys())[:20]
            if result_count > 0 and isinstance(found["results"][0], dict)
            else []
        )
        logger.warning(
            "DIKEVIA_DIAGNOSTIC PISTE_LODA_SEARCH response_keys=%s result_count=%d sample_keys=%s candidate_count=%d",
            top_keys, result_count, sample_keys, len(records),
        )
        output = []
        for record in records:
            identifier = self._first_value(record, ("id", "idTexte", "id_text", "textId"))
            detail = await self._request("POST", "/consult/legiPart", json_body={"date": stamp, "textId": identifier})
            returned_ids = [self._first_value(node, ("id", "idTexte", "id_text", "textId"))
                            for node in self._walk_dicts(detail)]
            text = self._extract_text(detail)
            id_matches = identifier in returned_ids
            text_valid = len(text) >= 80
            logger.warning(
                "DIKEVIA_DIAGNOSTIC PISTE_LODA_CONSULT id=%s id_matches=%s text_length=%d accepted=%s",
                identifier, id_matches, len(text), id_matches and text_valid,
            )
            if not id_matches or not text_valid:
                continue
            title = self._first_value(record, ("titre", "titreTexte", "title", "intitule")) or identifier
            number = self._first_value(record, ("nor", "NOR", "numero", "num"))
            status_raw = (self._first_value(record, ("etat", "etatJuridique", "status", "etatTexte")) or "").upper()
            status = "IN_FORCE" if any(token in status_raw for token in ("VIGUEUR", "EN VIGUEUR")) else (
                "REPEALED" if "ABROG" in status_raw else ("NOT_IN_FORCE" if "PERIME" in status_raw else "UNKNOWN"))
            signature = self._iso_date(self._first_value(record, ("dateTexte", "dateSignature", "date")))
            publication = self._iso_date(self._first_value(record, ("datePublication", "datePubli")))
            valid_from = self._iso_date(self._first_value(record, ("dateDebut", "dateDebutVersion", "dateEffet")))
            valid_to = self._iso_date(self._first_value(record, ("dateFin", "dateFinVersion")))
            kind_raw = (title + " " + (number or "")).lower()
            kind = "DECREE" if "décret" in kind_raw or "decret" in kind_raw else (
                "ORDER" if "arrêté" in kind_raw or "arrete" in kind_raw else (
                "ORDONNANCE" if "ordonnance" in kind_raw else "LAW"))
            output.append({"source_type": "LEGIFRANCE_LODA", "source_id": identifier,
                "title": title, "document_kind": kind, "official_number": number,
                "publisher": self._first_value(record, ("emetteur", "ministere", "autorite")),
                "official_url": f"https://www.legifrance.gouv.fr/loda/id/{identifier}",
                "signature_date": signature, "publication_date": publication,
                "status": status, "source_status": "OFFICIAL_TEXT_ID_VERIFIED",
                "excerpt": self._relevant_excerpt(text, query.strip()),
                "valid_from": valid_from, "valid_to": valid_to,
                # LODA_DATE + DATE_VERSION and the dated consultation select
                # the version applicable to the requested date even when the
                # search metadata omits a separate status label.
                "version_status": status if status != "UNKNOWN" else "IN_FORCE",
                "version_key": f"{identifier}:{effective_date.isoformat()}",
                "source_version_id": identifier, "full_text": text[:500000],
                "raw_metadata": record, "raw_version_payload": {
                    "requested_date": effective_date.isoformat(),
                    "date_filter": "DATE_VERSION",
                    "matching_consulted_id": identifier,
                    "api_method": "/consult/legiPart"}})
        return output

    async def search_code_articles(self, query: str, effective_date: date, *, code_name: str | None = None) -> list[dict]:
        if not query or len(query.strip()) < 2 or len(query) > 500:
            raise ValueError("La recherche Légifrance doit contenir entre 2 et 500 caractères.")
        payload = self._search_payload(query.strip(), effective_date, code_name)
        result = await self._request("POST", "/search", json_body=payload)
        logger.warning(
            "DIKEVIA_DIAGNOSTIC PISTE_CODE_SEARCH_SUMMARY result_count=%d",
            len(self._find_article_ids(result)),
        )
        article_ids = self._find_article_ids(result)
        if not article_ids:
            # No result IDs means getArticle is deliberately never called.
            logger.warning(
                "DIKEVIA_DIAGNOSTIC PISTE_CODE_SEARCH_COMPLETE result_count=0 get_article_calls=0"
            )
            return []
        requested_ref_match = re.search(
            r"\b(?:article\s+)?([LDR]\.\s*\d+(?:-\d+)*|[LDR]\s*\d+(?:-\d+)*)\b",
            query, re.I,
        )
        if requested_ref_match is None:
            requested_ref_match = re.search(r"\barticle\s+(\d+(?:-\d+)*)\b", query, re.I)
        requested_ref = (
            re.sub(r"[^A-Z0-9-]", "", requested_ref_match.group(1).upper())
            if requested_ref_match else None
        )
        articles: list[dict] = []
        get_article_calls = 0
        for article_id in article_ids:
            get_article_calls += 1
            detail = await self._request("POST", "/consult/getArticle", json_body={"id": article_id})
            returned_ids = self._find_article_ids(detail)
            text = self._extract_text(detail)
            # Temporary shape-only diagnostics: never log article text or credentials.
            text_fields = []
            for node in self._walk_dicts(detail):
                for key, value in node.items():
                    if isinstance(value, str) and key.lower() in {
                        "texte", "text", "contenu", "content", "textehtml", "contenuhtml"
                    }:
                        text_fields.append({"key": key, "length": len(value)})
            logger.warning(
                "DIKEVIA_DIAGNOSTIC PISTE_GET_ARTICLE id=%s top_keys=%s returned_ids=%s extracted_text_length=%d text_fields=%s",
                article_id, sorted(detail.keys()), returned_ids, len(text),
                json.dumps(text_fields[:20], ensure_ascii=False),
            )
            if article_id not in returned_ids or not text:
                logger.warning(
                    "DIKEVIA_DIAGNOSTIC PISTE_GET_ARTICLE_REJECTED id=%s id_match=%s text_present=%s",
                    article_id, article_id in returned_ids, bool(text),
                )
                continue
            matching_article_nodes = [
                node for node in self._walk_dicts(detail)
                if self._first_value(node, ("id", "idarticle", "id_article")) == article_id
            ]
            # Prefer the matching article object that actually carries its metadata.
            article_metadata = next(
                (node for node in matching_article_nodes
                 if self._first_value(node, ("num", "numero", "numArticle"))),
                matching_article_nodes[0] if matching_article_nodes else {},
            )
            raw_num = self._first_value(article_metadata, ("num", "numero", "numArticle"))
            article_ref = re.sub(r"[^A-Z0-9-]", "", raw_num.upper()) if raw_num else None
            article_label = re.sub(r"[.\s]+", "", raw_num.upper()) if raw_num else None
            code_name = self._first_value(
                article_metadata, ("nomCode", "titreCode", "codeName", "nameCode")
            )
            logger.warning(
                "DIKEVIA_DIAGNOSTIC PISTE_GET_ARTICLE_METADATA id=%s num=%s normalized_num=%s code_name=%s",
                article_id, raw_num, article_ref, code_name,
            )
            # The search result already supplied this exact LEGIARTI id.
            # If getArticle omits num, retain the id-bound result but mark its
            # article number as unverified; an explicit conflicting num is rejected.
            if requested_ref and article_ref and article_ref != requested_ref:
                logger.warning(
                    "DIKEVIA_DIAGNOSTIC PISTE_GET_ARTICLE_REJECTED_REFERENCE id=%s requested_num=%s returned_num=%s",
                    article_id, requested_ref, article_ref,
                )
                continue
            if requested_ref and not article_ref:
                logger.warning(
                    "DIKEVIA_DIAGNOSTIC PISTE_GET_ARTICLE_ID_FALLBACK id=%s requested_num=%s",
                    article_id, requested_ref,
                )
            valid_from = self._iso_date(self._first_value(
                article_metadata, ("dateDebut", "dateDebutVersion", "dateEffet", "dateDebutApplication")
            ))
            valid_to = self._iso_date(self._first_value(
                article_metadata, ("dateFin", "dateFinVersion", "dateFinApplication")
            ))
            articles.append({
                "source_type": "LEGIFRANCE_API", "source_id": article_id, "article": article_label,
                "article_id": article_id, "source_version_id": article_id,
                "title": f"{code_name or settings.legifrance_code_name} — {article_label or article_id}",
                "text": text[:20000],
                "excerpt": self._relevant_excerpt(text, query.strip(), max_chars=1800),
                "effective_date_requested": effective_date.isoformat(),
                "requested_effective_date": effective_date.isoformat(),
                "valid_from": valid_from.isoformat() if valid_from else None,
                "valid_to": valid_to.isoformat() if valid_to else None,
                "version_status": "IN_FORCE_ON_REQUESTED_DATE",
                "version_key": f"{article_id}:{effective_date.isoformat()}",
                "raw_version_payload": {
                    "requested_date": effective_date.isoformat(),
                    "date_filter": "CODE_DATE/DATE_VERSION",
                    "matching_consulted_id": article_id,
                    "api_method": "/consult/getArticle",
                },
                "official_source": True,
                "source_url": "https://www.legifrance.gouv.fr/",
            })
        logger.warning(
            "DIKEVIA_DIAGNOSTIC PISTE_CODE_SEARCH_COMPLETE result_count=%d get_article_calls=%d",
            len(articles), get_article_calls,
        )
        return articles


connector = LegifranceConnector()