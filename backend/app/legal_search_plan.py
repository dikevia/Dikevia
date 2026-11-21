"""Deterministic, narrow query expansions for French territorial public-service law."""

from __future__ import annotations

import re
import unicodedata


_ARTICLE_REFERENCE = re.compile(r"\b(?:article\s+)?[LRD]\.?\s*\d+(?:-\d+)*\b", re.IGNORECASE)
_DIRECT_ARTICLE_LOOKUP = re.compile(
    r"\b(?:que\s+(?:prevoit|dit|dispose)\s+(?:l(?:['’]\s*|\s+))?article"
    r"|(?:texte|contenu|teneur)\s+(?:integral\s+)?(?:de\s+)?(?:l(?:['’]\s*|\s+))?article"
    r"|(?:donne|fournis|reproduis)\s+(?:moi\s+)?(?:le\s+)?texte\s+(?:de\s+)?(?:l(?:['’]\s*|\s+))?article)\b",
    re.IGNORECASE,
)

# The most specific topic wins. Expansions are deliberately tied to French
# territorial public-service source families and their implementing texts.
_TOPIC_EXPANSIONS = (
    (
        ("peut me virer", "me virer", "me mettre dehors", "mettre dehors", "me licencier",
         "peut me licencier", "mettre fin a mes fonctions", "fin de mes fonctions",
         "licenciement fonctionnaire", "radiation des cadres",
         "perte de la qualite de fonctionnaire", "titulaire peut elle", "titulaire peut il"),
        "fonctionnaire territorial titulaire cessation definitive de fonctions radiation des cadres "
        "licenciement fonctionnaire titulaire CGFP motifs procedure insuffisance professionnelle "
        "suppression emploi abandon de poste revocation jurisprudence administrative",
    ),
    (
        ("manque de personnel", "manque d effectifs", "pas assez d agents",
         "pas suffisamment d agents", "on manque d agents", "on est pas assez nombreux",
         "on n est pas assez nombreux", "sous effectif", "effectif reduit",
         "effectifs insuffisants", "mon service est en sous effectif",
         "surcharge de travail", "ne renforce pas les equipes", "ne recrute pas",
         "charge de travail", "conditions de travail", "risques psychosociaux",
         "risques professionnels", "sante et securite au travail"),
        "fonction publique territoriale obligation employeur prevention sante securite au travail "
        "decret 85-603 document unique evaluation risques professionnels effectifs insuffisants "
        "charge de travail risques psychosociaux comite social territorial formation specialisee",
    ),
    (
        ("droit syndical", "droits syndicaux", "syndicat", "representant du personnel",
         "representants du personnel", "representant syndical", "representants syndicaux", "local syndical", "locaux syndicaux", "decharge d activite", "decharges d activite", "decharge syndicale",
         "credit de temps syndical", "credit d heures syndical", "asa syndicale",
         "autorisation speciale d absence syndicale",
         "formation syndicale", "reunion d information syndicale"),
        "droit syndical fonction publique territoriale CGFP livre II exercice du droit "
        "syndical dialogue social représentation des agents garanties exercice droit "
        "syndical facilités organisations syndicales locaux syndicaux autorisations "
        "spéciales absence décharges activité service crédit temps syndical formation "
        "syndicale réunions information syndicale partie réglementaire CGFP "
        "délibération protocole accord local",
    ),
    (
        ("heures supplementaires", "heure supplementaire", "heures sup", "ihts",
         "indemnites horaires pour travaux supplementaires", "travaux supplementaires"),
        "indemnités horaires pour travaux supplémentaires IHTS décret 2002-60 "
        "décret 91-875 décret 2001-623 fonction publique territoriale "
        "délibération assemblée délibérante repos compensateur",
    ),
    (
        ("harcelement moral",),
        "harcèlement moral agents territoriaux CGFP protection fonctionnelle "
        "décret procédure fonction publique territoriale jurisprudence administrative",
    ),
    (
        ("harcelement sexuel", "agissement sexiste", "propos sexistes"),
        "harcèlement sexuel agissement sexiste agents publics territoriaux CGFP "
        "protection fonctionnelle jurisprudence administrative",
    ),
    (
        ("protection fonctionnelle", "un usager m a menace", "un usager m a menacé",
         "menace pendant mon service", "agression pendant le service"),
        "protection fonctionnelle agent territorial CGFP obligations employeur public "
        "jurisprudence Conseil d'État collectivités territoriales",
    ),
    (
        ("sanction disciplinaire", "procedure disciplinaire", "conseil de discipline",
         "avertissement", "blame", "exclusion temporaire", "revocation"),
        "discipline fonction publique territoriale CGFP décret 89-677 "
        "droits défense conseil de discipline jurisprudence administrative",
    ),
    (
        ("renouvellement de contrat", "non renouvellement", "fin de contrat",
         "licenciement contractuel", "recrutement contractuel", "terme du contrat",
         "agent contractuel", "contractuel", "contractuels", "CDD", "CDI"),
        "agents contractuels territoriaux décret 88-145 CGFP recrutement renouvellement "
        "licenciement garanties procédure jurisprudence administrative",
    ),
    (
        ("temps de travail", "duree du travail", "annualisation", "astreinte",
         "temps partiel", "cycle de travail", "rtt"),
        "temps de travail fonction publique territoriale décret 2001-623 "
        "décret 2000-815 cycle de travail annualisation astreintes repos",
    ),
    (
        ("accident de service", "maladie professionnelle", "citis"),
        "congé pour invalidité temporaire imputable au service CITIS agents territoriaux "
        "accident de service maladie professionnelle CGFP décret 87-602",
    ),
    (
        ("ifse", "rifseep", "nbi", "regime indemnitaire",
         "remuneration", "traitement indiciaire"),
        "rémunération fonctionnaires territoriaux régime indemnitaire RIFSEEP IFSE NBI "
        "délibération locale décret 91-875 CGFP",
    ),
    (
        ("conges annuels", "congé annuel", "report de conges", "report de congés",
         "conges non pris", "congés non pris", "compte epargne temps",
         "compte épargne-temps", "conge sans solde", "congé sans solde",
         "conge maternite", "congé maternité"),
        "congés annuels fonction publique territoriale décret 85-1250 "
        "compte épargne temps décret 2004-878 report congés délibération locale",
    ),
    (
        ("conge maladie ordinaire", "congé de maladie ordinaire", "arret maladie",
         "arrêt maladie", "conge longue maladie", "congé longue maladie",
         "conge longue duree", "congé longue durée", "temps partiel therapeutique",
         "temps partiel thérapeutique", "maintien de traitement", "maintien de rémunération", "conseil medical", "conseil médical",
         "secret medical", "secret médical"),
        "congé maladie fonction publique territoriale CGFP fonctionnaire contractuel "
        "décret 87-602 décret 88-145 conseil médical temps partiel thérapeutique secret médical",
    ),
    (
        ("avancement d echelon", "avancement d'échelon", "avancement de grade",
         "promotion interne", "entretien professionnel", "compte rendu d entretien",
         "compte rendu d'entretien", "refus de titularisation", "titularisation",
         "reprise anciennete", "reprise d ancienneté", "anciennete dans le prive",
         "ancienneté dans le privé"),
        "CGFP livre V carrière fonction publique territoriale avancement échelon grade "
        "promotion interne entretien professionnel titularisation stage reprise ancienneté",
    ),
    (
        ("comite social territorial", "comité social territorial", "CST",
         "formation specialisee", "formation spécialisée"),
        "CGFP dialogue social comité social territorial décret 2021-571 "
        "formation spécialisée compétences consultation collectivités territoriales",
    ),
    (
        ("teletravail", "télétravail", "travail a distance", "travail à distance",
         "materiel de teletravail", "matériel de télétravail", "accident en teletravail", "accident pendant le teletravail", "accident a domicile pendant le teletravail"),
        "fonction publique territoriale télétravail décret 2016-151 décret 2020-524 "
        "autorisation individuelle délibération locale équipement",
    ),
    (
        ("droit de retrait", "danger grave et imminent", "registre danger grave",
         "document unique", "duerp", "medecine du travail", "médecine du travail",
         "preconisation medicale", "préconisation médicale", "adapter mon poste"),
        "fonction publique territoriale santé sécurité travail décret 85-603 "
        "droit de retrait danger grave imminent document unique médecin du travail",
    ),
    (
        ("mutation dans l interet du service", "mutation dans l'intérêt du service",
         "changement d affectation", "changement d'affectation",
         "disponibilite pour suivre", "disponibilité pour suivre",
         "suivre mon conjoint", "concours dans une autre collectivite",
         "concours dans une autre collectivité"),
        "CGFP mobilité fonctionnaires territoriaux mutation changement affectation "
        "disponibilité suivi conjoint concours détachement garanties",
    ),
    (
        ("suppression de poste", "poste supprime", "poste supprimé", "demission",
         "démission", "rupture conventionnelle", "revenir dans la fonction publique",
         "revenir dans la fonction publique"),
        "CGFP fin de fonctions fonction publique territoriale suppression emploi "
        "reclassement démission rupture conventionnelle réintégration",
    ),
    (
        ("cumul d activites", "cumul d'activités", "activite independante",
         "activité indépendante", "cumuler deux emplois", "deux emplois publics",
         "activite accessoire", "activité accessoire", "temps non complet"),
        "CGFP cumul activités fonctionnaires territoriaux décret 2020-69 "
        "activité accessoire création entreprise autorisation déclaration",
    ),
    (
        ("silence de l administration", "silence de l'administration",
         "ne repond pas a ma demande", "ne répond pas à ma demande",
         "decision implicite", "décision implicite", "refus implicite",
         "absence de reponse", "absence de réponse"),
        "code des relations entre le public et l administration CRPA silence "
        "décision implicite délai recours agent public territorial",
    ),
)

def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", ascii_text)).strip()


def build_official_search_query(question: str, max_length: int = 500) -> str:
    """Keep the user's wording first, then append one narrowly matched FPT expansion."""
    original = str(question or "").strip()
    if not original:
        return original
    # Exact legal-reference requests must remain exact; extra terms can turn
    # a direct lookup into an unrelated full-text search.
    folded = _fold(original)
    current_turn = original.splitlines()[0]
    current_turn_folded = _fold(current_turn)
    if _ARTICLE_REFERENCE.search(current_turn) and _DIRECT_ARTICLE_LOOKUP.search(current_turn_folded):
        return original[:max_length]

    expansion = next(
        (
            terms for triggers, terms in _TOPIC_EXPANSIONS
            if any(_fold(trigger) in folded for trigger in triggers)
        ),
        "",
    )
    if not expansion:
        # Dikévia is an FPT-only product: even an unfamiliar everyday question
        # must be searched in the territorial legal framework, not as a generic
        # employment query that can drift toward private-sector or FPE results.
        expansion = (
            "agent territorial fonction publique territoriale collectivité territoriale "
            "autorité territoriale CGFP"
        )

    # Preserve the user's wording first; append only the FPT legal context
    # within the official connector's 500-character query contract.
    prefix = original[: min(len(original), 250)]
    remaining = max(0, max_length - len(prefix) - 1)
    return (prefix + " " + expansion[:remaining]).strip()

# Independent, bounded research axes. These are separate retrieval queries,
# not claims about the applicable law. Keep the number small to control latency
# and provider load while avoiding a single overloaded keyword string.
_TOPIC_RESEARCH_AXES = (
    (
        ("droit syndical", "droits syndicaux", "syndicat", "representant du personnel",
         "representants du personnel", "representant syndical", "representants syndicaux",
         "local syndical", "locaux syndicaux", "decharge d activite", "decharges d activite",
         "decharge syndicale", "credit de temps syndical", "credit d heures syndical",
         "asa syndicale", "autorisation speciale d absence syndicale",
         "formation syndicale", "reunion d information syndicale"),
        (
            "CGFP livre II droit syndical fonction publique territoriale exercice droits syndicaux agents territoriaux",
            "CGFP autorisations speciales absence syndicale decharges activite service credit temps syndical locaux syndicaux deliberation locale reunions information formation syndicale dialogue social organisations syndicales",
        ),
    ),
    (
        ("heures supplementaires", "heure supplementaire", "heures sup", "ihts",
         "indemnites horaires pour travaux supplementaires", "travaux supplementaires"),
        (
            "IHTS fonction publique territoriale décret 2002-60 décret 91-875 indemnités horaires travaux supplémentaires",
            "FPT décret 2001-623 temps de travail cycle décompte heures supplémentaires délibération assemblée délibérante repos compensateur",
        ),
    ),
    (
        ("renouvellement de contrat", "non renouvellement", "fin de contrat",
         "licenciement contractuel", "recrutement contractuel", "terme du contrat",
         "agent contractuel", "contractuel", "CDD", "CDI"),
        (
            "agents contractuels fonction publique territoriale CGFP décret 88-145 recrutement renouvellement contrat",
            "décret 88-145 agents contractuels territoriaux procédure non renouvellement licenciement garanties délai prévenance",
        ),
    ),
    (
        ("temps de travail", "duree du travail", "annualisation", "astreinte",
         "temps partiel", "cycle de travail", "rtt"),
        (
            "fonction publique territoriale décret 2001-623 durée annuelle temps de travail cycles délibération locale",
            "décret 2001-623 décret 2000-815 FPT repos quotidien hebdomadaire astreintes annualisation",
        ),
    ),

    (
        ("peut me virer", "me virer", "me mettre dehors", "mettre dehors", "me licencier",
         "peut me licencier", "mettre fin a mes fonctions", "fin de mes fonctions",
         "licenciement fonctionnaire", "radiation des cadres",
         "perte de la qualite de fonctionnaire", "titulaire peut elle", "titulaire peut il"),
        (
            "fonctionnaire territorial titulaire radiation des cadres licenciement garanties motifs procedure CGFP",
            "CGFP cessation definitive de fonctions insuffisance professionnelle suppression emploi abandon de poste revocation jurisprudence administrative",
        ),
    ),
    (
        ("manque de personnel", "manque d effectifs", "pas assez d agents",
         "pas suffisamment d agents", "on manque d agents", "on est pas assez nombreux",
         "on n est pas assez nombreux", "sous effectif", "effectif reduit",
         "effectifs insuffisants", "mon service est en sous effectif",
         "surcharge de travail", "ne renforce pas les equipes", "ne recrute pas",
         "charge de travail", "conditions de travail", "risques psychosociaux",
         "risques professionnels", "sante et securite au travail"),
        (
            "fonction publique territoriale obligation employeur sante securite prevention risques professionnels decret 85-603",
            "FPT sous effectif charge de travail risques psychosociaux document unique CST formation specialisee conditions de travail",
        ),
    ),
    (
        ("harcelement moral", "harcèlement moral"),
        (
            "harcèlement moral agent public territorial CGFP protection fonctionnelle obligations employeur prévention",
            "jurisprudence administrative harcèlement moral fonction publique territoriale charge preuve protection agent",
        ),
    ),
    (
        ("harcelement sexuel", "harcèlement sexuel", "agissement sexiste", "propos sexistes"),
        (
            "harcèlement sexuel agissement sexiste agent territorial CGFP protection fonctionnelle",
            "jurisprudence administrative harcèlement sexuel agissements sexistes fonction publique territoriale",
        ),
    ),
    (
        ("protection fonctionnelle", "proteger par la collectivite", "menaces contre un agent", "menacé au travail", "un usager m a menace", "menace pendant mon service", "agression pendant le service"),
        (
            "protection fonctionnelle agent territorial CGFP obligation collectivité territoriale",
            "jurisprudence Conseil d'État protection fonctionnelle agents publics territoriaux conditions refus",
        ),
    ),
    (
        ("sanction disciplinaire", "procedure disciplinaire", "conseil de discipline", "avertissement", "blame", "exclusion temporaire", "revocation"),
        (
            "discipline fonction publique territoriale CGFP garanties disciplinaires droits défense conseil de discipline",
            "décret 89-677 fonction publique territoriale procédure disciplinaire jurisprudence administrative",
        ),
    ),
    (
        ("accident de service", "maladie professionnelle", "citis"),
        (
            "CITIS agent territorial accident de service maladie professionnelle CGFP décret 87-602",
            "fonction publique territoriale congé maladie imputabilité au service expertise médicale droits agent",
        ),
    ),
    (
        ("ifse", "rifseep", "nbi", "regime indemnitaire", "régime indemnitaire", "remuneration", "rémunération", "traitement indiciaire"),
        (
            "rémunération agents territoriaux CGFP régime indemnitaire RIFSEEP IFSE NBI délibération locale",
            "fonction publique territoriale décret 91-875 régime indemnitaire équivalence corps délibération assemblée",
        ),
    ),
    (
        ("conges annuels", "congé annuel", "report de conges", "report de congés",
         "conges non pris", "congés non pris", "compte epargne temps",
         "compte épargne-temps", "conge sans solde", "congé sans solde",
         "conge maternite", "congé maternité"),
        (
            "fonction publique territoriale congés annuels décret 85-1250 droits report congés",
            "FPT compte épargne temps décret 2004-878 congés non pris délibération locale",
        ),
    ),
    (
        ("conge maladie ordinaire", "congé de maladie ordinaire", "arret maladie",
         "arrêt maladie", "conge longue maladie", "congé longue maladie",
         "conge longue duree", "congé longue durée", "temps partiel therapeutique",
         "temps partiel thérapeutique", "conseil medical", "conseil médical",
         "secret medical", "secret médical"),
        (
            "CGFP congé maladie ordinaire fonctionnaire territorial droits rémunération",
            "décret 87-602 décret 88-145 FPT conseil médical temps partiel thérapeutique secret médical",
        ),
    ),
    (
        ("avancement d echelon", "avancement d'échelon", "avancement de grade",
         "promotion interne", "entretien professionnel", "compte rendu d entretien",
         "compte rendu d'entretien", "refus de titularisation", "titularisation",
         "reprise anciennete", "reprise d ancienneté", "anciennete dans le prive",
         "ancienneté dans le privé"),
        (
            "CGFP livre V fonctionnaires territoriaux avancement échelon grade promotion interne",
            "FPT entretien professionnel titularisation stage reprise ancienneté décret statutaire",
        ),
    ),
    (
        ("comite social territorial", "comité social territorial", "CST",
         "formation specialisee", "formation spécialisée"),
        (
            "CGFP comité social territorial compétences consultation collectivités territoriales",
            "décret 2021-571 CST formation spécialisée ordre du jour avis règlement intérieur",
        ),
    ),
    (
        ("teletravail", "télétravail", "travail a distance", "travail à distance",
         "materiel de teletravail", "matériel de télétravail"),
        (
            "fonction publique territoriale télétravail décret 2016-151 décret 2020-524",
            "FPT télétravail autorisation individuelle délibération locale équipement accident service",
        ),
    ),
    (
        ("droit de retrait", "danger grave et imminent", "registre danger grave",
         "document unique", "duerp", "medecine du travail", "médecine du travail",
         "preconisation medicale", "préconisation médicale", "adapter mon poste"),
        (
            "FPT santé sécurité travail décret 85-603 droit de retrait danger grave imminent",
            "fonction publique territoriale document unique médecin du travail prévention risques professionnels",
        ),
    ),
    (
        ("mutation dans l interet du service", "mutation dans l'intérêt du service",
         "changement d affectation", "changement d'affectation",
         "disponibilite pour suivre", "disponibilité pour suivre",
         "suivre mon conjoint", "concours dans une autre collectivite",
         "concours dans une autre collectivité"),
        (
            "CGFP mobilité fonctionnaires territoriaux mutation changement affectation disponibilité",
            "FPT suivi conjoint concours détachement nomination stage garanties statutaires",
        ),
    ),
    (
        ("suppression de poste", "poste supprime", "poste supprimé", "demission",
         "démission", "rupture conventionnelle", "revenir dans la fonction publique",
         "refus de titularisation"),
        (
            "CGFP fin de fonctions territoriales suppression emploi reclassement démission",
            "fonction publique territoriale rupture conventionnelle réintégration garanties procédure",
        ),
    ),
    (
        ("cumul d activites", "cumul d'activités", "activite independante",
         "activité indépendante", "cumuler deux emplois", "deux emplois publics",
         "activite accessoire", "activité accessoire"),
        (
            "CGFP cumul activités agents territoriaux décret 2020-69 autorisation déclaration",
            "FPT activité accessoire création entreprise cumul emplois publics exceptions",
        ),
    ),
    (
        ("silence de l administration", "silence de l'administration",
         "ne repond pas a ma demande", "ne répond pas à ma demande",
         "decision implicite", "décision implicite", "refus implicite",
         "absence de reponse", "absence de réponse"),
        (
            "CRPA silence administration décision implicite délai recours agent territorial",
            "code relations public administration refus implicite voies délais recours",
        ),
    ),
)

def build_official_search_queries(question: str, max_queries: int = 3) -> list[str]:
    """Build a small set of distinct, topic-focused legal retrieval queries.

    The original expanded query remains first for backward-compatible recall.
    Additional axes are only emitted for explicitly recognized topics.
    """
    primary = build_official_search_query(question)
    if not primary:
        return []
    queries = [primary]
    original = str(question or "").strip()
    current_turn = original.splitlines()[0] if original else ""
    if _ARTICLE_REFERENCE.search(current_turn) and _DIRECT_ARTICLE_LOOKUP.search(_fold(current_turn)):
        return queries
    folded = _fold(original)
    query_limit = max(1, min(max_queries, 3))
    matched_axes = []
    other_topic_present = any(
        any(_fold(trigger) in folded for trigger in triggers)
        for index, (triggers, _axes) in enumerate(_TOPIC_RESEARCH_AXES)
        if index != 2
    )
    contract_triggers, contract_axes = _TOPIC_RESEARCH_AXES[2]
    contract_subject_present = any(
        _fold(trigger) in folded for trigger in contract_triggers[:6]
    )
    for index, (triggers, axes) in enumerate(_TOPIC_RESEARCH_AXES):
        if not any(_fold(trigger) in folded for trigger in triggers):
            continue
        # "Je suis contractuel" identifies status, not the legal topic. Do not
        # let it displace a substantive topic such as IHTS or union rights.
        if index == 2 and other_topic_present and not contract_subject_present:
            continue
        matched_axes.append(axes)

    # "Et pour les contractuels ?" is a status comparison, not necessarily a
    # contract-law issue. Use the contract axis only when no substantive topic
    # is already present in the contextual question.
    if not matched_axes and re.search(r"\b(?:et\s+)?pour\s+les?\s+contractuels?\b", folded):
        matched_axes = [contract_axes]

    # Unclassified everyday questions still receive independent FPT retrieval
    # axes: one for the applicable statutory framework and one for territorial
    # administrative case law. This improves recall without treating search
    # terms as legal conclusions.
    if not matched_axes:
        topic = original.splitlines()[0][:180]
        matched_axes = [(
            f"fonction publique territoriale agent territorial CGFP autorité territoriale {topic}",
            f"jurisprudence administrative agent territorial collectivité territoriale {topic}",
        )]

    # For compound questions, first allocate one focused query to each
    # recognized topic. Only then spend remaining capacity on a second axis
    # for the first topic. This avoids silently dropping a second legal issue.
    for axes in matched_axes:
        if len(queries) >= query_limit:
            break
        candidate = axes[0][:500]
        if candidate not in queries:
            queries.append(candidate)

    for axes in matched_axes:
        for axis in axes[1:]:
            if len(queries) >= query_limit:
                break
            candidate = axis[:500]
            if candidate not in queries:
                queries.append(candidate)
        if len(queries) >= query_limit:
            break
    return queries[:query_limit]
