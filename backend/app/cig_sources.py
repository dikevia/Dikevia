"""Catalogue des ressources du CIG Petite Couronne pour la veille FPT.

Ce registre référence des ressources et leurs conditions d'accès. Il ne contourne
aucune authentification et n'autorise pas, à lui seul, la copie ou l'indexation
des contenus protégés. Les contenus éditoriaux restent en mode lien/métadonnées
tant qu'une licence ou une autorisation écrite ne couvre pas l'usage envisagé.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlparse


CIG_HOSTS = frozenset({"www.cig929394.fr", "cig929394.fr", "bip.cig929394.fr"})


@dataclass(frozen=True)
class CIGSource:
    source_id: str
    title: str
    url: str
    resource_type: str
    access: Literal["PUBLIC", "AUTHENTICATED", "PAID_OR_SUBSCRIPTION"]
    content_policy: Literal["LINK_ONLY", "METADATA_ONLY", "LICENSE_REQUIRED"]
    legal_weight: Literal["OFFICIAL_TEXT", "JURISPRUDENTIAL_SOURCE", "EDITORIAL_ANALYSIS", "PRACTICAL_GUIDANCE"]
    scope_note: str


CIG_SOURCES: tuple[CIGSource, ...] = (
    CIGSource(
        "CIG_PUBLICATIONS_CATALOG",
        "Catalogue des publications et ressources",
        "https://www.cig929394.fr/je-souhaite-acceder-aux-publications-et-ressources-du-cig/",
        "CATALOG",
        "PUBLIC",
        "METADATA_ONLY",
        "PRACTICAL_GUIDANCE",
        "Point d'entrée de découverte ; chaque ressource doit être qualifiée individuellement.",
    ),
    CIGSource(
        "CIG_MINUTE_STATUT",
        "Podcasts Minute Statut",
        "https://www.cig929394.fr/je-souhaite-acceder-aux-publications-et-ressources-du-cig/",
        "PODCAST",
        "PUBLIC",
        "LICENSE_REQUIRED",
        "EDITORIAL_ANALYSIS",
        "Contenus pédagogiques du CIG ; transcription, stockage et réutilisation soumis aux droits applicables.",
    ),
    CIGSource(
        "CIG_INFOGRAPHIES",
        "Infographies statutaires",
        "https://www.cig929394.fr/je-souhaite-acceder-aux-publications-et-ressources-du-cig/",
        "INFOGRAPHIC",
        "PUBLIC",
        "LICENSE_REQUIRED",
        "PRACTICAL_GUIDANCE",
        "Utilisables comme piste de compréhension ; ne remplacent jamais le texte officiel.",
    ),
    CIGSource(
        "CIG_SVP_PUBLIC",
        "SVP Statut – réponses publiées et anonymisées",
        "https://www.cig929394.fr/je-souhaite-acceder-aux-publications-et-ressources-du-cig/",
        "ANONYMIZED_QA",
        "PUBLIC",
        "LICENSE_REQUIRED",
        "EDITORIAL_ANALYSIS",
        "Point d'entrée catalogue uniquement ; chaque réponse doit être vérifiée individuellement et ses droits de réutilisation autorisés avant indexation.",
    ),
    CIGSource(
        "CIG_IAJ",
        "Informations administratives et juridiques (IAJ)",
        "https://www.cig929394.fr/je-souhaite-acceder-aux-publications-et-ressources-du-cig/iaj/",
        "JOURNAL",
        "PAID_OR_SUBSCRIPTION",
        "LICENSE_REQUIRED",
        "EDITORIAL_ANALYSIS",
        "Revue sur abonnement/achat ; pas d'extraction ni d'indexation commerciale sans licence adaptée.",
    ),
    CIGSource(
        "CIG_BIP",
        "Banque d'information sur le personnel (BIP)",
        "https://bip.cig929394.fr/",
        "DATABASE",
        "AUTHENTICATED",
        "LICENSE_REQUIRED",
        "EDITORIAL_ANALYSIS",
        "Accès nominatif/habilité ; l'abonnement d'un tiers ne vaut pas autorisation d'intégration dans Dikévia.",
    ),
    CIGSource(
        "CIG_RCT",
        "Répertoire des carrières territoriales (RCT)",
        "https://www.cig929394.fr/je-souhaite-acceder-aux-publications-et-ressources-du-cig/",
        "CAREER_REFERENCE",
        "PAID_OR_SUBSCRIPTION",
        "LICENSE_REQUIRED",
        "PRACTICAL_GUIDANCE",
        "Vérifier l'abonnement et les droits de réutilisation avant toute ingestion.",
    ),
    CIGSource(
        "CIG_SVP_EXPERTISE",
        "Expertise statutaire SVP Statut",
        "https://www.cig929394.fr/je-souhaite-un-accompagnement-dans-la-gestion-des-rh/conseil-et-ressources-statutaires/conseil-et-lexpertise-statutaire-svp-statut/",
        "EXPERT_SERVICE",
        "AUTHENTICATED",
        "LINK_ONLY",
        "PRACTICAL_GUIDANCE",
        "Service d'accompagnement réservé aux collectivités et établissements affiliés ; ce n'est pas un corpus public.",
    ),
)


def get_cig_source(source_id: str) -> CIGSource | None:
    """Return a known CIG source by stable identifier."""
    return next((item for item in CIG_SOURCES if item.source_id == source_id), None)


def validate_cig_source_url(url: str) -> bool:
    """Accept only HTTPS URLs on explicitly allowlisted CIG domains."""
    try:
        parsed = urlparse(url)
    except (TypeError, ValueError):
        return False
    return (
        parsed.scheme == "https"
        and parsed.hostname in CIG_HOSTS
        and not parsed.username
        and not parsed.password
    )


def can_ingest_cig_content(
    source_id: str,
    *,
    written_permission: bool = False,
    permission_scope: str | None = None,
) -> bool:
    """Fail closed until a verifiable permission registry exists.

    A caller-supplied boolean and free-text scope cannot prove that a written
    licence exists, is current, covers the exact material, or authorizes the
    requested commercial processing. No CIG permission registry is integrated,
    so this helper deliberately never authorizes ingestion.
    """
    # Validate the source identifier, but never infer authorization from input.
    return get_cig_source(source_id) is not None and False


def cig_source_metadata(source_id: str) -> dict[str, str] | None:
    """Return citation-safe catalogue metadata, never protected source content."""
    source = get_cig_source(source_id)
    if source is None:
        return None
    return {
        "source_type": "CIG_DOCUMENTARY_RESOURCE",
        "source_id": source.source_id,
        "title": source.title,
        "official_url": source.url,
        "resource_type": source.resource_type,
        "access": source.access,
        "content_policy": source.content_policy,
        "legal_weight": source.legal_weight,
        "scope_note": source.scope_note,
        "publisher": "CIG Petite Couronne",
        "source_status": "CATALOGUED_NOT_INGESTED",
        "citation_integrity": "URL_ALLOWLISTED_METADATA_ONLY",
    }
