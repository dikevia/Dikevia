"""Recherche CGFP enrichie par concepts juridiques explicites.

Le moteur reste déterministe et lexical : les synonymes améliorent le rappel,
les ancrages dans le texte évitent les faux positifs et les scores servent
uniquement à ordonner les documents à examiner. Aucun statut juridique n'est déduit.
"""
from __future__ import annotations

from typing import Any
import re

from .cgfp import get_cgfp_article, normalize, search_cgfp as lexical_search


_TOPICS: tuple[dict[str, Any], ...] = (
    {
        "key": "protection_fonctionnelle",
        "triggers": (
            "protection fonctionnelle", "insult", "injur", "menace", "violence",
            "outrage", "diffam", "agression", "attaque", "propos blessant",
            "propos humiliant", "rabaisser",
        ),
        "expansion": (
            "protection fonctionnelle attaques injures menaces violences "
            "diffamations outrages dignité intégrité agent public"
        ),
        "anchors": (
            "protection fonctionnelle", "injure", "menace", "violence",
            "attaque", "outrage", "diffamation",
        ),
        "boosts": {
            "protection fonctionnelle": 14.0, "injure": 9.0, "menace": 6.0,
            "violence": 6.0, "attaque": 6.0, "outrage": 6.0,
            "diffamation": 5.0,
        },
        "exclude_unless_anchor": ("harcelement sexuel", "connotation sexuelle"),
    },
    {
        "key": "harcelement_moral",
        "triggers": (
            "harcelement moral", "agissements repetes", "degradation des conditions",
            "humiliations repetees", "mise a l ecart repetee",
        ),
        "expansion": (
            "harcèlement moral agissements répétés dégradation conditions travail "
            "dignité santé physique mentale avenir professionnel"
        ),
        "anchors": (
            "harcelement moral", "agissements repetes", "degradation des conditions",
            "sante physique ou mentale", "dignite", "avenir professionnel",
        ),
        "boosts": {
            "harcelement moral": 14.0, "agissements repetes": 10.0,
            "degradation des conditions": 7.0, "sante physique ou mentale": 5.0,
        },
        "exclude_unless_anchor": (),
    },
    {
        "key": "harcelement_sexuel",
        "triggers": (
            "harcelement sexuel", "propos sexistes", "agissement sexiste",
            "connotation sexuelle", "agression sexuelle",
        ),
        "expansion": (
            "harcèlement sexuel propos comportements connotation sexuelle "
            "pression grave répétée agissement sexiste dignité"
        ),
        "anchors": (
            "harcelement sexuel", "connotation sexuelle", "agissement sexiste",
            "propos sexistes",
        ),
        "boosts": {"harcelement sexuel": 14.0, "agissement sexiste": 8.0},
        "exclude_unless_anchor": (),
    },
    {
        "key": "discipline",
        "triggers": (
            "sanction disciplinaire", "procedure disciplinaire", "avertissement",
            "blame", "exclusion temporaire", "revocation", "conseil de discipline",
            "suspension disciplinaire",
        ),
        "expansion": (
            "sanction disciplinaire faute procédure droits défense avertissement blâme "
            "exclusion temporaire révocation conseil discipline proportionnalité"
        ),
        "anchors": (
            "sanction disciplinaire", "procedure disciplinaire", "avertissement",
            "blame", "exclusion temporaire", "revocation", "conseil de discipline",
        ),
        "boosts": {"sanction disciplinaire": 12.0, "procedure disciplinaire": 9.0},
        "exclude_unless_anchor": (),
    },
    {
        "key": "maladie_service",
        "triggers": (
            "accident de service", "maladie professionnelle", "imputable au service",
            "conge longue maladie", "conge longue duree", "citis",
            "arret maladie", "conge maladie",
        ),
        "expansion": (
            "accident de service maladie professionnelle imputabilité au service CITIS "
            "congé maladie congé longue maladie congé longue durée soins arrêt"
        ),
        "anchors": (
            "accident de service", "maladie professionnelle", "imputable au service",
            "citis", "conge de longue maladie", "conge de longue duree",
            "conge de maladie",
        ),
        "boosts": {"accident de service": 12.0, "maladie professionnelle": 12.0, "citis": 10.0},
        "exclude_unless_anchor": (),
    },
    {
        "key": "heures_supplementaires_ihts",
        "triggers": (
            "heures supplementaires", "heure supplementaire", "heures sup",
            "heures supp", "heures supolementaires", "heure supolementaire",
            "heures supllementaires", "ihts",
            "indemnites horaires pour travaux supplementaires",
            "travaux supplementaires",
        ),
        "expansion": (
            "indemnités horaires pour travaux supplémentaires IHTS "
            "décret 2002-60 décret 91-875 décret 2001-623 "
            "heures supplémentaires heures complémentaires cycle de travail "
            "bornes horaires demande expresse autorité territoriale "
            "délibération assemblée délibérante repos compensateur indemnisation "
            "contrôle décompte des heures cadre d'emplois catégorie B catégorie C"
        ),
        "anchors": (
            "heures supplementaires", "heure supplementaire",
            "indemnites horaires pour travaux supplementaires",
            "travaux supplementaires", "repos compensateur",
            "cycle de travail", "decret 2002 60", "decret 91 875",
            "decret 2001 623",
        ),
        "boosts": {
            "heures supplementaires": 16.0,
            "indemnites horaires pour travaux supplementaires": 18.0,
            "repos compensateur": 7.0,
            "cycle de travail": 6.0,
            "decret 2002 60": 8.0,
            "decret 91 875": 10.0,
            "decret 2001 623": 8.0,
        },
        "exclude_unless_anchor": (),
    },
    {
        "key": "remuneration",
        "triggers": (
            "remuneration", "traitement indiciaire", "salaire", "prime", "indemnite",
            "ifse", "nbi", "rifseep", "heures supplementaires",
        ),
        "expansion": (
            "rémunération traitement indiciaire salaire indemnité primes NBI IFSE "
            "RIFSEEP régime indemnitaire heures supplémentaires"
        ),
        "anchors": (
            "remuneration", "traitement indiciaire", "indemnite", "prime",
            "nouvelle bonification indiciaire", "nbi", "ifse",
        ),
        "boosts": {"remuneration": 12.0, "traitement indiciaire": 10.0},
        "exclude_unless_anchor": (),
    },
    {
        "key": "temps_travail",
        "triggers": (
            "temps de travail", "duree du travail", "temps partiel", "heures supplementaires",
            "astreinte", "conges annuels", "rtt", "annualisation", "horaires",
        ),
        "expansion": (
            "durée temps de travail temps partiel horaires annualisation RTT astreintes "
            "heures supplémentaires congés annuels repos"
        ),
        "anchors": (
            "temps de travail", "duree du travail", "temps partiel", "astreinte",
            "heures supplementaires", "conges annuels", "repos",
        ),
        "boosts": {"temps de travail": 12.0, "duree du travail": 10.0, "temps partiel": 8.0},
        "exclude_unless_anchor": (),
    },
    {
        "key": "charge_travail_conditions_travail",
        "triggers": (
            "charge de travail", "surcharge de travail", "trop de travail",
            "plus de travail que mes collegues", "plus de travail que les collegues",
            "repartition du travail", "taches supplementaires", "plein de travail",
            "inegalite de charge", "menace de me donner du travail",
        ),
        "expansion": (
            "charge de travail surcharge répartition des tâches organisation du travail "
            "conditions de travail risques psychosociaux santé physique mentale prévention "
            "harcèlement moral agissements répétés dégradation conditions de travail"
        ),
        "anchors": (
            "charge de travail", "conditions de travail", "sante physique ou mentale",
            "prevention des risques professionnels", "risques psychosociaux",
            "harcelement moral", "dignite", "avenir professionnel",
        ),
        "boosts": {
            "charge de travail": 12.0, "conditions de travail": 7.0,
            "prevention des risques professionnels": 6.0,
            "harcelement moral": 5.0,
        },
        "exclude_unless_anchor": (),
    },
    {
        "key": "agents_contractuels",
        "triggers": (
            "agent contractuel", "contractuel", "cdd", "cdi", "renouvellement de contrat",
            "fin de contrat", "licenciement contractuel",
        ),
        "expansion": (
            "agent contractuel contrat durée déterminée CDD CDI renouvellement recrutement "
            "licenciement fin de contrat rémunération droits"
        ),
        "anchors": (
            "agent contractuel", "contrat a duree determinee", "contrat a duree indeterminee",
            "renouvellement du contrat", "licenciement",
        ),
        "boosts": {"agent contractuel": 12.0, "contrat a duree determinee": 8.0},
        "exclude_unless_anchor": (),
    },
)


def _matching_topics(query: str) -> list[dict[str, Any]]:
    folded = normalize(query)
    matched = [
        topic for topic in _TOPICS
        if any(normalize(trigger) in folded for trigger in topic["triggers"])
    ]
    # Overtime/IHTS is a specific compensation topic. Do not also activate
    # generic remuneration and working-time topics for the same phrase,
    # otherwise their broad anchors reintroduce unrelated CGFP articles.
    overtime = [topic for topic in matched if topic["key"] == "heures_supplementaires_ihts"]
    return overtime or matched


def search_cgfp(query: str, limit: int = 8) -> dict[str, Any]:
    """Return ranked CGFP leads, with domain-specific precision safeguards."""
    safe_limit = max(1, min(int(limit), 20))
    base = lexical_search(query, limit=20)
    # An explicit article number is a direct lookup, never a lexical search.
    # The BM25 engine also scores ordinary words in the question; returning its
    # top hits when the requested reference is absent creates convincing but
    # unrelated articles (for example L999-999 -> R134-4, L822-8, ...).
    reference_match = re.search(r"\b([LRD])\s*(\d+(?:-\d+)*)", query, re.IGNORECASE)
    if reference_match:
        requested_ref = (reference_match.group(1) + reference_match.group(2)).upper()
        exact_results = [
            item for item in base.get("results", [])
            if re.sub(r"\s+", "", str(item.get("article") or "")).upper() == requested_ref
        ]
        return {
            **base,
            "results": exact_results[:safe_limit],
            "search_mode": "reference_directe",
            "requested_reference": requested_ref,
            "reference_found_in_snapshot": bool(exact_results),
        }

    topics = _matching_topics(query)
    if not topics:
        # A generic word such as "travail" must not make dozens of unrelated
        # CGFP articles look relevant. Keep only meaningful lexical matches;
        # explicit article references were already handled above.
        generic_terms = {
            "mon", "ma", "mes", "ton", "ta", "tes", "son", "sa", "ses",
            "dans", "avec", "pour", "par", "sur", "une", "des", "les", "aux",
            "est", "sont", "que", "qui", "quoi", "quel", "quelle", "quels",
            "quelles", "comment", "quand", "doit", "peut", "faire", "fait",
            "agent", "agents", "fonction", "fonctionnaire", "fonctionnaires",
            "territorial", "territoriaux", "territoriale", "territoriales",
            "collectivite", "collectivites", "public", "publique", "publiques",
            "publics", "article", "code", "travail",
        }
        query_terms = set(re.findall(r"[a-z0-9]{3,}", normalize(query))) - generic_terms
        lexical_results = []
        for item in base.get("results", []):
            article = get_cgfp_article(item["article"]) or {}
            body = normalize(str(article.get("text") or item.get("excerpt") or ""))
            overlap = sum(1 for term in query_terms if term in body)
            # Require at least two distinct query concepts. A generic match
            # on a single word such as "travail" is not enough.
            if overlap >= 2:
                lexical_results.append(item)
        # If the question contains no discriminating legal concept (for
        # example, "les fonctionnaires territoriaux"), keep the lexical
        # engine's best hits as documentary leads instead of returning an
        # empty result set. These broad hits remain explicitly unverified
        # and are never sufficient on their own to trigger a legal conclusion.
        broad_fallback = not lexical_results
        if broad_fallback:
            lexical_results = base.get("results", [])
        return {
            **base,
            "results": [
                {**item, "relevance_label": (
                    "Piste documentaire large — pertinence à vérifier"
                    if broad_fallback else "Correspondance lexicale à confirmer"
                )}
                for item in lexical_results[:safe_limit]
            ],
            "search_mode": "lexical_broad_fallback" if broad_fallback else "lexical",
        }

    expansion = " ".join(topic["expansion"] for topic in topics)
    enriched = lexical_search((query[:350] + " " + expansion)[:500], limit=20)
    merged: dict[str, dict[str, Any]] = {}
    for item in base.get("results", []):
        merged[item["article"]] = {**item, "_original_score": float(item.get("score", 0.0))}
    for item in enriched.get("results", []):
        current = merged.get(item["article"], {})
        merged[item["article"]] = {
            **current, **item,
            "_original_score": max(
                float(current.get("_original_score", 0.0)),
                float(item.get("score", 0.0)) * 0.72,
            ),
        }

    ranked: list[dict[str, Any]] = []
    for ref, item in merged.items():
        article = get_cgfp_article(ref) or {}
        body = normalize(str(article.get("text") or item.get("excerpt") or ""))
        matched_anchors: list[str] = []
        score = float(item.get("_original_score", item.get("score", 0.0)))
        excluded = False
        for topic in topics:
            topic_anchors = [anchor for anchor in topic["anchors"] if normalize(anchor) in body]
            matched_anchors.extend(topic_anchors)
            if topic["exclude_unless_anchor"] and any(
                normalize(term) in body for term in topic["exclude_unless_anchor"]
            ) and not topic_anchors:
                excluded = True
            for phrase, boost in topic["boosts"].items():
                if normalize(phrase) in body:
                    score += boost
        if excluded or not matched_anchors:
            continue
        unique_anchors = list(dict.fromkeys(matched_anchors))
        ranked.append({
            **{k: v for k, v in item.items() if not k.startswith("_")},
            "score": round(score, 4),
            "matched_concepts": unique_anchors[:6],
            "relevance_label": "Fondement à examiner en priorité" if score >= 10 else "Disposition complémentaire à examiner",
        })

    # L134-10 ne concerne que des catégories précises d'agents publics
    # (notamment préfets, administration pénitentiaire et douanes). Ne pas le
    # présenter comme piste prioritaire aux autres agents.
    special_categories = (
        "prefet", "sous-prefet", "administration penitentiaire",
        "agent penitentiaire", "douanes", "douanier",
    )
    if not any(normalize(term) in normalize(query) for term in special_categories):
        ranked = [item for item in ranked if item.get("article") != "L134-10"]

    ranked.sort(key=lambda item: (-float(item["score"]), item["article"]))
    for index, item in enumerate(ranked):
        if index == 0:
            item["relevance_label"] = "Premier résultat à examiner"
    return {
        **base,
        "results": ranked[:safe_limit],
        "search_mode": "concepts_juridiques",
        "detected_topics": [topic["key"] for topic in topics],
    }
