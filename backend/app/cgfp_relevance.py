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
        "key": "citis",
        "triggers": (
            "citis", "conge pour invalidite temporaire imputable au service",
            "invalidite temporaire imputable au service",
        ),
        "expansion": (
            "congé pour invalidité temporaire imputable au service accident reconnu imputable "
            "accident de trajet maladie contractée en service incapacité temporaire de travail "
            "intégralité du traitement reprise du service retraite période de service effectif "
            "déclaration expertise médicale imputabilité au service"
        ),
        "anchors": (
            "conge pour invalidite temporaire imputable au service",
            "accident reconnu imputable au service", "accident de trajet",
            "maladie contractee en service", "integralite du traitement",
            "periode de service effectif",
        ),
        "boosts": {
            "conge pour invalidite temporaire imputable au service": 18.0,
            "accident reconnu imputable au service": 12.0,
            "integralite du traitement": 10.0,
            "accident de trajet": 8.0,
        },
        "exclude_unless_anchor": (),
    },
    {
        "key": "temps_partiel_therapeutique",
        "triggers": (
            "temps partiel therapeutique", "temps partiel pour raison therapeutique",
            "tpt",
        ),
        "expansion": (
            "temps partiel pour raison thérapeutique maintien retour emploi amélioration état santé "
            "rééducation réadaptation professionnelle quotité mi temps traitement intégral "
            "supplément familial traitement indemnité résidence durée continue discontinue "
            "autorisation nouvelle période"
        ),
        "anchors": (
            "temps partiel pour raison therapeutique", "maintien ou le retour a l emploi",
            "reeducation", "readaptation professionnelle", "ne peut pas etre inferieur au mi temps",
            "integralite de son traitement", "supplement familial de traitement",
            "indemnite de residence", "continue ou discontinue",
        ),
        "boosts": {
            "temps partiel pour raison therapeutique": 18.0,
            "maintien ou le retour a l emploi": 10.0,
            "integralite de son traitement": 10.0,
            "reeducation": 7.0,
            "readaptation professionnelle": 7.0,
        },
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
    {
        "key": "droits_obligations_deontologie",
        "triggers": (
            "obligations professionnelles", "obligation de neutralite", "neutralite",
            "laicite", "secret professionnel", "discretion professionnelle",
            "devoir de reserve", "integrite", "probite", "conflit d interets",
            "cumul d activites", "obligation d obeissance",
        ),
        "expansion": (
            "droits obligations agents publics territoriaux neutralité laïcité dignité "
            "impartialité intégrité probité secret professionnel discrétion professionnelle "
            "obéissance hiérarchique cumul activités conflits intérêts"
        ),
        "anchors": (
            "neutralite", "laicite", "secret professionnel", "discretion professionnelle",
            "integrite", "probite", "conflit d interets", "cumul d activites",
            "obligation d obeissance", "dignité",
        ),
        "boosts": {"obligations": 8.0, "neutralite": 12.0, "laicite": 10.0},
        "exclude_unless_anchor": (),
    },
    {
        "key": "recrutement_stage_titularisation",
        "triggers": (
            "recrutement", "concours", "concours externe", "concours interne",
            "liste d aptitude", "nomination stagiaire", "fonctionnaire stagiaire",
            "stage", "titularisation", "refus de titularisation", "prolongation de stage",
        ),
        "expansion": (
            "recrutement fonction publique territoriale concours liste aptitude nomination "
            "fonctionnaire stagiaire stage titularisation prolongation stage refus titularisation "
            "aptitude physique autorité territoriale"
        ),
        "anchors": (
            "concours", "liste d aptitude", "fonctionnaire stagiaire", "titularisation",
            "nomination stagiaire", "stage", "refus de titularisation",
        ),
        "boosts": {"titularisation": 14.0, "fonctionnaire stagiaire": 12.0, "concours": 7.0},
        "exclude_unless_anchor": (),
    },
    {
        "key": "carriere_avancement_evaluation",
        "triggers": (
            "avancement", "avancement d echelon", "avancement de grade",
            "promotion interne", "carriere", "entretien professionnel",
            "evaluation professionnelle", "evaluation annuelle", "evaluation a charge",
            "contester evaluation", "contestation evaluation", "compte rendu d evaluation",
            "compte rendu d entretien", "tableau d avancement", "ligne directrice de gestion",
        ),
        "expansion": (
            "CGFP L521-1 L521-3 L521-5 appréciation valeur professionnelle fonctionnaire territorial "
            "entretien professionnel annuel compte rendu révision contestation décret 2014-1526 "
            "articles 2 3 4 5 6 7 autorité territoriale commission administrative paritaire"
        ),
        "anchors": (
            "avancement", "avancement d echelon", "avancement de grade",
            "promotion interne", "entretien professionnel", "evaluation annuelle",
            "evaluation a charge", "contester evaluation", "compte rendu d evaluation",
            "valeur professionnelle", "tableau d avancement", "ligne directrice de gestion",
        ),
        "boosts": {"avancement": 10.0, "promotion interne": 12.0, "entretien professionnel": 9.0,
                   "evaluation annuelle": 14.0, "contester evaluation": 16.0},
        "exclude_unless_anchor": (),
    },
    {
        "key": "mobilite_positions_statutaires",
        "triggers": (
            "mobilite", "mutation", "mute", "muter", "detachement", "mise a disposition",
            "disponibilite", "integration directe", "reclassement",
            "position d activite", "position statutaire",
        ),
        "expansion": (
            "fonctionnaire territorial mobilité mutation détachement mise à disposition "
            "disponibilité intégration directe reclassement positions statutaires réintégration "
            "emploi collectivité territoriale"
        ),
        "anchors": (
            "mobilite", "mutation", "mute", "detachement", "mise a disposition",
            "disponibilite", "integration directe", "reclassement",
            "position d activite", "reintegration",
        ),
        "boosts": {"detachement": 10.0, "disponibilite": 10.0, "mutation": 9.0},
        "exclude_unless_anchor": (),
    },
    {
        "key": "formation_professionnelle",
        "triggers": (
            "formation professionnelle", "formation cnfpt", "cnfpt",
            "compte personnel de formation", "cpf", "vae",
            "bilan de competences", "conge de formation",
            "formation obligatoire", "formation d integration",
        ),
        "expansion": (
            "formation professionnelle agents territoriaux CNFPT formation intégration "
            "professionnalisation perfectionnement compte personnel formation CPF VAE "
            "bilan compétences congé formation obligation employeur"
        ),
        "anchors": (
            "formation professionnelle", "cnfpt", "compte personnel de formation",
            "bilan de competences", "conge de formation", "formation d integration",
            "formation de professionnalisation", "validation des acquis",
        ),
        "boosts": {"formation professionnelle": 12.0, "cnfpt": 12.0, "compte personnel de formation": 9.0},
        "exclude_unless_anchor": (),
    },
    {
        "key": "conges_absences_familiales",
        "triggers": (
            "conges annuels", "conge annuel", "conge parental", "conge maternite",
            "conge paternite", "conge adoption", "conge proche aidant",
            "conge presence parentale", "autorisation speciale d absence",
            "absence familiale", "temps partiel therapeutique",
        ),
        "expansion": (
            "agents territoriaux congés annuels congé parental maternité paternité adoption "
            "proche aidant présence parentale autorisation spéciale absence événements familiaux "
            "temps partiel thérapeutique droits garanties"
        ),
        "anchors": (
            "conges annuels", "conge parental", "conge maternite", "conge paternite",
            "conge adoption", "conge proche aidant", "conge de presence parentale",
            "autorisation speciale d absence", "temps partiel therapeutique",
        ),
        "boosts": {"conge parental": 10.0, "conge maternite": 10.0, "conges annuels": 8.0},
        "exclude_unless_anchor": (),
    },
    {
        "key": "sante_securite_prevention",
        "triggers": (
            "sante et securite", "hygiene et securite", "risques professionnels",
            "prevention des risques", "medecine preventive", "medecin du travail",
            "accident de service", "maladie professionnelle", "citis",
            "inaptitude physique", "reclassement pour inaptitude",
        ),
        "expansion": (
            "fonction publique territoriale santé sécurité travail prévention risques professionnels "
            "médecine préventive accident service maladie professionnelle CITIS aptitude physique "
            "inaptitude reclassement protection santé agents"
        ),
        "anchors": (
            "sante et securite", "hygiene et securite", "prevention des risques",
            "medecine preventive", "accident de service", "maladie professionnelle",
            "citis", "inaptitude physique", "reclassement",
        ),
        "boosts": {"prevention des risques": 10.0, "medecine preventive": 12.0, "citis": 12.0},
        "exclude_unless_anchor": (),
    },
    {
        "key": "greve_dialogue_social_representativite",
        "triggers": (
            "droit de greve", "greve", "preavis de greve", "service minimum",
            "dialogue social", "comite social territorial", "cst",
            "representants du personnel", "representativite syndicale",
            "negociation collective", "accord collectif",
        ),
        "expansion": (
            "fonction publique territoriale droit de grève préavis service minimum dialogue social "
            "comité social territorial CST représentants du personnel organisations syndicales "
            "représentativité négociation accords collectifs garanties agents"
        ),
        "anchors": (
            "droit de greve", "preavis de greve", "service minimum",
            "dialogue social", "comite social territorial", "representants du personnel",
            "representativite syndicale", "negociation collective", "accord collectif",
        ),
        "boosts": {"droit de greve": 12.0, "comite social territorial": 10.0, "dialogue social": 8.0},
        "exclude_unless_anchor": (),
    },
    {
        "key": "cessation_fonctions_retraite",
        "triggers": (
            "demission", "retraite", "radiation des cadres", "licenciement",
            "abandon de poste", "perte de la qualite de fonctionnaire",
            "cessation definitive de fonctions", "rupture conventionnelle",
            "retraite pour invalidite", "mise a la retraite",
        ),
        "expansion": (
            "fonctionnaire territorial cessation définitive fonctions démission retraite radiation "
            "cadres licenciement abandon poste perte qualité fonctionnaire rupture conventionnelle "
            "retraite invalidité garanties procédure"
        ),
        "anchors": (
            "demission", "retraite", "radiation des cadres", "licenciement",
            "abandon de poste", "cessation definitive de fonctions",
            "rupture conventionnelle", "retraite pour invalidite",
        ),
        "boosts": {"radiation des cadres": 10.0, "retraite": 8.0, "demission": 8.0},
        "exclude_unless_anchor": (),
    },
    {
        "key": "egalite_discrimination",
        "triggers": (
            "discrimination", "egalite professionnelle", "egalite femmes hommes",
            "sexisme", "grossesse", "origine", "handicap", "amenagement de poste",
            "lanceur d alerte", "alerte ethique",
        ),
        "expansion": (
            "agents publics territoriaux égalité professionnelle non discrimination égalité femmes "
            "hommes handicap grossesse aménagement poste lanceur alerte protection signalement "
            "agissements sexistes"
        ),
        "anchors": (
            "discrimination", "egalite professionnelle", "egalite femmes hommes",
            "agissement sexiste", "grossesse", "handicap", "amenagement de poste",
            "lanceur d alerte", "signalement",
        ),
        "boosts": {"discrimination": 12.0, "egalite professionnelle": 10.0, "handicap": 8.0},
        "exclude_unless_anchor": (),
    },
    {
        "key": "droits_syndicaux_dialogue_social",
        "triggers": (
            "droit syndical", "droits syndicaux", "liberte syndicale",
            "asa syndicale", "autorisation speciale d absence syndicale",
            "decharge syndicale", "decharge d activite de service",
            "credit de temps syndical", "local syndical", "locaux syndicaux",
            "reunion d information syndicale", "formation syndicale",
            "representant syndical", "representants du personnel",
        ),
        "expansion": (
            "CGFP livre II droit syndical fonction publique territoriale liberté syndicale "
            "autorisations spéciales absence décharges activité service crédit temps syndical "
            "locaux syndicaux réunions information formation organisations syndicales dialogue social"
        ),
        "anchors": (
            "droit syndical", "liberte syndicale", "autorisation speciale d absence",
            "decharge d activite de service", "credit de temps syndical",
            "local syndical", "reunion d information syndicale",
            "formation syndicale", "representant syndical",
        ),
        "boosts": {"droit syndical": 14.0, "liberte syndicale": 12.0, "decharge d activite de service": 10.0},
        "exclude_unless_anchor": (),
    },
)


def _matching_topics(query: str) -> list[dict[str, Any]]:
    folded = normalize(query)
    matched = [
        topic for topic in _TOPICS
        if any(normalize(trigger) in folded for trigger in topic["triggers"])
    ]
    # Health-related routes are intentionally specific. If the question
    # explicitly names CITIS or therapeutic part-time, do not dilute retrieval
    # with generic leave, working-time or sick-leave expansions.
    focused_health = [
        topic for topic in matched
        if topic["key"] in {"citis", "temps_partiel_therapeutique"}
    ]
    if focused_health:
        return focused_health

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
        # Topic anchors and exclusions may improve ordering, but must not
        # suppress lexical candidates: applicable general provisions may use
        # different vocabulary from the question and this topic taxonomy.
        unique_anchors = list(dict.fromkeys(matched_anchors))
        if excluded:
            score *= 0.35
        elif not unique_anchors:
            score *= 0.55
        ranked.append({
            **{k: v for k, v in item.items() if not k.startswith("_")},
            "score": round(score, 4),
            "matched_concepts": unique_anchors[:6],
            "relevance_label": (
                "Correspondance lexicale — pertinence à vérifier"
                if excluded or not unique_anchors
                else "Fondement à examiner en priorité" if score >= 10
                else "Disposition complémentaire à examiner"
            ),
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
