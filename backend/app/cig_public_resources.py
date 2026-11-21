"""Curated public CIG Petite Couronne discovery index.

Only page-level metadata and canonical URLs are stored here. This file does
not mirror PDFs, transcripts, paywalled content, authenticated BIP pages, or
restricted webinar material. Re-check each resource's current access and reuse
terms before any content extraction or indexing.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CIGPublicResource:
    resource_id: str
    title: str
    url: str
    format: str
    themes: tuple[str, ...]
    territorial_scope: str
    source_role: str
    content_status: str = "METADATA_ONLY"


CIG_PUBLIC_RESOURCES: tuple[CIGPublicResource, ...] = (
    CIGPublicResource(
        "CIG_SVP_MEDICINE_PREVENTIVE_PROVIDER",
        "Encadrement du recours à un prestataire extérieur pour assurer les missions du service de médecine du travail",
        "https://www.cig929394.fr/je-souhaite-acceder-aux-publications-et-ressources-du-cig/",
        "PDF publication listed in public catalogue",
        ("sante_securite", "medecine_preventive", "organisation_des_services"),
        "FPT general information; verify territorial and temporal applicability",
        "EDITORIAL_LEGAL_ANALYSIS",
    ),
    CIGPublicResource(
        "CIG_SVP_RIGHTS_UNION_ORGANIZATION",
        "Les modalités d’exercice du droit syndical dans le cadre de la création d’une organisation syndicale",
        "https://www.cig929394.fr/je-souhaite-acceder-aux-publications-et-ressources-du-cig/?a=1&categorie=&date=&f=1&recherche=statutaire",
        "PDF publication listed in public catalogue",
        ("droits_syndicaux", "liberte_syndicale", "organisation_syndicale"),
        "FPT general information; verify territorial and temporal applicability",
        "EDITORIAL_LEGAL_ANALYSIS",
    ),
    CIGPublicResource(
        "CIG_INFOGRAPHIC_CUMUL_ACTIVITES",
        "Le cumul d’activités des agents publics – Infographie",
        "https://www.cig929394.fr/publications/le-cumul-dactivites-des-agents-publics-infographie/",
        "Infographic / PDF",
        ("cumul_activites", "deontologie", "obligations_agents"),
        "FPT-oriented educational resource; verify the underlying current rules",
        "PRACTICAL_GUIDANCE",
    ),
    CIGPublicResource(
        "CIG_INFOGRAPHIC_TEMPS_PARTIEL",
        "Le temps partiel de droit des agents publics territoriaux – Infographie",
        "https://www.cig929394.fr/je-souhaite-acceder-aux-publications-et-ressources-du-cig/",
        "Infographic / PDF listed in public catalogue",
        ("temps_partiel", "temps_travail", "droits_agents"),
        "Explicitly territorial in title",
        "PRACTICAL_GUIDANCE",
    ),
    CIGPublicResource(
        "CIG_INFOGRAPHIC_EMPLOIS_FONCTIONNELS",
        "La procédure de recrutement sur les emplois fonctionnels de direction – Infographie",
        "https://www.cig929394.fr/publications/la-procedure-de-recrutement-sur-les-emplois-fonctionnels-de-direction-infographie/",
        "Infographic / PDF",
        ("emplois_fonctionnels", "recrutement", "direction"),
        "FPT; special statutory regime for functional posts",
        "PRACTICAL_GUIDANCE",
    ),
    CIGPublicResource(
        "CIG_SVP_PUBLIC_RESPONSES",
        "SVP Statut : réponses écrites anonymisées publiées",
        "https://www.cig929394.fr/actualites/svp-statut-nos-reponses-a-vos-questions-nouvelles-ressources/",
        "Public article and linked publications",
        ("questions_statutaires", "situations_individuelles", "analyse_juridique"),
        "Answers produced for CIG Petite Couronne affiliated authorities; check context",
        "EDITORIAL_LEGAL_ANALYSIS",
    ),
    CIGPublicResource(
        "CIG_MINUTE_STATUT_CATALOG",
        "Podcasts Minute Statut",
        "https://www.cig929394.fr/je-souhaite-acceder-aux-publications-et-ressources-du-cig/?a=1&categorie=podcasts&date=&f=1&recherche=Minute+Statut&sous-categorie=",
        "Podcast catalogue",
        ("actualite_statutaire", "procedures_rh", "droits_agents"),
        "FPT-oriented; each episode requires individual date and scope validation",
        "EDITORIAL_EXPLANATION",
    ),
    CIGPublicResource(
        "CIG_PUBLICATION_CATALOG",
        "Catalogue public des publications et ressources du CIG",
        "https://www.cig929394.fr/je-souhaite-acceder-aux-publications-et-ressources-du-cig/",
        "Catalogue",
        ("veille_statutaire", "documentation_fpt", "ressources_syndicales"),
        "CIG Petite Couronne; some resources may be specific to 92/93/94",
        "DISCOVERY_INDEX",
    ),
)


def get_public_resources_for_theme(theme: str) -> tuple[CIGPublicResource, ...]:
    """Find catalogue entries by exact normalized theme key."""
    key = theme.strip().lower()
    if not key:
        return ()
    return tuple(item for item in CIG_PUBLIC_RESOURCES if key in item.themes)


def public_resource_metadata(resource_id: str) -> dict[str, object] | None:
    """Return safe citation metadata; never claim the content was ingested."""
    item = next((r for r in CIG_PUBLIC_RESOURCES if r.resource_id == resource_id), None)
    if item is None:
        return None
    return {
        "source_type": "CIG_PUBLIC_RESOURCE",
        "source_id": item.resource_id,
        "title": item.title,
        "official_url": item.url,
        "format": item.format,
        "themes": list(item.themes),
        "territorial_scope": item.territorial_scope,
        "source_role": item.source_role,
        "content_status": item.content_status,
        "legal_weight": "NON_BINDING_EDITORIAL_OR_PRACTICAL_RESOURCE",
        "publisher": "CIG Petite Couronne",
    }
