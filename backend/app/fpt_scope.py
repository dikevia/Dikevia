"""Conservative public-service scope classifier for Légifrance regulatory hits.

A text is eligible for analysis only when its own content supports the selected
public-service branch (FPT, FPE or FPH), or an explicitly common rule. Ambiguous
records remain research leads rather than applicable-law evidence. This is a
relevance guard, not a legal applicability determination.
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
    "agent contractuel territorial",
    "agents contractuels territoriaux",
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
    "etablissement public de sante",
    "centres hospitaliers",
    "centre hospitalier",
    "agent hospitalier",
    "agents hospitaliers",
    "personnel hospitalier",
    "personnels hospitaliers",
    "agent contractuel hospitalier",
    "agents contractuels hospitaliers",
    "decret n 91 155",
    "decret 91 155",
    "loi n 86 33",
    "loi 86 33",
)

_FPE_MARKERS = (
    "fonction publique de l etat",
    "fonctionnaire de l etat",
    "fonctionnaires de l etat",
    "agent de l etat",
    "agents de l etat",
    "administration centrale",
    "administrations centrales",
    "service deconcentre de l etat",
    "services deconcentres de l etat",
    "agent contractuel de l etat",
    "agents contractuels de l etat",
    "decret n 86 83",
    "decret 86 83",
)

# These words can occur as incidental context and do not establish a
# branch by themselves. They may contribute to an ambiguity check when a
# strong marker for another branch is also present.
_FPH_CONTEXT_MARKERS = (
    "personnels hospitaliers",
    "personnels medicaux",
    "directeur d hopital",
)
_FPE_CONTEXT_MARKERS = ("ministeres",)


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


def classify_public_service_scope(
    source: dict[str, Any], target_versant: str = "FPT",
) -> dict[str, Any]:
    """Return a conservative scope label and eligibility for the selected versant."""
    target_versant = str(target_versant or "FPT").upper()
    if target_versant not in {"FPT", "FPE", "FPH"}:
        target_versant = "FPT"
    title = str(source.get("title") or "")
    # Classify the same relevant passage that can support a claim, not an
    # entire instrument whose unrelated chapters may mention another versant.
    text = str(source.get("excerpt") or source.get("text") or source.get("full_text") or "")
    article_ref = _fold(str(source.get("article") or source.get("article_id") or ""))
    corpus = _fold((title + " " + text)[:500_000])
    title_folded = _fold(title)

    # CGFP L111-1 expressly guarantees freedom of opinion to public agents.
    # This is a common statutory guarantee, not merely generic contextual
    # wording. Only the live Légifrance article may ground a claim.
    if (
        title_folded.startswith("code general de la fonction publique")
        and article_ref == "l111 1"
    ):
        official_live_article = source.get("source_type") == "LEGIFRANCE_API"
        return {
            "scope": "COMMON_PUBLIC_SERVICE",
            "evidence": [
                "Article L.111-1 du CGFP : liberté d'opinion garantie aux agents publics",
            ],
            "analysis_eligible": True,
            "claim_eligible": official_live_article,
        }

    # The CGFP chapter L823-1 to L823-6 states the common statutory TPT
    # framework for civil servants. Only a live Légifrance article may ground
    # a claim; a bundled snapshot remains contextual and cannot certify the
    # current wording. Branch-specific implementing rules must still be checked.
    if (
        title_folded.startswith("code general de la fonction publique")
        and article_ref in {f"l823 {number}" for number in range(1, 7)}
    ):
        official_live_article = source.get("source_type") == "LEGIFRANCE_API"
        return {
            "scope": "COMMON_PUBLIC_SERVICE",
            "evidence": [
                f"Article {article_ref.upper()} du CGFP : disposition statutaire commune relative au TPT",
                "Le texte réglementaire propre au versant doit être vérifié pour les modalités d'application",
            ],
            "analysis_eligible": True,
            "claim_eligible": official_live_article,
        }
    # CGFP L. 137-1 and L. 137-4 establish the composition and access
    # guarantees for every public agent's individual file.
    if title_folded.startswith("code general de la fonction publique") and article_ref in {
        "l137 1", "l137 4",
    }:
        official_live_article = source.get("source_type") == "LEGIFRANCE_API"
        article_evidence = (
            "Article L. 137-1 du CGFP : le dossier individuel comporte toutes les pièces intéressant la situation administrative de l'agent, enregistrées, numérotées et classées sans discontinuité"
            if article_ref == "l137 1"
            else "Article L. 137-4 du CGFP : tout agent public a accès à son dossier individuel"
        )
        return {
            "scope": "COMMON_PUBLIC_SERVICE",
            "evidence": [
                article_evidence,
                "Droit applicable à l'agent public, sous réserve de vérifier les modalités de communication pertinentes",
            ],
            "analysis_eligible": True,
            "claim_eligible": official_live_article,
        }

    # CGFP L. 532-4 sets the disciplinary-file disclosure and defence
    # guarantees applicable to civil servants across the three public-service
    # branches. The current wording has been in force since 1 October 2025.
    if title_folded.startswith("code general de la fonction publique") and article_ref == "l532 4":
        official_live_article = source.get("source_type") == "LEGIFRANCE_API"
        return {
            "scope": "COMMON_PUBLIC_SERVICE",
            "evidence": [
                "Article L. 532-4 du CGFP : droit à la communication de l'intégralité du dossier individuel et de ses annexes, ainsi qu'à l'assistance de défenseurs de son choix",
                "Garantie applicable lorsqu'une procédure disciplinaire est engagée contre un fonctionnaire",
            ],
            "analysis_eligible": True,
            "claim_eligible": official_live_article,
        }
    # CGFP L. 532-9 specifically governs referral to the disciplinary board
    # by a territorial authority and the content of its referral report.
    if title_folded.startswith("code general de la fonction publique") and article_ref == "l532 9":
        official_live_article = source.get("source_type") == "LEGIFRANCE_API"
        return {
            "scope": "FPT",
            "evidence": [
                "Article L. 532-9 du CGFP : en procédure disciplinaire, l'autorité territoriale saisit le conseil de discipline par un rapport précisant les faits reprochés et leurs circonstances",
            ],
            "analysis_eligible": True,
            "claim_eligible": official_live_article,
        }

    # CGFP L. 822-1 to L. 822-5 contain ordinary sick-leave statutory provisions.
    # Only a live Légifrance article may support a claim; snapshots remain contextual.
    if (
        title_folded.startswith("code general de la fonction publique")
        and article_ref in {f"l822 {number}" for number in range(1, 6)}
    ):
        official_live_article = source.get("source_type") == "LEGIFRANCE_API"
        return {
            "scope": "COMMON_PUBLIC_SERVICE",
            "evidence": [
                f"Article {article_ref.upper()} du CGFP : dispositions relatives aux congés de maladie",
                "Champ commun aux fonctionnaires des trois versants, sous réserve du texte applicable",
            ],
            "analysis_eligible": True,
            "claim_eligible": official_live_article,
        }

    if (
        "loi n 2017 1837" in title_folded
        and "article 115" in corpus
        and ("agents publics" in corpus or "agent public" in corpus)
    ):
        return {
            "scope": "COMMON_PUBLIC_SERVICE",
            "evidence": ["Article 115 de la loi n° 2017-1837 : délai de carence des agents publics"],
            "analysis_eligible": True,
            "claim_eligible": source.get("source_type") == "LEGIFRANCE_LODA",
        }

    # CITIS provisions remain contextual until their branch-specific scope and
    # implementing rules have been independently established.
    if target_versant == "FPT" and article_ref in {
        f"l822 {number}" for number in range(18, 24)
    }:
        return {
            "scope": "GENERAL_PUBLIC_SERVICE",
            "evidence": [
                f"Article {article_ref.upper()} du CGFP : piste de contexte uniquement",
                "Applicabilité FPT et dispositions réglementaires d'application à vérifier séparément",
            ],
            "analysis_eligible": True,
            "claim_eligible": False,
        }
    # Articles L. 332-8 to L. 332-14 belong to the CGFP subsection devoted
    # specifically to permanent contractual employment in the FPT. Their
    # individual wording does not always repeat the territorial scope.
    if target_versant == "FPT" and article_ref in {f"l332 {number}" for number in range(8, 15)}:
        return {
            "scope": "FPT",
            "evidence": [f"Article {article_ref.upper()} situé dans la sous-section FPT des emplois permanents contractuels"],
            "analysis_eligible": True,
        }
    # Dikévia handles French public-service law in the selected versant.
    # Exclude EU instruments by structured metadata before looking at generic
    # public-service wording that may also appear in comparative documents.
    european_metadata = _fold(" ".join(str(source.get(key) or "") for key in (
        "jurisdiction", "source_type", "official_source", "document_kind"
    )))
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
    fph_context_hits = [marker for marker in _FPH_CONTEXT_MARKERS if _fold(marker) in corpus]
    fpe_context_hits = [marker for marker in _FPE_CONTEXT_MARKERS if _fold(marker) in corpus]

    # A territorial reference buried in the body must not override a source
    # whose title identifies it as an FPE/FPH instrument. Titles are a stronger
    # signal of the document's primary scope than incidental cross-references.
    title_fpt_hits = [marker for marker in _FPT_MARKERS if _fold(marker) in title_folded]
    title_fpe_hits = [marker for marker in _FPE_MARKERS if _fold(marker) in title_folded]
    title_fph_hits = [marker for marker in _FPH_MARKERS if _fold(marker) in title_folded]
    common_scope_hits = [
        marker for marker in _COMMON_PUBLIC_SERVICE_MARKERS
        if _fold(marker) in corpus
    ]
    # An explicit statement that a provision covers all three branches takes
    # precedence over a title that names only two of them.
    if common_scope_hits:
        return {
            "scope": "COMMON_PUBLIC_SERVICE",
            "evidence": common_scope_hits[:3],
            "analysis_eligible": True,
            "claim_eligible": True,
        }
    if title_fpe_hits and title_fph_hits and not title_fpt_hits:
        return {
            "scope": "MIXED_OR_CONFLICTING_PUBLIC_SERVICE_SCOPE",
            "evidence": title_fpe_hits[:2] + title_fph_hits[:2],
            "analysis_eligible": False,
            "claim_eligible": False,
        }
    if (title_fpe_hits or title_fph_hits) and not title_fpt_hits:
        title_scope = "FPH" if title_fph_hits else "FPE"
        return {
            "scope": title_scope,
            "evidence": (title_fph_hits or title_fpe_hits)[:3],
            "analysis_eligible": title_scope == target_versant,
            "claim_eligible": title_scope == target_versant,
        }

    # Narrow FPT bridge: decree n° 2002-60 is the IHTS reference regime
    # used through the territorial indemnity framework. The prompt still
    # requires decree n° 91-875 and the local deliberation to be checked.
    is_ihts_reference = (
        "2002 60" in title_folded
        and "indemnites horaires pour travaux supplementaires" in title_folded
    )
    if is_ihts_reference:
        return {
            "scope": "FPT_REFERENCE",
            "evidence": ["Décret 2002-60 : référence IHTS à vérifier avec le décret 91-875 et la délibération locale"],
            "analysis_eligible": target_versant == "FPT",
            "claim_eligible": target_versant == "FPT",
        }

    # A common rule may support analysis for the selected versant only when
    # the source itself explicitly identifies all three branches. Generic
    # public-service wording is not sufficient evidence of cross-branch scope.
    # When the title does not establish a primary branch, simultaneous State
    # and hospital references in the relevant passage are ambiguous. Do not
    # let the later single-branch fallback silently prefer FPH.
    if (
        fpe_hits and (fph_hits or fph_context_hits)
        or fph_hits and (fpe_hits or fpe_context_hits)
    ) and not (title_fpt_hits or title_fpe_hits or title_fph_hits) and not common_scope_hits:
        return {
            "scope": "MIXED_OR_CONFLICTING_PUBLIC_SERVICE_SCOPE",
            "evidence": fpe_hits[:2] + fph_hits[:2] + fpe_context_hits[:1] + fph_context_hits[:1],
            "analysis_eligible": False,
            "claim_eligible": False,
        }
    # A source containing competing territorial and State/hospital markers
    # is not safe FPT proof, even when one marker appears in its title.
    if title_fpt_hits and (title_fpe_hits or title_fph_hits):
        return {
            "scope": "MIXED_OR_CONFLICTING_PUBLIC_SERVICE_SCOPE",
            "evidence": title_fpt_hits[:2] + title_fpe_hits[:1] + title_fph_hits[:1],
            "analysis_eligible": False,
            "claim_eligible": False,
        }

    # If the body contains competing versant markers and the title does not
    # identify a territorial instrument, its primary scope is unresolved.
    if fpt_hits and (fpe_hits or fph_hits or fpe_context_hits or fph_context_hits) and not title_fpt_hits:
        return {
            "scope": "OUT_OF_SCOPE_OR_UNCONFIRMED",
            "evidence": (fpt_hits[:2] + fpe_hits[:1] + fph_hits[:1] + fpe_context_hits[:1] + fph_context_hits[:1]),
            "analysis_eligible": False,
        }

    if fpt_hits:
        return {
            "scope": "FPT",
            "evidence": fpt_hits[:3],
            "analysis_eligible": target_versant == "FPT",
            "claim_eligible": target_versant == "FPT",
        }
    if fph_hits:
        return {
            "scope": "FPH",
            "evidence": fph_hits[:3],
            "analysis_eligible": target_versant == "FPH",
            "claim_eligible": target_versant == "FPH",
        }
    if fpe_hits:
        return {
            "scope": "FPE",
            "evidence": fpe_hits[:3],
            "analysis_eligible": target_versant == "FPE",
            "claim_eligible": target_versant == "FPE",
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
    if target_versant == "FPT" and local_employer_hits and employment_context_hits:
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


def is_ihts_relevant_source(
    question: str, source: dict[str, Any], target_versant: str = "FPT",
) -> bool:
    """Apply the IHTS-specific FPT guard only to territorial public-service questions."""
    if str(target_versant or "FPT").upper() != "FPT" or not is_ihts_question(question):
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
        "conge longue duree", "maladie professionnelle", "arret maladie",
    ),
    # Ordinary sick leave (CMO) and service-related leave (CITIS) are
    # legally distinct mechanisms. A lexical hit on "congé de maladie"
    # must not make a CITIS provision evidence for a CMO question.
    "ORDINARY_SICK_LEAVE": (
        "conge de maladie ordinaire", "maladie ordinaire", "cmo",
        "jour de carence", "jours de carence",
    ),
    "CITIS": (
        "citis", "conge pour invalidite temporaire imputable au service",
        "invalidite temporaire imputable au service", "accident de service",
        "accident de trajet", "maladie contractee en service",
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
        "discipline", "disciplinaire", "procedure disciplinaire",
        "sanction disciplinaire", "conseil de discipline",
        "exclusion temporaire", "blame", "revocation",
    ),
    "TELEWORK": (
        "teletravail", "travail a distance",
    ),
    "FUNCTIONAL_PROTECTION": (
        "protection fonctionnelle", "harcelement moral", "harcelement sexuel",
        "agissement sexiste",
    ),
    "FAMILY_BEREAVEMENT": (
        "deces d un proche", "deces d un membre de la famille",
        "deces d un ascendant", "deces du grand pere", "deces de la grand mere",
        "deces de son grand pere", "deces de sa grand mere",
        "deces de mon grand pere", "deces de ma grand mere",
        "grand pere decede", "grand mere decedee", "grand parent decede",
        "obseques", "autorisation d absence pour deces", "conge pour deces",
        "conge de deuil", "justificatif de deces", "acte de deces",
        # A kinship document alone does not establish a bereavement question.

    ),
    "UNION_ASSISTANCE": (
        "accompagnement syndical", "assistance syndicale",
        "accompagnement par un representant syndical",
        "assistance d un representant syndical",
        "assiste par un representant syndical",
        "se faire assister", "assistance par un defenseur",
        "assistance du fonctionnaire", "droits de la defense",
        "entretien disciplinaire", "entretien prealable",
        "convocation a un entretien hierarchique",
    ),
    "AGGRESSION_AGENT_PROTECTION": (
        "agression", "agresse par un usager", "agressions",
        "violence", "menace d un usager", "insulte d un usager",
        "incident avec un usager", "signalement d agression",
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
    "REPORT_HIERARCHICAL_CONTESTATION": (
        "rapport hierarchique", "rapport contre moi", "rapport fait contre moi",
        "mon chef a fait un rapport", "mon superieur a fait un rapport",
        "rapport a charge", "rapport defavorable", "rapport circonstancie",
        "contester un rapport de mon chef", "contester le rapport de mon superieur",
    ),
    "INDIVIDUAL_FILE": (
        "dossier individuel", "communication du dossier", "consultation du dossier",
        "acces au dossier", "pieces du dossier", "documents verses au dossier",
        "verse au dossier individuel",
    ),
    "PROFESSIONAL_EVALUATION": (
        "entretien professionnel", "evaluation professionnelle", "evaluation annuelle",
        "compte rendu d evaluation", "compte rendu d entretien",
        "valeur professionnelle", "appreciation de la valeur professionnelle",
    ),
    "AVAILABILITY": (
        "disponibilite", "mise en disponibilite", "disponibilite pour convenances personnelles",
        "convenances personnelles", "disponibilite d office", "disponibilite sur demande",
    ),
    "CONTRACTUAL_STATUS": (
        "agent contractuel", "agents contractuels", "contractuel territorial",
        "contractuelle", "cdd", "cdi", "contrat a duree determinee",
        "contrat a duree indeterminee",
    ),
    "CONTRACT_CDI_SIX_YEARS": (
        "6 ans", "six ans", "six annees", "l332 8", "l332 9", "l332 10",
        "l332 11", "l332 12", "l332 23", "l452 44",
        "interruption entre deux contrats", "meme categorie hierarchique",
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


def is_topic_relevant_source(
    question: str, source: dict[str, Any], target_versant: str = "FPT",
) -> bool:
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
    source_corpus = _fold(source_text[:500_000])
    title_folded = _fold(str(source.get("title") or ""))
    source_topics = _matched_topic_families(source_text[:500_000])
    source_article_ref = _fold(str(source.get("article") or source.get("article_id") or ""))
    if (
        title_folded.startswith("code general de la fonction publique")
        and source_article_ref in {f"l822 {number}" for number in range(1, 6)}
    ):
        source_topics.add("ORDINARY_SICK_LEAVE")
    if "loi n 2017 1837" in title_folded and "article 115" in source_corpus:
        source_topics.add("ORDINARY_SICK_LEAVE")
    source_article_number_raw = " ".join(
        str(source.get(key) or "") for key in ("article", "article_id", "article_number")
    )
    source_article_number_match = re.search(r"\b(14|15)\b", _fold(source_article_number_raw))
    source_article_number = source_article_number_match.group(1) if source_article_number_match else ""
    if (
        "decret n 87 602" in title_folded
        and (
            source_article_number in {"14", "15"}
            or "article 14" in source_corpus
            or "article 15" in source_corpus
        )
    ):
        source_topics.add("ORDINARY_SICK_LEAVE")
    if (
        "decret n 2025 197" in title_folded
        and any(marker in source_corpus for marker in (
            "conge de maladie", "maladie ordinaire", "90 %", "90 pour cent",
            "trois premiers mois", "trois premiers mois de conge",
        ))
    ):
        source_topics.add("ORDINARY_SICK_LEAVE")
    # Do not let the similar wording "extra hours" merge two distinct FPT
    # regimes: decree 2004-777 concerns part-time IHTS conditions, while
    # decree 2020-592 governs complementary hours for permanent non-complete
    # jobs. A source explicitly limited to the opposite status is not evidence
    # for the user's status unless it also addresses that status.
    if str(target_versant or "FPT").upper() == "FPT" and (
        "PART_TIME" in question_topics
        and "NON_COMPLETE_TIME" in source_topics
        and "PART_TIME" not in source_topics
    ):
        return False
    if str(target_versant or "FPT").upper() == "FPT" and (
        "NON_COMPLETE_TIME" in question_topics
        and "PART_TIME" in source_topics
        and "NON_COMPLETE_TIME" not in source_topics
    ):
        return False
    # The six-year CDI route is a specific legal mechanism. Apply this
    # guard before the generic CONTRACTUAL_STATUS intersection below: a
    # provision about contract agents (e.g. end-of-contract compensation or
    # retirement) is not evidence of the six-year conversion mechanism.
    if "CONTRACT_CDI_SIX_YEARS" in question_topics and (
        "CONTRACT_CDI_SIX_YEARS" not in source_topics
    ):
        return False

    # A specific bereavement/kinship-proof question must not be satisfied by
    # an unrelated leave provision merely because both mention absence.
    if (
        "FAMILY_BEREAVEMENT" in question_topics
        and "FAMILY_BEREAVEMENT" not in source_topics
    ):
        return False
    # Generic union-rights material is not proof of a right to assistance at
    # a particular kind of meeting. Keep disciplinary procedure material as
    # a related lead, but reject unrelated union administration provisions.
    if (
        "UNION_ASSISTANCE" in question_topics
        and not ({"UNION_ASSISTANCE", "DISCIPLINE"} & source_topics)
    ):
        return False
    # Never cross-match ordinary sick leave with CITIS. Both mechanisms
    # contain the words "congé" and "maladie", but their conditions and
    # remuneration rules are different. A CITIS source remains available
    # only when the question actually concerns service-related incapacity.
    if (
        "CITIS" in source_topics
        and "CITIS" not in question_topics
        and ("SICK_LEAVE" in question_topics or "ORDINARY_SICK_LEAVE" in question_topics)
    ):
        return False

    if "ORDINARY_SICK_LEAVE" in question_topics:
        cmo_pay_evidence = (
            source_article_ref in {f"l822 {number}" for number in range(1, 6)}
            or ("loi n 2017 1837" in title_folded and "article 115" in source_corpus)
            or ("decret n 87 602" in title_folded and source_article_number in {"14", "15"})
            or "decret n 2025 197" in title_folded
        )
        if "ORDINARY_SICK_LEAVE" not in source_topics and not (
            "REMUNERATION" in source_topics and cmo_pay_evidence
        ):
            return False

    if "REPORT_HIERARCHICAL_CONTESTATION" in question_topics and not (
        {"REPORT_HIERARCHICAL_CONTESTATION", "INDIVIDUAL_FILE", "DISCIPLINE", "PROFESSIONAL_EVALUATION"}
        & source_topics
    ):
        return False

    if question_topics & source_topics:
        return True

    # Strict question families reject generic keyword hits that cannot be
    # tied to the requested legal mechanism. Annual-appraisal questions retain
    # unclassified cross-cutting procedural sources as a narrow exception.

    strict_topics = {
        "TERMINATION_OF_TITULAR",
        "STAFFING_AND_WORK_CONDITIONS",
        # Evaluation searches are especially prone to lexical false positives:
        # generic references to evaluating risks, health, senior civil-service
        # jobs or skills are not evidence about the annual FPT appraisal report.
        "PROFESSIONAL_EVALUATION",
        "REPORT_HIERARCHICAL_CONTESTATION",
        "CONTRACT_CDI_SIX_YEARS",
        "AVAILABILITY",
        "CONTRACTUAL_STATUS",
        "FAMILY_BEREAVEMENT",
        "UNION_ASSISTANCE",
        "AGGRESSION_AGENT_PROTECTION",
    }
    if str(target_versant or "FPT").upper() == "FPT" and question_topics & strict_topics:
        # Preserve only explicit, narrowly related source families for the
        # two compound topics; generic hits remain excluded.
        related_strict_source = (
            (
                "AGGRESSION_AGENT_PROTECTION" in question_topics
                and bool({
                    "FUNCTIONAL_PROTECTION", "SICK_LEAVE",
                    "STAFFING_AND_WORK_CONDITIONS",
                } & source_topics)
            )
            or (
                "REPORT_HIERARCHICAL_CONTESTATION" in question_topics
                and bool({"INDIVIDUAL_FILE", "DISCIPLINE", "PROFESSIONAL_EVALUATION"} & source_topics)
            )
            or (
                "UNION_ASSISTANCE" in question_topics
                and "DISCIPLINE" in source_topics
            )
        )
        # For annual-appraisal questions only, an unclassified procedural
        # source may still be relevant. The CDI six-year mechanism remains
        # strict: generic or unrelated CGFP provisions are rejected.
        if not related_strict_source and (
            "PROFESSIONAL_EVALUATION" not in question_topics or source_topics
        ):
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
        "AGGRESSION_AGENT_PROTECTION": {
            "FUNCTIONAL_PROTECTION", "SICK_LEAVE", "STAFFING_AND_WORK_CONDITIONS",
        },
        "UNION_ASSISTANCE": {"DISCIPLINE"},
        "REPORT_HIERARCHICAL_CONTESTATION": {
            "INDIVIDUAL_FILE", "DISCIPLINE", "PROFESSIONAL_EVALUATION",
        },
    }
    return any(
        source_family in related_families.get(question_family, set())
        for question_family in question_topics
        for source_family in source_topics
    )
