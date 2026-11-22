"""Conservative public-service scope classifier for Légifrance regulatory hits.

A text is eligible for case-specific FPT analysis only when its own content
supports a territorial or genuinely cross-public-service scope. Ambiguous
records remain visible as research leads but are not sent to Gemini as applicable
law. This is a relevance guard, not a legal applicability determination.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any


_FPT_MARKERS = (
    "fonction publique territoriale",
    "fonctionnaire territorial",
    "fonctionnaires territoriaux",
    "agent territorial",
    "agents territoriaux",
    "agents publics territoriaux",
    "collectivites territoriales",
    "collectivite territoriale",
    "centre national de la fonction publique territoriale",
    "cnfpt",
    "centres de gestion",
    "centre de gestion",
    "conseil superieur de la fonction publique territoriale",
    "communes et leurs etablissements publics",
    "departements et regions",
    "maires et presidents d etablissements publics",
    "decret 88-145", "decret n 88 145",
    "decret 87-602", "decret n 87 602",
    "decret 89-677", "decret n 89 677",
    "decret 91-298", "decret n 91 298",
)

_FPH_MARKERS = (
    "fonction publique hospitaliere",
    "etablissements publics de sante",
    "personnels hospitaliers",
    "personnels medicaux",
    "directeur d hopital",
    "centres hospitaliers",
)

_FPE_MARKERS = (
    "fonction publique de l etat",
    "fonctionnaires de l etat",
    "agents de l etat",
    "administrations centrales",
    "services deconcentres de l etat",
    "ministeres",
)

_LOCAL_EMPLOYER_MARKERS = (
    "commune", "mairie", "centre communal d action sociale",
    "etablissement public de cooperation intercommunale", "epci",
    "metropole", "departement", "region",
)

_EMPLOYMENT_CONTEXT_MARKERS = (
    "agent public", "agents publics", "agent territorial", "agents territoriaux",
    "fonctionnaire", "fonctionnaires", "contractuel", "contractuels",
    "personnel communal", "personnels communaux", "personnel territorial",
    "mesure disciplinaire", "procedure disciplinaire", "recrutement",
    "remuneration", "contrat de travail", "licenciement", "sanction disciplinaire",
)

_GENERAL_MARKERS = (
    "code general de la fonction publique",
    "fonction publique",
    "agents publics",
    "fonctionnaires",
    "droits et obligations des fonctionnaires",
    "discipline des fonctionnaires",
    "protection fonctionnelle",
)

# These formulations explicitly establish a common scope across all three
# public-service branches. Generic references to "agents publics" alone do not.
_COMMON_PUBLIC_SERVICE_MARKERS = (
    "les trois versants de la fonction publique",
    "les trois fonctions publiques",
    "fonction publique de l etat territoriale et hospitaliere",
    "fonction publique de l etat territoriale et de l hospitaliere",
    "agents des trois versants",
    "agents des trois fonctions publiques",
)


def _fold(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def classify_public_service_scope(source: dict[str, Any]) -> dict[str, Any]:
    """Return a conservative scope label and whether this hit may reach Gemini."""
    title = str(source.get("title") or "")
    text = str(source.get("full_text") or source.get("text") or source.get("excerpt") or "")
    corpus = _fold((title + " " + text)[:500_000])
    # Dikévia is deliberately limited to French territorial public-service law.
    # Exclude EU instruments by structured metadata before looking at generic
    # public-service wording that may also appear in comparative documents.
    european_metadata = _fold(" ".join(str(source.get(key) or "") for key in (
        "jurisdiction", "source_type", "official_source", "document_kind"
    )))
    title_folded = _fold(title)
    direct_eu_instrument_title = title_folded.startswith((
        "directive ue ", "directive europeenne ", "reglement ue ",
        "reglement europeen ", "decision ue ", "decision europeenne ",
    ))
    if direct_eu_instrument_title or any(marker in european_metadata for marker in (
        "european union", "union europeenne", "eur lex", "eurlex",
        "eu regulation", "eu directive", "european directive",
        "european treaty", "european law", "droit europeen",
        "convention europeenne",
    )) or _fold(str(source.get("jurisdiction") or "")) in {"eu", "ue"}:
        return {
            "scope": "OUT_OF_SCOPE_EUROPEAN_LAW",
            "evidence": ["Instrument de droit de l'Union européenne hors périmètre Dikévia"],
            "analysis_eligible": False,
        }

    fpt_hits = [marker for marker in _FPT_MARKERS if _fold(marker) in corpus]
    fph_hits = [marker for marker in _FPH_MARKERS if _fold(marker) in corpus]
    fpe_hits = [marker for marker in _FPE_MARKERS if _fold(marker) in corpus]

    # Narrow FPT bridge: decree n° 2002-60 is the IHTS reference regime
    # used through the territorial indemnity framework. The prompt still
    # requires decree n° 91-875 and the local deliberation to be checked.
    is_ihts_reference = (
        "2002 60" in corpus
        and "indemnites horaires pour travaux supplementaires" in corpus
    )
    if is_ihts_reference:
        return {
            "scope": "FPT_REFERENCE",
            "evidence": ["Décret 2002-60 : référence IHTS à vérifier avec le décret 91-875 et la délibération locale"],
            "analysis_eligible": True,
        }

    # A territorial reference buried in the body must not override a source
    # whose title identifies it as an FPE/FPH instrument. Titles are a stronger
    # signal of the document's primary scope than incidental cross-references.
    title_fpt_hits = [marker for marker in _FPT_MARKERS if _fold(marker) in title_folded]
    title_fpe_hits = [marker for marker in _FPE_MARKERS if _fold(marker) in title_folded]
    title_fph_hits = [marker for marker in _FPH_MARKERS if _fold(marker) in title_folded]
    if (title_fpe_hits or title_fph_hits) and not title_fpt_hits:
        return {
            "scope": "FPH" if title_fph_hits else "FPE",
            "evidence": (title_fph_hits or title_fpe_hits)[:3],
            "analysis_eligible": False,
        }

    # A common rule may support FPT analysis only when the source itself
    # explicitly identifies the three branches. Generic public-service wording
    # is not sufficient evidence of territorial applicability.
    common_scope_hits = [
        marker for marker in _COMMON_PUBLIC_SERVICE_MARKERS
        if _fold(marker) in corpus
    ]
    if common_scope_hits:
        return {
            "scope": "COMMON_PUBLIC_SERVICE",
            "evidence": common_scope_hits[:3],
            "analysis_eligible": True,
            "claim_eligible": True,
        }

    # If the body contains competing versant markers and the title does not
    # identify a territorial instrument, its primary scope is unresolved.
    if fpt_hits and (fpe_hits or fph_hits) and not title_fpt_hits:
        return {
            "scope": "OUT_OF_SCOPE_OR_UNCONFIRMED",
            "evidence": (fpt_hits[:2] + fpe_hits[:1] + fph_hits[:1]),
            "analysis_eligible": False,
        }

    if fpt_hits:
        return {
            "scope": "FPT",
            "evidence": fpt_hits[:3],
            "analysis_eligible": True,
        }
    if fph_hits:
        return {
            "scope": "FPH",
            "evidence": fph_hits[:3],
            "analysis_eligible": False,
        }
    if fpe_hits:
        return {
            "scope": "FPE",
            "evidence": fpe_hits[:3],
            "analysis_eligible": False,
        }

    # Administrative case law often names the local employer ("commune de…")
    # rather than repeating the words "fonction publique territoriale".
    # Accept that combination only when the same decision also concerns an
    # employment/HR subject; a municipal planning case must not pass this guard.
    local_employer_hits = [
        marker for marker in _LOCAL_EMPLOYER_MARKERS if _fold(marker) in corpus
    ]
    employment_context_hits = [
        marker for marker in _EMPLOYMENT_CONTEXT_MARKERS if _fold(marker) in corpus
    ]
    if local_employer_hits and employment_context_hits:
        return {
            "scope": "FPT",
            "evidence": (local_employer_hits[:2] + employment_context_hits[:2]),
            "analysis_eligible": True,
        }

    general_hits = [marker for marker in _GENERAL_MARKERS if _fold(marker) in corpus]
    if len(general_hits) >= 2:
        return {
            "scope": "GENERAL_PUBLIC_SERVICE",
            "evidence": general_hits[:3],
            # May be supplied to the model as context, but never as proof
            # of FPT applicability or as direct support for a legal claim.
            "analysis_eligible": True,
            "claim_eligible": False,
        }
    if general_hits:
        return {
            "scope": "GENERAL_PUBLIC_SERVICE",
            "evidence": general_hits[:2],
            "analysis_eligible": False,
            "claim_eligible": False,
        }
    return {
        # Do not let an unclassified document enter the AI evidence set.
        # The user-facing research may still disclose it as an unverified lead.
        "scope": "OUT_OF_SCOPE_OR_UNCONFIRMED",
        "evidence": general_hits[:2],
        "analysis_eligible": False,
    }

_IHTS_QUERY_MARKERS = (
    "heures supplementaires", "heure supplementaire", "heures sup",
    "heures supp", "heures supolementaires", "heure supolementaire",
    "ihts", "travaux supplementaires",
)

_IHTS_SOURCE_MARKERS = (
    "indemnites horaires pour travaux supplementaires",
    "indemnite horaire pour travaux supplementaires",
    "indemnites horaires de travaux supplementaires",
    "ihts",
    "2002 60",
    "91 875",
    "repos compensateur des heures supplementaires",
    "repos compensateur au titre des heures supplementaires",
)


def is_ihts_question(question: str) -> bool:
    """Identify overtime/IHTS questions that need the territorial implementing decree."""
    folded_question = _fold(str(question or ""))
    return any(_fold(marker) in folded_question for marker in _IHTS_QUERY_MARKERS)


def is_ihts_relevant_source(question: str, source: dict[str, Any]) -> bool:
    """Reject generic hour credits and unrelated CGFP hits for IHTS questions."""
    if not is_ihts_question(question):
        return True

    title = str(source.get("title") or "")
    article = str(source.get("article") or source.get("article_id") or "")
    text = str(source.get("full_text") or source.get("text") or source.get("excerpt") or "")
    corpus = _fold((title + " " + article + " " + text)[:500_000])

    # Explicitly exclude unrelated CGFP provisions that use "heures
    # supplémentaires" to describe CPF credits or union time credits.
    excluded_articles = ("r422 96", "l422 15", "r214 28", "r214 32", "r214 33")
    if any(_fold(code) in corpus for code in excluded_articles):
        return False

    # Generic mentions of extra hours are not enough: require the IHTS
    # terminology or one of the implementing/reference decrees.
    return any(_fold(marker) in corpus for marker in _IHTS_SOURCE_MARKERS)



# Narrow topic families used only to reject an obviously unrelated retrieval hit.
# They are not legal taxonomies: broad or unclassified sources remain eligible
# for review so that cross-cutting provisions are not accidentally discarded.
_TOPIC_FAMILIES = {
    "SICK_LEAVE": (
        "conge maladie", "conge de maladie", "conge longue maladie",
        "conge longue duree", "citis", "accident de service",
        "maladie professionnelle", "arret maladie",
    ),
    "LEAVE": (
        "conges annuels", "conge annuel", "conges bonifies",
        "autorisation speciale d absence", "absence pour raison familiale",
        "compte epargne temps",
    ),
    "REMUNERATION": (
        "remuneration", "traitement indiciaire", "regime indemnitaire",
        "rifseep", "ifse", "nbi", "indemnite", "prime", "paie",
    ),
    "WORKING_TIME": (
        "temps de travail", "duree du travail", "heures supplementaires",
        "travaux supplementaires", "ihts", "astreinte", "annualisation",
        "repos compensateur", "cycle de travail",
    ),
    "PART_TIME": (
        "temps partiel", "decret 2004 777",
    ),
    "NON_COMPLETE_TIME": (
        "temps non complet", "heures complementaires", "decret 2020 592",
    ),
    "DISCIPLINE": (
        "discipline", "sanction disciplinaire", "conseil de discipline",
        "exclusion temporaire", "blame", "revocation",
    ),
    "TELEWORK": (
        "teletravail", "travail a distance",
    ),
    "FUNCTIONAL_PROTECTION": (
        "protection fonctionnelle", "harcelement moral", "harcelement sexuel",
        "agissement sexiste",
    ),
    "TERMINATION_OF_TITULAR": (
        # Query-side expressions must classify the question too; keep generic
        # "titulaire" out of this family because it also appears in unrelated
        # CST provisions (e.g. titular members and substitutes).
        "me virer", "peut me virer", "me mettre dehors", "mettre dehors",
        "me licencier", "peut me licencier", "mettre fin a mes fonctions",
        "fin de mes fonctions", "licenciement", "radiation des cadres",
        "perte de la qualite de fonctionnaire", "cessation definitive de fonctions",
        "insuffisance professionnelle", "abandon de poste", "suppression d emploi",
    ),
    "STAFFING_AND_WORK_CONDITIONS": (
        "manque de personnel", "pas assez d agents", "pas suffisamment d agents",
        "on manque d agents", "on est pas assez nombreux", "on n est pas assez nombreux",
        "sous effectif", "effectif reduit", "effectifs insuffisants",
        "mon service est en sous effectif", "surcharge de travail",
        "charge de travail", "conditions de travail", "risques psychosociaux",
        "risques professionnels", "prevention des risques", "evaluation des risques",
        "sante et securite", "hygiene et securite", "conditions d hygiene et de securite",
        "protection de la sante physique et mentale", "medecine preventive",
        "service de medecine preventive", "assistant de prevention",
        "conseiller de prevention", "danger grave et imminent",
        "document unique", "formation specialisee", "comite social territorial",
    ),
    "UNION_RIGHTS": (
        "droit syndical", "autorisation speciale d absence syndicale",
        "decharge d activite de service", "heures de delegation",
        "local syndical", "activite syndicale",
        "suivi des agents a activite syndicale",
    ),
    "CST": (
        "comite social territorial", "formation specialisee",
        "comite technique", "instance de dialogue social",
    ),
    "PROFESSIONAL_EVALUATION": (
        "entretien professionnel", "evaluation professionnelle", "evaluation annuelle",
        "compte rendu d evaluation", "compte rendu d entretien",
        "valeur professionnelle", "appreciation de la valeur professionnelle",
    ),
    # Lexical false positives seen in official search results: these are
    # evaluations of policies, senior ministry jobs or recruitment skills,
    # not annual appraisals of territorial staff.
    "OTHER_EVALUATION": (
        "emplois superieurs", "evaluation des emplois", "politiques rh",
        "evaluation des politiques", "evaluation des competences",
        "competences en matiere de recrutement",
    ),
}


def _matched_topic_families(value: str) -> set[str]:
    folded = _fold(value)
    padded_text = f" {folded} "
    matched = {
        family
        for family, markers in _TOPIC_FAMILIES.items()
        if any(f" {_fold(marker)} " in padded_text for marker in markers)
    }
    # CET is also the ordinary French demonstrative "cet". Recognize it as
    # an acronym only when explicitly written in uppercase; the full phrase
    # "compte épargne-temps" is recognized regardless of capitalization.
    if re.search(r"\bCET\b", value):
        matched.add("LEAVE")
    return matched


def is_topic_relevant_source(question: str, source: dict[str, Any]) -> bool:
    """Reject only a source clearly belonging to another recognized topic family.

    Sources with no recognized family are retained as potentially cross-cutting
    legal provisions. This deliberately favors recall over aggressive filtering.
    """
    question_topics = _matched_topic_families(question)
    if not question_topics:
        return True
    source_text = " ".join(str(source.get(key) or "") for key in (
        "title", "article", "official_number", "excerpt", "text", "full_text"
    ))
    source_topics = _matched_topic_families(source_text[:500_000])
    # Do not let the similar wording "extra hours" merge two distinct FPT
    # regimes: decree 2004-777 concerns part-time IHTS conditions, while
    # decree 2020-592 governs complementary hours for permanent non-complete
    # jobs. A source explicitly limited to the opposite status is not evidence
    # for the user's status unless it also addresses that status.
    if (
        "PART_TIME" in question_topics
        and "NON_COMPLETE_TIME" in source_topics
        and "PART_TIME" not in source_topics
    ):
        return False
    if (
        "NON_COMPLETE_TIME" in question_topics
        and "PART_TIME" in source_topics
        and "NON_COMPLETE_TIME" not in source_topics
    ):
        return False
    if question_topics & source_topics:
        return True

    # For these two question families, a source with no identifiable subject
    # is not useful evidence: generic CGFP keyword hits must not masquerade
    # as a relevant answer.
    strict_topics = {
        "TERMINATION_OF_TITULAR",
        "STAFFING_AND_WORK_CONDITIONS",
        # Evaluation searches are especially prone to lexical false positives:
        # generic references to evaluating risks, health, senior civil-service
        # jobs or skills are not evidence about the annual FPT appraisal report.
        "PROFESSIONAL_EVALUATION",
    }
    if question_topics & strict_topics:
        # For annual-appraisal questions, an unclassified procedural source
        # (for example, a general administrative appeal rule) may still be
        # relevant. Reject only when the hit is positively classified as a
        # different legal topic; retain unknown cross-cutting sources.
        if "PROFESSIONAL_EVALUATION" not in question_topics or source_topics:
            return False
    if not source_topics:
        return True

    # Some legal mechanisms are structurally connected even when a text is
    # indexed under a neighboring family (e.g. IHTS within the territorial
    # compensation/indemnity framework). Keep these narrowly defined bridges.
    related_families = {
        "WORKING_TIME": {"REMUNERATION"},
        "REMUNERATION": {"WORKING_TIME", "SICK_LEAVE"},
        "SICK_LEAVE": {"REMUNERATION"},
    }
    return any(
        source_family in related_families.get(question_family, set())
        for question_family in question_topics
        for source_family in source_topics
    )
