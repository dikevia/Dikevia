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
        ("accompagne d un syndicat", "accompagne par un syndicat",
         "accompagne d un representant syndical", "accompagne par un representant syndical",
         "assiste par un representant syndical", "venir avec mon syndicat",
         "venir avec un syndicat", "assistance syndicale lors d une convocation",
         "accompagnement syndical lors d une convocation"),
        "agent territorial convocation hierarchie entretien accompagnement assistance representant syndical "
        "procedure disciplinaire garanties droits de la defense defenseur de son choix CGFP "
        "distinguer entretien hierarchique ordinaire et procedure disciplinaire",
    ),
    (
        ("evaluation annuelle", "évaluation annuelle", "evaluation a charge", "évaluation à charge",
         "contester mon evaluation", "contester mon évaluation", "contestation evaluation",
         "contestation de l evaluation", "compte rendu d evaluation", "compte rendu d'évaluation",
         "evaluation professionnelle", "évaluation professionnelle"),
        "CGFP articles L521-1 L521-3 L521-5 appréciation valeur professionnelle fonctionnaire territorial "
        "entretien professionnel annuel compte rendu contestation révision décret 2014-1526 articles 2 3 4 5 6 7 "
        "superieur hierarchique direct autorite territoriale commission administrative paritaire",
    ),
    (
        ("disponibilite pour convenances personnelles",
         "disponibilité pour convenances personnelles",
         "mise en disponibilite pour convenances personnelles",
         "mise en disponibilité pour convenances personnelles",
         "convenances personnelles"),
        "décret 86-68 du 13 janvier 1986 article 21 disponibilité pour convenances personnelles "
        "fonctionnaire territorial titulaire durée maximale cinq ans renouvellement dix ans "
        "nécessités du service demande de l'intéressé",
    ),
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
         "formation syndicale", "reunion d information syndicale", "reunion syndicale",
         "tract syndical", "mandat syndical", "appartenance syndicale",
         "communication syndicale", "messagerie professionnelle syndicale",
         "fournir un local au syndicat"),
        "droit syndical fonction publique territoriale CGFP livre II exercice du droit "
        "syndical dialogue social représentation des agents garanties exercice droit "
        "syndical facilités organisations syndicales locaux syndicaux autorisations "
        "spéciales absence décharges activité service crédit temps syndical formation "
        "syndicale réunions information syndicale partie réglementaire CGFP "
        "délibération protocole accord local",
    ),
    (
        ("deces d un grand pere", "deces d une grand mere",
         "deces de son grand pere", "deces de sa grand mere",
         "deces de mon grand pere", "deces de ma grand mere",
         "deces d un proche", "deces d un membre de la famille",
         "deces d un ascendant", "grand pere decede", "grand mere decedee",
         "grand parent decede", "obseques", "autorisation d absence pour deces",
         "acte de deces", "justificatif de deces"),
        (
            "fonction publique territoriale autorisation speciale absence deces grand parent ascendant CGFP textes reglementaires deliberation locale",
            "agent territorial justificatif deces lien de parente livret de famille acte de deces protection des donnees minimisation donnees personnelles",
        ),
    ),
    (
        ("heures supplementaires", "heure supplementaire", "heures sup", "ihts",
         "indemnites horaires pour travaux supplementaires", "travaux supplementaires",
         "rester apres mon horaire", "heures effectuees au dela de mon horaire"),
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
         "menace pendant mon service", "agression pendant le service",
         "agression au travail", "poursuivi penalement", "poursuites penales",
         "agent victime de harcelement", "signalement de harcelement"),
        "protection fonctionnelle agent territorial CGFP obligations employeur public "
        "jurisprudence Conseil d'État collectivités territoriales",
    ),
    (
        ("sanction disciplinaire", "procedure disciplinaire", "conseil de discipline",
         "avertissement", "blame", "exclusion temporaire", "revocation",
         "entretien disciplinaire", "suspension de fonctions", "suspension conservatoire",
         "ordre manifestement illegal", "sanction sans avoir ete entendu",
         "effacement sanction dossier", "conservation sanction dossier",
         "faits commis hors service", "temoignages contre moi"),
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
        ("temps partiel pour raison therapeutique", "temps partiel therapeutique",
         "mi temps therapeutique", "mi-temps therapeutique", "tpt"),
        "CGFP articles L823-1 a L823-6 temps partiel pour raison therapeutique maintien retour emploi "
        "rééducation réadaptation mi-temps intégralité traitement supplément familial indemnité résidence "
        "décret 87-602 articles 13-1 13-2 13-3 13-5 13-7 13-9 13-11 13-13 CITIS reprise après congé imputable au service",
    ),
    (
        ("temps de travail", "duree du travail", "annualisation", "astreinte",
         "temps partiel", "temps non complet", "cycle de travail", "rtt",
         "compteur d heures", "compteur d heures remis a zero",
         "heures effectuees au dela de mon horaire"),
        "temps de travail fonction publique territoriale décret 2001-623 "
        "décret 2000-815 cycle de travail annualisation astreintes repos décompte heures "
        "temps partiel temps non complet heures complémentaires heures supplémentaires "
        "compteur temps de travail délibération locale",
    ),
    (
        ("accident de service", "accident sur mon lieu de travail", "imputable au service", "imputabilité au service", "maladie professionnelle", "citis"),
        "congé pour invalidité temporaire imputable au service CITIS agents territoriaux "
        "accident de service maladie professionnelle CGFP décret 87-602",
    ),
    (
        ("ifse", "rifseep", "nbi", "regime indemnitaire",
         "remuneration", "traitement indiciaire", "baisse de primes",
         "suppression de primes"),
        "rémunération fonctionnaires territoriaux régime indemnitaire RIFSEEP IFSE NBI "
        "délibération locale décret 91-875 CGFP",
    ),
    (
        ("conges annuels", "congé annuel", "report de conges", "report de congés",
         "conges non pris", "congés non pris", "dates de conges", "dates de congés",
         "jour ferie pendant mes conges", "jour férié pendant mes congés",
         "rappel pendant mes conges", "rappel pendant mes congés", "compte epargne temps",
         "compte épargne-temps", "conge sans solde", "congé sans solde",
         "conge maternite", "congé maternité", "solde de conges", "solde de congés",
         "regles de conges", "règles de congés"),
        "congés annuels fonction publique territoriale décret 85-1250 "
        "compte épargne temps décret 2004-878 report congés délibération locale",
    ),
    (
        ("conge maladie ordinaire", "congé de maladie ordinaire", "arret maladie",
         "arrêt maladie", "conge longue maladie", "congé longue maladie",
         "conge longue duree", "congé longue durée", "temps partiel therapeutique",
         "temps partiel thérapeutique", "maintien de traitement", "maintien de rémunération", "conseil medical", "conseil médical",
         "secret medical", "secret médical", "motif medical", "motif médical"),
        "congé maladie fonction publique territoriale CGFP fonctionnaire contractuel "
        "décret 87-602 décret 88-145 conseil médical temps partiel thérapeutique secret médical",
    ),
    (
        ("evaluation annuelle", "évaluation annuelle", "evaluation a charge", "évaluation à charge",
         "contester mon evaluation", "contester mon évaluation", "contestation evaluation",
         "compte rendu d evaluation", "compte rendu d'évaluation", "evaluation professionnelle",
         "entretien professionnel", "compte rendu d entretien"),
        (
            "CGFP L521-1 L521-3 L521-5 fonctionnaire territorial appréciation valeur professionnelle compte rendu demande révision CAP",
            "décret 2014-1526 articles 2 5 6 7 entretien professionnel territorial notification observations demande révision quinze jours francs CAP délai un mois",
            "décret 88-145 article 1-3 emploi permanent CDI CDD supérieur à un an contrat de projet agent contractuel territorial entretien professionnel compte rendu révision CCP quinze jours francs délai un mois jurisprudence administrative",
        ),
    ),
    (
        ("avancement d echelon", "avancement d'échelon", "avancement de grade",
         "promotion interne", "refus de titularisation", "titularisation",
         "fonctionnaire stagiaire", "agent stagiaire", "stagiaire",
         "reprise anciennete", "reprise d ancienneté", "anciennete dans le prive",
         "ancienneté dans le privé", "modifier mes missions", "changement de missions",
         "missions sans changer mon grade"),
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
         "preconisation medicale", "préconisation médicale", "adapter mon poste", "conditions de securite sont dangereuses",
         "conditions de sécurité sont dangereuses", "poste dangereux",
         "sanctionne apres avoir signale des risques",
         "sanctionne apres avoir signale un danger",
         "represailles apres signalement de risques",
         "represailles apres signalement d un danger", "risques psychosociaux"),
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
        ("suppression de poste", "poste supprime", "poste supprimé", "poste est supprime",
         "poste est supprimé", "emploi supprime", "emploi supprimé", "emploi est supprime",
         "emploi est supprimé", "demission",
         "démission", "rupture conventionnelle", "revenir dans la fonction publique",
         "revenir dans la fonction publique"),
        "CGFP fin de fonctions fonction publique territoriale suppression emploi "
        "reclassement démission rupture conventionnelle réintégration",
    ),
    (
        ("cumul d activites", "cumul d'activités", "activite independante",
         "activité indépendante", "cumuler deux emplois", "deux emplois publics",
         "activite accessoire", "activité accessoire"),
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


def _contains_trigger(text: str, trigger: str) -> bool:
    """Match a normalized trigger as complete words, never as an arbitrary substring."""
    normalized_text = f" {_fold(text)} "
    normalized_trigger = f" {_fold(trigger)} "
    return normalized_trigger in normalized_text



def _is_union_assistance_convocation_question(question: str) -> bool:
    """Recognize a request about bringing union assistance to a hierarchical summons."""
    folded = _fold(str(question or ""))
    assistance = (
        "accompagne d un syndicat",
        "accompagne par un syndicat",
        "accompagne d un representant syndical",
        "accompagne par un representant syndical",
        "assiste par un representant syndical",
        "venir avec mon syndicat",
        "venir avec un syndicat",
        "etre accompagne par un syndicat",
        "etre accompagne d un syndicat",
        "assistance syndicale lors d une convocation",
        "accompagnement syndical lors d une convocation",
        "accompagnement syndical", "assistance syndicale",
        "etre accompagne par un representant syndical",
        "etre assiste par un representant syndical",
    )
    has_assistance = any(_contains_trigger(folded, trigger) for trigger in assistance)
    has_summons = any(_contains_trigger(folded, trigger) for trigger in (
        "convocation", "convoque par ma hierarchie", "convoque par sa hierarchie",
        "convoque par mon chef", "convoque par son chef",
        "entretien avec ma hierarchie", "entretien hierarchique",
    ))
    return has_assistance and has_summons


def clarification_for_union_assistance_summons(question: str) -> str | None:
    """Ask for the type of summons before researching an ambiguous assistance question."""
    if not _is_union_assistance_convocation_question(question):
        return None
    folded = _fold(str(question or ""))
    procedure_is_specified = any(_contains_trigger(folded, marker) for marker in (
        "procedure disciplinaire", "entretien disciplinaire", "sanction disciplinaire",
        "simple entretien", "entretien ordinaire", "entretien non disciplinaire",
        "enquete administrative", "enquete interne", "entretien professionnel",
        "audition administrative", "entretien de recadrage",
    ))
    if procedure_is_specified:
        return None
    return (
        "Pour identifier les règles applicables, votre convocation concerne-t-elle "
        "un entretien hiérarchique ordinaire, une procédure disciplinaire, ou une autre "
        "procédure (par exemple une enquête administrative) ?"
    )

def _is_therapeutic_part_time_question(question: str) -> bool:
    folded = _fold(str(question or ""))
    return any(
        _contains_trigger(folded, trigger)
        for trigger in (
            "temps partiel pour raison therapeutique",
            "temps partiel therapeutique",
            "mi temps therapeutique",
            "mi-temps therapeutique",
            "tpt",
        )
    )


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

    if _is_contractual_evaluation_question(original):
        expansion = (
            "agent contractuel territorial entretien professionnel annuel décret 88-145 "
            "article 1-3 emploi permanent CDI CDD supérieur à un an contrat de projet "
            "compte rendu appréciation professionnelle observations demande de révision CCP"
        )
    elif _is_union_assistance_convocation_question(original):
        expansion = (
            "agent territorial convocation hiérarchie entretien accompagnement syndical "
            "assistance représentant syndical procédure disciplinaire droits de la défense "
            "défenseur de son choix entretien ordinaire"
        )
    else:
        expansion = next(
            (
                terms for triggers, terms in _TOPIC_EXPANSIONS
                if any(_contains_trigger(folded, trigger) for trigger in triggers)
            ),
            "",
        )
    if isinstance(expansion, tuple):
        # Some topics intentionally fan out into several complementary search
        # phrases. Keep the official connector contract as one bounded string.
        expansion = " ".join(str(part) for part in expansion if part)
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
        ("accompagne d un syndicat", "accompagne par un syndicat",
         "accompagne d un representant syndical", "accompagne par un representant syndical",
         "assiste par un representant syndical", "venir avec mon syndicat",
         "venir avec un syndicat", "assistance syndicale lors d une convocation",
         "accompagnement syndical lors d une convocation",
         "accompagnement syndical", "assistance syndicale",
         "etre accompagne par un representant syndical"),
        (
            "agent territorial convocation hierarchie entretien ordinaire accompagnement representant syndical assistance entretien conditions applicables",
            "fonction publique territoriale procedure disciplinaire droits de la defense droit etre assiste defenseur de son choix CGFP decret 89-677",
        ),
    ),
    (
        ("deces d un grand pere", "deces d une grand mere",
         "deces de son grand pere", "deces de sa grand mere",
         "deces de mon grand pere", "deces de ma grand mere",
         "deces d un proche", "deces d un membre de la famille",
         "deces d un ascendant", "grand pere decede", "grand mere decedee",
         "grand parent decede", "obseques", "autorisation d absence pour deces",
         "acte de deces", "justificatif de deces"),
        (
            "fonction publique territoriale autorisation speciale absence deces grand parent ascendant CGFP textes reglementaires deliberation locale",
            "agent territorial justificatif deces lien de parente livret de famille acte de deces protection des donnees minimisation donnees personnelles",
        ),
    ),
    (
        ("droit syndical", "droits syndicaux", "syndicat", "representant du personnel",
         "representants du personnel", "representant syndical", "representants syndicaux",
         "local syndical", "locaux syndicaux", "decharge d activite", "decharges d activite",
         "decharge syndicale", "credit de temps syndical", "credit d heures syndical",
         "asa syndicale", "autorisation speciale d absence syndicale",
         "formation syndicale", "reunion d information syndicale", "reunion syndicale",
         "tract syndical", "mandat syndical", "appartenance syndicale",
         "communication syndicale", "messagerie professionnelle syndicale",
         "fournir un local au syndicat"),
        (
            "CGFP livre II droit syndical fonction publique territoriale exercice droits syndicaux agents territoriaux",
            "CGFP autorisations speciales absence syndicale decharges activite service credit temps syndical locaux syndicaux deliberation locale reunions information formation syndicale dialogue social organisations syndicales",
        ),
    ),
    (
        ("convocation par ma hierarchie", "convocation par mon chef",
         "convocation par la hierarchie", "entretien avec ma hierarchie",
         "entretien hierarchique", "accompagne d un syndicat",
         "accompagne par un representant syndical",
         "accompagne par un representant du personnel"),
        (
            "agent public convocation entretien hiérarchique ordinaire accompagnement syndical présence représentant syndical conditions",
            "fonction publique territoriale procédure disciplinaire convocation audition droits de la défense assistance conseil représentant syndical décret 89-677",
        ),
    ),
    (
        ("agresse par un usager", "agressee par un usager",
         "agression par un usager", "agression d un usager",
         "agent victime d une agression", "violence d un usager",
         "menace d un usager", "usager m a frappe",
         "refuse que je fasse un rapport", "refuse de faire un rapport",
         "rapport d incident agent public"),
        (
            "agent public territorial victime agression usager protection fonctionnelle collectivité territoriale obligation de protection violences",
            "fonction publique territoriale santé sécurité travail signalement écrit incident agression usager rapport circonstancié déclaration accident service prévention employeur décret 85-603",
        ),
    ),
    (
        ("heures supplementaires", "heure supplementaire", "heures sup", "ihts",
         "indemnites horaires pour travaux supplementaires", "travaux supplementaires",
         "rester apres mon horaire",
         "heures effectuees au dela de mon horaire"),
        (
            "IHTS fonction publique territoriale décret 2002-60 décret 91-875 indemnités horaires travaux supplémentaires",
            "FPT décret 2001-623 temps de travail cycle décompte heures supplémentaires délibération assemblée délibérante repos compensateur",
        ),
    ),
    (
        ("temps partiel therapeutique", "temps partiel pour raison therapeutique",
         "mi temps therapeutique", "mi-temps therapeutique", "tpt"),
        (
            "CGFP L823-1 L823-2 L823-3 L823-4 L823-5 L823-6 fonctionnaire territorial temps partiel pour raison therapeutique conditions maintien retour emploi mi temps remuneration integrale traitement SFT indemnite residence decret 87-602",
            "decret 87-602 articles 13-1 13-2 13-3 13-5 13-7 13-9 13-11 13-13 decret 2026-705 CITIS reprise apres conge imputable au service autorisation temps partiel therapeutique",
        ),
    ),
    (
        ("temps partiel", "agent a temps partiel", "agent à temps partiel"),
        (
            "fonction publique territoriale temps partiel heures supplémentaires IHTS décret 2004-777 décret 2002-60",
            "FPT agent à temps partiel conditions indemnités horaires travaux supplémentaires décret 82-624 décret 2004-777",
        ),
    ),
    (
        ("temps non complet", "agent a temps non complet", "agent à temps non complet"),
        (
            "FPT emploi permanent temps non complet heures complémentaires décret 2020-592 seuil 35 heures",
            "fonction publique territoriale temps non complet heures supplémentaires IHTS décret 2002-60 décret 2001-623",
        ),
    ),
    (
        ("prescription quadriennale", "prescription de ma creance",
         "heures supplementaires realisees il y a deux ans",
         "reclamer des heures supplementaires il y a deux ans"),
        (
            "prescription quadriennale créance de rémunération agent public territorial loi 68-1250",
            "jurisprudence administrative prescription créances salariales heures supplémentaires fonction publique territoriale interruption suspension",
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
         "cycle de travail", "rtt", "compteur d heures",
         "compteur d heures remis a zero", "heures effectuees au dela de mon horaire",
         "heures supplementaires", "heure supplementaire", "heures sup", "ihts"),
        (
            "fonction publique territoriale décret 2001-623 durée annuelle temps de travail cycles délibération locale heures supplémentaires",
            "FPT décret 2001-623 décret 2000-815 organisation du temps de travail cycles seuils décompte heures supplémentaires",
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
        ("protection fonctionnelle", "proteger par la collectivite", "menaces contre un agent", "menacé au travail", "un usager m a menace", "menace pendant mon service", "agression pendant le service", "agression au travail", "agresse par un usager", "agressee par un usager", "agression par un usager", "agression d un usager", "violence d un usager", "refuse que je fasse un rapport", "refuse de faire un rapport", "poursuivi penalement", "poursuites penales", "agent victime de harcelement", "signalement de harcelement"),
        (
            "protection fonctionnelle agent territorial CGFP obligation collectivité territoriale",
            "jurisprudence Conseil d'État protection fonctionnelle agents publics territoriaux conditions refus",
        ),
    ),
    (
        ("sanction disciplinaire", "procedure disciplinaire", "conseil de discipline", "avertissement", "blame", "exclusion temporaire", "revocation",
         "entretien disciplinaire", "suspension de fonctions", "suspension conservatoire",
         "ordre manifestement illegal", "sanction sans avoir ete entendu",
         "effacement sanction dossier", "conservation sanction dossier",
         "faits commis hors service", "temoignages contre moi"),
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
        ("ifse", "rifseep", "nbi", "regime indemnitaire", "régime indemnitaire", "remuneration", "rémunération", "traitement indiciaire", "baisse de primes", "suppression de primes"),
        (
            "rémunération agents territoriaux CGFP régime indemnitaire RIFSEEP IFSE NBI délibération locale",
            "fonction publique territoriale décret 91-875 régime indemnitaire équivalence corps délibération assemblée",
        ),
    ),
    (
        ("conges annuels", "congé annuel", "report de conges", "report de congés",
         "conges non pris", "congés non pris", "compte epargne temps",
         "compte épargne-temps", "conge sans solde", "congé sans solde",
         "conge maternite", "congé maternité", "solde de conges", "solde de congés",
         "regles de conges", "règles de congés"),
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
         "secret medical", "secret médical", "motif medical", "motif médical"),
        (
            "CGFP congé maladie ordinaire fonctionnaire territorial droits rémunération",
            "décret 87-602 décret 88-145 FPT conseil médical temps partiel thérapeutique secret médical",
        ),
    ),
    (
        ("evaluation annuelle", "évaluation annuelle", "evaluation a charge", "évaluation à charge",
         "contester mon evaluation", "contester mon évaluation", "contestation evaluation",
         "compte rendu d evaluation", "compte rendu d'évaluation", "evaluation professionnelle",
         "entretien professionnel", "compte rendu d entretien"),
        (
            "CGFP L521-1 L521-3 L521-5 décret 2014-1526 articles 2 3 4 5 6 7 fonctionnaire territorial compte rendu observations révision CAP quinze jours francs délai un mois",
            "décret 88-145 article 1-3 agent contractuel territorial emploi permanent CDI CDD supérieur à un an contrat de projet compte rendu observations révision CCP quinze jours francs délai un mois",
            "jurisprudence administrative contestation compte rendu entretien professionnel annuel fonction publique territoriale erreur manifeste appréciation exactitude matérielle faits",
        ),
    ),
    (
        ("avancement d echelon", "avancement d'échelon", "avancement de grade",
         "promotion interne", "refus de titularisation", "titularisation",
         "fonctionnaire stagiaire", "agent stagiaire", "stagiaire",
         "reprise anciennete", "reprise d ancienneté", "anciennete dans le prive",
         "ancienneté dans le privé", "modifier mes missions", "changement de missions",
         "missions sans changer mon grade"),
        (
            "CGFP livre V fonctionnaires territoriaux avancement échelon grade promotion interne fonctionnaire stagiaire décret 92-1194 stage évaluation",
            "FPT entretien professionnel titularisation fonctionnaire stagiaire stage évaluation décret 92-1194 reprise ancienneté",
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
         "preconisation medicale", "préconisation médicale", "adapter mon poste",
         "conditions de securite sont dangereuses", "conditions de sécurité sont dangereuses",
         "poste dangereux", "sanctionne apres avoir signale des risques",
         "sanctionne apres avoir signale un danger",
         "represailles apres signalement de risques",
         "represailles apres signalement d un danger", "risques psychosociaux"),
        (
            "FPT santé sécurité travail décret 85-603 droit de retrait danger grave imminent",
            "fonction publique territoriale document unique médecin du travail prévention risques professionnels",
        ),
    ),
    (
        ("disponibilite pour convenances personnelles",
         "disponibilité pour convenances personnelles",
         "mise en disponibilite pour convenances personnelles",
         "mise en disponibilité pour convenances personnelles",
         "convenances personnelles"),
        (
            "décret 86-68 du 13 janvier 1986 article 21 disponibilité pour convenances personnelles fonctionnaire territorial titulaire durée renouvellement nécessités du service",
            "CGFP positions statutaires disponibilité fonctionnaire territorial convenances personnelles réintégration",
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

def _is_professional_evaluation_question(question: str) -> bool:
    folded = _fold(str(question or ""))
    return any(
        _contains_trigger(folded, marker)
        for marker in (
            "evaluation annuelle", "evaluation a charge", "contester mon evaluation",
            "contestation evaluation", "compte rendu d evaluation",
            "evaluation professionnelle", "entretien professionnel",
        )
    )


def _is_explicit_functionary_status(question: str) -> bool:
    folded = _fold(str(question or ""))
    return any(
        _contains_trigger(folded, marker)
        for marker in (
            "fonctionnaire titulaire", "agent titulaire", "je suis titulaire",
            "fonctionnaire stagiaire", "agent stagiaire", "fonctionnaire",
            "stagiaire de la fonction publique",
        )
    )


def _is_contractual_evaluation_question(question: str) -> bool:
    folded = _fold(str(question or ""))
    has_evaluation = any(
        _contains_trigger(folded, marker)
        for marker in (
            "evaluation annuelle", "evaluation professionnelle",
            "entretien professionnel", "compte rendu d evaluation",
        )
    )
    has_contractual_status = any(
        _contains_trigger(folded, marker)
        for marker in ("agent contractuel", "contractuel", "contractuels", "CDD", "CDI")
    )
    return has_evaluation and has_contractual_status


def build_official_search_queries(question: str, max_queries: int = 6) -> list[str]:
    """Build a small set of distinct, topic-focused legal retrieval queries.

    The original expanded query remains first for backward-compatible recall.
    Additional axes are only emitted for explicitly recognized topics.
    """
    original = str(question or "").strip()
    contractual_evaluation = _is_contractual_evaluation_question(original)
    functionary_evaluation = (
        _is_professional_evaluation_question(original)
        and _is_explicit_functionary_status(original)
    )
    primary = build_official_search_query(question)
    if not primary:
        return []
    queries = [primary]
    current_turn = original.splitlines()[0] if original else ""
    if _ARTICLE_REFERENCE.search(current_turn) and _DIRECT_ARTICLE_LOOKUP.search(_fold(current_turn)):
        return queries
    folded = _fold(original)
    matched_axes = []
    contract_triggers, contract_axes = next(
        (triggers, axes)
        for triggers, axes in _TOPIC_RESEARCH_AXES
        if "agent contractuel" in triggers
    )
    other_topic_present = any(
        any(_contains_trigger(folded, trigger) for trigger in triggers)
        for triggers, _axes in _TOPIC_RESEARCH_AXES
        if triggers != contract_triggers
    )
    ihts_topic_present = any(
        "IHTS" in axes[0]
        and any(_contains_trigger(folded, trigger) for trigger in triggers)
        for triggers, axes in _TOPIC_RESEARCH_AXES
    )
    independent_working_time_triggers = (
        "temps de travail", "duree du travail", "annualisation", "astreinte",
        "cycle de travail", "rtt", "compteur d heures",
        "compteur d heures remis a zero",
    )
    independent_working_time_present = any(
        _contains_trigger(folded, trigger)
        for trigger in independent_working_time_triggers
    )
    therapeutic_part_time_present = _is_therapeutic_part_time_question(original)
    personal_convenience_availability = any(
        _contains_trigger(folded, trigger)
        for trigger in (
            "disponibilite pour convenances personnelles",
            "mise en disponibilite pour convenances personnelles",
            "convenances personnelles",
        )
    )
    union_assistance_convocation = _is_union_assistance_convocation_question(original)
    for triggers, axes in _TOPIC_RESEARCH_AXES:
        if union_assistance_convocation and "CGFP livre II droit syndical" in axes[0]:
            continue
        # A personal-convenience availability request has its own implementing
        # decree; do not dilute it with the broader mutation/following-spouse route.
        if personal_convenience_availability and (
            "mutation dans l interet du service" in triggers
            or "titulaire peut il" in triggers
        ):
            continue
        # A therapeutic return is not ordinary part-time work. Keep its
        # dedicated CGFP/decree axis and suppress the generic IHTS expansion.
        if therapeutic_part_time_present and "temps partiel heures supplémentaires IHTS" in axes[0]:
            continue
        # Overtime/IHTS is already a dedicated legal topic. Do not count the
        # generic time-work axis as a second issue unless the wording also
        # raises an independent cycle, annualisation, on-call or counter issue.
        if (
            "annualisation" in triggers
            and ihts_topic_present
            and not independent_working_time_present
        ):
            continue
        if not any(_contains_trigger(folded, trigger) for trigger in triggers):
            continue
        # "Je suis contractuel" identifies status, not the legal topic. Do not
        # let it displace a substantive topic such as IHTS or union rights.
        if triggers == contract_triggers and (
            other_topic_present
        ):
            continue
        matched_axes.append(axes)

    # "Et pour les contractuels ?" is a status comparison, not necessarily a
    # contract-law issue. Use the contract axis only when no substantive topic
    # is already present in the contextual question.
    if not matched_axes and re.search(r"\b(?:et\s+)?pour\s+les?\s+contractuels?\b", folded):
        matched_axes = [contract_axes]

    # Contract agents' annual assessments must be researched under the
    # territorial contractual regime, not the civil-servant evaluation decree.
    if contractual_evaluation:
        matched_axes = [
            axes for axes in matched_axes
            if "CGFP L521-1" not in " ".join(axes)
            and "décret 2014-1526" not in " ".join(axes)
            and "CGFP livre V" not in " ".join(axes)
        ]
        matched_axes.insert(0, (
            "décret 88-145 article 1-3 agent contractuel territorial emploi permanent CDI CDD supérieur à un an contrat de projet entretien professionnel compte rendu observations révision CCP",
            "jurisprudence administrative évaluation professionnelle agent contractuel territorial impartialité erreur manifeste procédure",
        ))
    elif functionary_evaluation:
        matched_axes = [
            tuple(axis for axis in axes if "décret 88-145" not in axis)
            for axes in matched_axes
        ]

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

    # Keep the usual three-query budget for ordinary questions. When the
    # wording explicitly combines at least three recognized legal topics,
    # reserve one focused query for each topic instead of silently dropping
    # the third issue behind the global cap. The hard ceiling limits provider
    # fan-out; larger compound requests are handled in a later pass.
    explicit_compound = bool(re.search(
        r"\b(?:et|ainsi que|par ailleurs|de plus|egalement)\b|[;?]\s*(?:et|puis|ensuite)\b",
        folded,
    ))
    query_limit = max(1, min(max_queries, 4 if _is_professional_evaluation_question(original) else 3))
    if explicit_compound and len(matched_axes) >= 3:
        query_limit = min(max_queries, len(matched_axes) + 1)

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


def build_official_research_axes(question: str) -> list[str]:
    """Return distinct recognized legal topics, not retrieval variants.

    Generic fallback and case-law expansion queries improve recall but are not
    independent user sub-questions and must not become mandatory answer axes.
    """
    original = str(question or "").strip()
    current_turn = original.splitlines()[0] if original else ""
    if not original or (
        _ARTICLE_REFERENCE.search(current_turn)
        and _DIRECT_ARTICLE_LOOKUP.search(_fold(current_turn))
    ):
        return []
    folded = _fold(original)
    # An invitation to bring a union representative to an unspecified
    # hierarchical summons is not enough to classify the procedure. The
    # chatbot asks for clarification first; do not turn the competing
    # ordinary-interview and disciplinary routes into mandatory answer axes.
    union_assistance_markers = (
        "accompagne d un syndicat",
        "accompagne par un syndicat",
        "accompagne d un representant syndical",
        "accompagne par un representant syndical",
        "assiste par un representant syndical",
        "venir avec mon syndicat",
        "venir avec un syndicat",
        "assistance syndicale lors d une convocation",
        "accompagnement syndical lors d une convocation",
        "accompagnement syndical", "assistance syndicale",
        "etre accompagne par un representant syndical",
        "etre assiste par un representant syndical",
    )
    union_summons_markers = (
        "convocation", "convoque par ma hierarchie", "convoque par sa hierarchie",
        "convoque par mon chef", "convoque par son chef",
        "entretien avec ma hierarchie", "entretien hierarchique",
    )
    explicit_procedure_markers = (
        "procedure disciplinaire",
        "entretien disciplinaire",
        "entretien ordinaire",
        "simple entretien",
        "enquete administrative",
        "audition disciplinaire",
    )
    if (
        any(_contains_trigger(folded, marker) for marker in union_assistance_markers)
        and any(_contains_trigger(folded, marker) for marker in union_summons_markers)
        and not any(_contains_trigger(folded, marker) for marker in explicit_procedure_markers)
    ):
        return []
    if _is_contractual_evaluation_question(original):
        return [
            "décret 88-145 article 1-3 agent contractuel territorial emploi permanent CDI CDD supérieur à un an contrat de projet entretien professionnel compte rendu observations révision CCP"
        ]
    is_evaluation_question = _is_professional_evaluation_question(original)
    explicit_functionary_status = _is_explicit_functionary_status(original)
    if is_evaluation_question and not explicit_functionary_status:
        # The wording does not establish whether the evaluated person is a
        # civil servant or a contract agent. Keep both legal regimes as
        # conditional research axes; the answer must not apply either blindly.
        return [
            "CGFP L521-1 L521-3 L521-5 décret 2014-1526 articles 2 5 6 7 fonctionnaire territorial demande révision CAP délais",
            "décret 88-145 article 1-3 agent contractuel territorial emploi permanent CDI CDD supérieur à un an contrat de projet révision CCP délais",
        ]
    if is_evaluation_question and explicit_functionary_status:
        return [
            "CGFP L521-1 L521-3 L521-5 décret 2014-1526 articles 2 5 6 7 fonctionnaire territorial demande révision CAP délais"
        ]
    contract_triggers, _contract_axes = next(
        (triggers, axes)
        for triggers, axes in _TOPIC_RESEARCH_AXES
        if "agent contractuel" in triggers
    )
    other_topic_present = any(
        any(_contains_trigger(folded, trigger) for trigger in triggers)
        for triggers, _axes in _TOPIC_RESEARCH_AXES
        if triggers != contract_triggers
    )
    ihts_topic_present = any(
        "IHTS" in axes[0]
        and any(_contains_trigger(folded, trigger) for trigger in triggers)
        for triggers, axes in _TOPIC_RESEARCH_AXES
    )
    independent_working_time_triggers = (
        "temps de travail", "duree du travail", "annualisation", "astreinte",
        "cycle de travail", "rtt", "compteur d heures",
        "compteur d heures remis a zero",
    )
    independent_working_time_present = any(
        _contains_trigger(folded, trigger)
        for trigger in independent_working_time_triggers
    )
    medico_social_ihts_markers = (
        "filiere medico-sociale", "filiere medico-technique",
        "cadre de sante", "cadres de sante",
        "cadre territorial de sante", "cadres territoriaux de sante",
        "cadre de sante paramedical", "cadres de sante paramedicaux",
        "technicien paramedical", "techniciens paramedicaux",
        "sage-femme", "sage femme", "sages-femmes", "puericultrice",
        "puericultrices", "auxiliaire de puericulture",
        "auxiliaires de puericulture", "masseur-kinesitherapeute",
        "masseurs-kinesitherapeutes", "orthophoniste", "orthophonistes",
        "ergotherapeute", "ergotherapeutes", "psychomotricien",
        "psychomotriciens",
    )
    medico_social_ihts_present = ihts_topic_present and any(
        _contains_trigger(folded, marker)
        for marker in medico_social_ihts_markers
    )
    axes_found = []
    therapeutic_part_time_present = _is_therapeutic_part_time_question(original)
    union_assistance_convocation = _is_union_assistance_convocation_question(original)
    for triggers, axes in _TOPIC_RESEARCH_AXES:
        if union_assistance_convocation and "CGFP livre II droit syndical" in axes[0]:
            continue
        if therapeutic_part_time_present and "temps partiel heures supplémentaires IHTS" in axes[0]:
            continue
        if (
            "annualisation" in triggers
            and ihts_topic_present
            and not independent_working_time_present
        ):
            continue
        matched_triggers = [
            trigger for trigger in triggers
            if _contains_trigger(folded, trigger)
        ]
        if not matched_triggers:
            continue
        if triggers == contract_triggers and other_topic_present:
            continue
        # These are compound situations with two legally distinct research
        # dimensions. Preserve both axes instead of collapsing each tuple to
        # its first query (which silently discarded the second dimension).
        if (
            "convocation par ma hierarchie" in triggers
            or "agresse par un usager" in triggers
            or any(trigger in matched_triggers for trigger in (
                "deces d un grand pere", "deces d une grand mere",
                "deces de son grand pere", "deces de sa grand mere",
                "deces de mon grand pere", "deces de ma grand mere",
                "deces d un proche", "deces d un membre de la famille",
                "deces d un ascendant", "grand pere decede", "grand mere decedee",
                "grand parent decede", "obseques", "autorisation d absence pour deces",
            ))
        ):
            axes_found.extend(axis[:500] for axis in axes[:2])
            continue
        axes_found.append(axes[0][:500])
    if medico_social_ihts_present:
        axes_found.append(
            "IHTS FPT : vérifier l'équivalence exacte du cadre médico-social ou médico-technique "
            "et l'éventuel contingent mensuel spécifique avant d'appliquer le plafond général"
        )
    return list(dict.fromkeys(axes_found)) if len(axes_found) > 1 else []


def select_required_research_axes(deterministic_axes: list[str] | None) -> list[str]:
    """Keep mandatory coverage axes tied to deterministic analysis of the user's question.

    Model-generated issue labels are useful planning hints, but they are not a
    reliable basis for mandatory coverage checks: they may be unsearched,
    duplicative, or phrased differently from the validated research axes.
    """
    selected: list[str] = []
    seen: set[str] = set()
    for axis in deterministic_axes or []:
        if not isinstance(axis, str):
            continue
        normalized = " ".join(axis.split())[:500]
        if len(normalized) < 8 or normalized.casefold() in seen:
            continue
        seen.add(normalized.casefold())
        selected.append(normalized)
        if len(selected) >= 10:
            break
    return selected


def merge_ai_and_fallback_research_queries(
    ai_queries: list[str],
    fallback_queries: list[str],
    fallback_axes: list[str],
    *,
    max_queries: int = 5,
) -> list[str]:
    """Preserve model-led research while retaining independent fallback axes for compound cases.

    The fallback planner is not treated as legal authority. Its independent retrieval
    queries provide recall insurance when the model planner omits one of the explicit
    topics in a compound question. Keep a bounded fan-out and give the model's first
    queries priority.
    """
    limit = max(1, min(int(max_queries), 8))
    primary = list(dict.fromkeys(
        " ".join(str(query or "").split())[:500]
        for query in (ai_queries or [])
        if isinstance(query, str) and query.strip()
    ))
    fallback = list(dict.fromkeys(
        " ".join(str(query or "").split())[:500]
        for query in (fallback_queries or [])
        if isinstance(query, str) and query.strip()
    ))
    if not primary:
        return fallback[:limit]
    if not fallback:
        return primary[:limit]

    # Keep one deterministic fallback even when the planner produced only the
    # broad user query. When focused fallback queries exist, reserve one for
    # each independently detected legal axis; never let a model-only plan
    # consume the entire retrieval budget.
    if limit == 1:
        # With a one-query budget, prefer deterministic retrieval over an
        # unverified model plan: this is the only route to official sources.
        reserved = fallback[:1]
    elif len(fallback) == 1:
        reserved = fallback[:1]
    else:
        reserve_count = max(1, min(len(fallback_axes or []), len(fallback) - 1, limit - 1))
        reserved = fallback[1:1 + reserve_count]
    primary_budget = max(0, limit - len(reserved))
    ordered = [*primary[:primary_budget], *reserved, *primary[primary_budget:], *fallback]
    merged: list[str] = []
    seen: set[str] = set()
    for query in ordered:
        key = query.casefold()
        if key in seen:
            continue
        seen.add(key)
        merged.append(query)
        if len(merged) >= limit:
            break
    return merged or fallback[:limit]
