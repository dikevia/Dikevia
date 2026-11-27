from app.fpt_scope import _matched_topic_families, classify_public_service_scope, is_topic_relevant_source
from app.orchestrator import (
    _build_code_research_queries,
    _build_targeted_cgfp_article_queries,
    _build_targeted_regulatory_queries,
    filter_irrelevant_sources_for_display,
    _source_relevant_to_any_research_axis,
)


def test_relevant_source_for_same_legal_topic_is_kept():
    question = "Quels sont mes droits concernant un congé maladie ?"
    source = {
        "title": "Congé de maladie des fonctionnaires territoriaux",
        "text": "Dispositions relatives au congé de maladie et aux agents territoriaux. " * 4,
    }
    assert is_topic_relevant_source(question, source) is True


def test_source_from_clearly_unrelated_topic_is_rejected():
    question = "Comment sont calculées les heures supplémentaires ?"
    source = {
        "title": "Régime disciplinaire des fonctionnaires",
        "text": "Sanction disciplinaire, conseil de discipline et exclusion temporaire.",
    }
    assert is_topic_relevant_source(question, source) is False


def test_cross_cutting_or_unclassified_source_is_preserved():
    question = "Quels sont mes droits concernant un congé maladie ?"
    source = {
        "title": "Code général de la fonction publique",
        "text": "Les agents publics bénéficient des garanties prévues par les textes applicables.",
    }
    assert is_topic_relevant_source(question, source) is True


def test_multi_topic_question_keeps_either_relevant_source_family():
    question = "Quels sont mes droits en congé maladie et sur ma rémunération ?"
    source = {
        "title": "Rémunération des agents publics",
        "text": "Dispositions relatives au traitement indiciaire et à la rémunération.",
    }
    assert is_topic_relevant_source(question, source) is True


def test_display_filter_hides_explicitly_unrelated_topic_sources():
    sources = [
        {"source_id": "relevant", "topic_relevant": True},
        {"source_id": "unrelated", "topic_relevant": False},
        {"source_id": "legacy_ihts_filter", "ihts_relevant": False},
    ]
    assert [s["source_id"] for s in filter_irrelevant_sources_for_display(sources)] == ["relevant"]



def test_working_time_question_keeps_related_territorial_indemnity_source():
    question = "Comment sont indemnisées les heures supplémentaires ?"
    source = {
        "title": "Décret relatif au régime indemnitaire des fonctionnaires territoriaux",
        "text": "Dispositions relatives au régime indemnitaire applicable aux collectivités territoriales.",
    }
    assert is_topic_relevant_source(question, source) is True


def test_sick_leave_question_keeps_related_remuneration_source():
    question = "Comment est maintenue la rémunération pendant un congé maladie ?"
    source = {
        "title": "Règles de rémunération des agents publics",
        "text": "Dispositions relatives au traitement indiciaire et à la rémunération.",
    }
    assert is_topic_relevant_source(question, source) is True



def test_short_topic_acronym_does_not_match_inside_an_unrelated_word():
    question = "Quels sont mes droits pendant un congé maladie ?"
    source = {
        "title": "Organisation des services et recettes de la collectivité",
        "text": "Les recettes de fonctionnement financent les services publics locaux.",
    }
    assert is_topic_relevant_source(question, source) is True



def test_french_demonstrative_cet_is_not_mistaken_for_leave_acronym():
    assert "LEAVE" not in _matched_topic_families("Cet arrêté fixe les règles applicables.")
    assert "LEAVE" in _matched_topic_families("Le CET permet de conserver des jours de congé.")


def test_titular_status_alone_does_not_trigger_termination_topic_filter():
    question = "Je suis fonctionnaire titulaire : quels sont mes droits pendant un congé maladie ?"
    source = {
        "title": "Congé de maladie des fonctionnaires territoriaux",
        "text": "Dispositions relatives au congé de maladie et aux agents territoriaux. " * 4,
    }
    assert "TERMINATION_OF_TITULAR" not in _matched_topic_families(question)
    assert is_topic_relevant_source(question, source) is True


def test_titular_status_alone_does_not_hide_working_time_sources():
    question = "Je suis fonctionnaire titulaire : comment sont calculées mes heures supplémentaires ?"
    source = {
        "title": "Indemnités horaires pour travaux supplémentaires",
        "text": "Règles relatives aux IHTS et aux agents territoriaux. " * 4,
    }
    assert "TERMINATION_OF_TITULAR" not in _matched_topic_families(question)
    assert is_topic_relevant_source(question, source) is True


def test_actual_termination_question_still_triggers_termination_filter():
    question = "Je suis fonctionnaire titulaire, ma collectivité peut-elle me licencier ?"
    assert "TERMINATION_OF_TITULAR" in _matched_topic_families(question)

def test_composite_question_keeps_sources_for_non_ihts_subquestions():
    axes = [
        "Comment sont indemnisées les heures supplémentaires ?",
        "Quels sont les droits pendant un congé maladie ?",
    ]
    sick_leave_source = {
        "title": "Congé de maladie des fonctionnaires territoriaux",
        "text": "Dispositions relatives au congé de maladie et aux agents territoriaux. " * 4,
    }
    assert _source_relevant_to_any_research_axis(axes, sick_leave_source) is True


def test_composite_question_still_rejects_irrelevant_ihts_credit_sources():
    axes = [
        "Comment sont indemnisées les heures supplémentaires ?",
        "Quels sont les droits pendant un congé maladie ?",
    ]
    unrelated_credit = {
        "title": "CGFP R422-96",
        "article": "R422-96",
        "excerpt": "Crédit d'heures supplémentaires pour prévenir une inaptitude.",
    }
    assert _source_relevant_to_any_research_axis(axes, unrelated_credit) is False



def test_required_answer_axes_include_only_distinct_recognized_legal_topics():
    from app.legal_search_plan import (
        build_official_research_axes,
        build_official_search_queries,
    )

    compound = "Mon employeur refuse mes heures supplémentaires et mon arrêt maladie."
    axes = build_official_research_axes(compound)
    queries = build_official_search_queries(compound)
    assert len(axes) >= 2
    assert all(axis in queries for axis in axes)

    # A general question can have several retrieval variants, but those are
    # not separate legal questions and must not become mandatory answer axes.
    general = "Quels sont les droits des agents territoriaux ?"
    assert len(build_official_search_queries(general)) > 1
    assert build_official_research_axes(general) == []


def test_annual_professional_evaluation_rejects_unrelated_evaluation_hits():
    question = (
        "Mon agent de maîtrise m'a fait une évaluation annuelle à charge, "
        "puis-je la contester ?"
    )
    unrelated_sources = [
        {
            "title": "Entretien de suivi des agents à activité syndicale",
            "text": "Évaluation et suivi de l'activité syndicale.",
        },
        {
            "title": "Évaluation des emplois supérieurs ministériels",
            "text": "Évaluation des emplois supérieurs dans les administrations ministérielles.",
        },
        {
            "title": "Comité chargé de débattre des évaluations et politiques RH",
            "text": "Débat sur les évaluations des politiques de ressources humaines.",
        },
        {
            "title": "Évaluation des compétences en matière de recrutement",
            "text": "Évaluation des compétences et procédure de recrutement.",
        },
    ]
    for source in unrelated_sources:
        assert is_topic_relevant_source(question, source) is False

    # A generic administrative-recourse source is cross-cutting, not an
    # unrelated topic, and must remain available for review.
    assert is_topic_relevant_source(
        question,
        {
            "title": "Recours administratif",
            "excerpt": "La décision administrative peut faire l'objet d'un recours préalable.",
        },
    ) is True


def test_annual_professional_evaluation_keeps_the_appraisal_report_rules():
    question = "Je souhaite contester mon entretien professionnel annuel."
    source = {
        "title": "Décret n° 2014-1526 relatif à l'entretien professionnel",
        "text": (
            "L'entretien professionnel annuel des fonctionnaires territoriaux "
            "donne lieu à un compte rendu et peut faire l'objet d'une demande de révision."
        ),
    }
    assert is_topic_relevant_source(question, source) is True


def test_six_year_cdi_question_rejects_unrelated_contract_and_hr_provisions():
    question = (
        "Un agent contractuel territorial en CDD peut-il obtenir un CDI "
        "après 6 ans de services ?"
    )
    relevant = {
        "title": "Code général de la fonction publique — article L332-10",
        "article": "L332-10",
        "text": (
            "Tout contrat établi ou renouvelé pour pourvoir un emploi permanent "
            "avec un agent contractuel territorial justifiant de six ans de services "
            "publics sur des fonctions de même catégorie hiérarchique est conclu "
            "pour une durée indéterminée."
        ),
    }
    unrelated = [
        {
            "title": "Code général de la fonction publique — article L554-3",
            "article": "L554-3",
            "text": "Indemnité de fin de contrat et plafond de rémunération brute globale.",
        },
        {
            "title": "Code général de la fonction publique — article L556-13",
            "article": "L556-13",
            "text": "Prolongation d'activité des agents contractuels avant la retraite.",
        },
        {
            "title": "Code général de la fonction publique — article L422-3",
            "article": "L422-3",
            "text": "Formation professionnelle et évolution des agents de catégorie C.",
        },
    ]

    assert is_topic_relevant_source(question, relevant) is True
    assert all(is_topic_relevant_source(question, source) is False for source in unrelated)


def test_fpe_overtime_relevance_does_not_require_fpt_ihts_implementing_markers():
    from app.orchestrator import _source_relevant_to_any_research_axis

    query = "heures supplémentaires des agents de la fonction publique de l'État"
    source = {
        "title": "Organisation du temps de travail dans la fonction publique de l'État",
        "text": (
            "Les agents de l'État peuvent être amenés à effectuer des heures "
            "supplémentaires selon les règles propres à leur administration."
        ),
    }
    assert _source_relevant_to_any_research_axis([query], source, "FPE") is True
    assert _source_relevant_to_any_research_axis([query], source, "FPT") is False


def test_fph_overtime_relevance_does_not_require_fpt_ihts_implementing_markers():
    from app.orchestrator import _source_relevant_to_any_research_axis

    query = "heures supplémentaires des personnels hospitaliers"
    source = {
        "title": "Organisation du temps de travail dans les établissements publics de santé",
        "text": (
            "Les personnels hospitaliers peuvent effectuer des heures "
            "supplémentaires selon les dispositions propres à la fonction publique hospitalière."
        ),
    }
    assert _source_relevant_to_any_research_axis([query], source, "FPH") is True
    assert _source_relevant_to_any_research_axis([query], source, "FPT") is False


def test_availability_question_rejects_unrelated_long_term_sick_leave_source():
    question = "Un fonctionnaire peut-il demander une disponibilité pour convenances personnelles ?"
    source = {
        "title": "Congé de longue durée (CLD) du fonctionnaire",
        "text": "Règles relatives au congé de longue durée et à la reprise après maladie.",
    }
    assert is_topic_relevant_source(question, source) is False


def test_availability_question_keeps_availability_regulation():
    question = "Un fonctionnaire peut-il demander une disponibilité pour convenances personnelles ?"
    source = {
        "title": "Décret relatif à la disponibilité des fonctionnaires territoriaux",
        "text": "Disponibilité sur demande pour convenances personnelles.",
    }
    assert is_topic_relevant_source(question, source) is True


def test_contractual_availability_question_rejects_titular_sick_leave_source():
    question = "Un agent contractuel peut-il être placé en disponibilité ?"
    source = {
        "title": "Congé de longue durée du fonctionnaire",
        "text": "Le congé de longue durée concerne les fonctionnaires titulaires.",
    }
    assert is_topic_relevant_source(question, source) is False


def test_cmo_exact_cgfp_articles_are_claim_eligible_only_from_live_legifrance():
    for number in range(1, 6):
        live = {
            "source_type": "LEGIFRANCE_API",
            "title": f"Code général de la fonction publique — article L822-{number}",
            "article": f"L822-{number}",
            "text": "Le fonctionnaire bénéficie du congé de maladie et des règles de rémunération applicables.",
        }
        snapshot = {**live, "source_type": "CGFP_SNAPSHOT"}
        live_scope = classify_public_service_scope(live, target_versant="FPT")
        snapshot_scope = classify_public_service_scope(snapshot, target_versant="FPT")
        assert live_scope["scope"] == "COMMON_PUBLIC_SERVICE"
        assert live_scope["analysis_eligible"] is True
        assert live_scope["claim_eligible"] is True
        assert snapshot_scope["analysis_eligible"] is True
        assert snapshot_scope["claim_eligible"] is False


def test_cmo_questions_trigger_exact_cgfp_and_territorial_regulatory_queries():
    question = "Quelles sont les règles du congé de maladie ordinaire et du jour de carence ?"
    assert _build_targeted_cgfp_article_queries(question, "FPT") == [
        "article L822-1", "article L822-2", "article L822-3", "article L822-4", "article L822-5",
    ]
    regulatory = _build_targeted_regulatory_queries(question, "FPT")
    assert any("décret n° 87-602" in query and "articles 14 et 15" in query for query in regulatory)
    assert any("loi n° 2017-1837" in query and "article 115" in query for query in regulatory)


def test_cmo_exact_queries_are_not_added_for_fpe_or_fph():
    question = "Congé de maladie ordinaire et jour de carence"
    assert _build_targeted_cgfp_article_queries(question, "FPE") == []
    assert _build_targeted_cgfp_article_queries(question, "FPH") == []
    assert _build_targeted_regulatory_queries(question, "FPE") == []
    assert _build_targeted_regulatory_queries(question, "FPH") == []


def test_cmo_exact_articles_are_prioritized_within_bounded_cgfp_query_budget():
    exact = _build_targeted_cgfp_article_queries(
        "Congé de maladie ordinaire et jour de carence", "FPT"
    )
    queries = _build_code_research_queries(
        ["broad", "specific", "another axis"],
        exact,
        max_queries=8,
    )
    assert queries == [
        "broad", "specific", "another axis",
        "article L822-1", "article L822-2", "article L822-3", "article L822-4", "article L822-5",
    ]


def test_cmo_query_rejects_unrelated_annual_leave_source():
    question = "Quelles sont les règles du congé de maladie ordinaire ?"
    unrelated = {
        "title": "Décret relatif au report de congés annuels non pris",
        "text": "Les congés annuels non pris en raison d'une maladie peuvent être reportés.",
    }
    assert is_topic_relevant_source(question, unrelated) is False


def test_cmo_query_keeps_exact_cgfp_article_without_ordinary_wording():
    question = "Congé de maladie ordinaire : jour de carence et rémunération"
    source = {
        "source_type": "LEGIFRANCE_API",
        "title": "Code général de la fonction publique — article L822-3",
        "article": "L822-3",
        "text": "Le fonctionnaire en congé de maladie perçoit 90 % de son traitement pendant trois mois.",
    }
    assert is_topic_relevant_source(question, source) is True

def test_semantic_direct_verdict_cannot_override_cmo_citis_exclusion(monkeypatch):
    import asyncio
    import app.orchestrator as orchestrator

    async def fake_evaluate_source_relevance(**kwargs):
        return {"citis": "DIRECT"}

    monkeypatch.setattr(orchestrator, "evaluate_source_relevance", fake_evaluate_source_relevance)
    question = (
        "Je suis fonctionnaire territorial titulaire. Quelles sont les règles "
        "du congé de maladie ordinaire, notamment le jour de carence et le maintien de rémunération ?"
    )
    source = {
        "source_id": "citis",
        "title": "Code général de la fonction publique — article L822-21",
        "article": "L822-21",
        "text": (
            "Le fonctionnaire en activité a droit à un congé pour invalidité "
            "temporaire imputable au service lorsque son incapacité temporaire "
            "de travail est consécutive à un accident reconnu imputable au service."
        ),
    }

    asyncio.run(orchestrator.apply_semantic_source_relevance(
        question=question,
        research_axes=[question],
        sources=[source],
        target_versant="FPT",
    ))

    assert source["research_axis_relevant"] is False
    assert source["semantic_relevance"] == "BLOCKED_BY_TOPIC_GUARD"

def test_cmo_keeps_decree_87_602_article_from_formatted_article_number_metadata():
    question = "Fonctionnaire territorial : règles du congé de maladie ordinaire et maintien de rémunération"
    source = {
        "source_type": "LEGIFRANCE_API",
        "title": "Décret n° 87-602 du 30 juillet 1987",
        "article_number": "Article 15 du décret",
        "text": "Le comité médical examine la situation du fonctionnaire en congé de maladie.",
    }
    assert is_topic_relevant_source(question, source) is True
def test_ordinary_sick_leave_question_rejects_citis_articles():
    question = (
        "Je suis fonctionnaire territorial titulaire. Quelles sont les règles "
        "du congé de maladie ordinaire, notamment le jour de carence et le maintien de rémunération ?"
    )
    citis_article = {
        "title": "Code général de la fonction publique — article L822-21",
        "article": "L822-21",
        "text": (
            "Le fonctionnaire en activité a droit à un congé pour invalidité "
            "temporaire imputable au service lorsque son incapacité temporaire "
            "de travail est consécutive à un accident reconnu imputable au service."
        ),
    }
    assert "ORDINARY_SICK_LEAVE" in _matched_topic_families(question)
    assert "CITIS" in _matched_topic_families(citis_article["text"])
    assert is_topic_relevant_source(question, citis_article) is False


def test_citis_question_keeps_citis_articles():
    question = "Quelles sont les conditions du congé pour invalidité temporaire imputable au service (CITIS) ?"
    source = {
        "title": "Code général de la fonction publique — article L822-21",
        "article": "L822-21",
        "text": (
            "Le fonctionnaire a droit à un congé pour invalidité temporaire "
            "imputable au service après un accident reconnu imputable au service."
        ),
    }
    assert is_topic_relevant_source(question, source) is True


def test_ordinary_sick_leave_question_keeps_ordinary_sick_leave_source():
    question = "Quelles sont les règles du congé de maladie ordinaire et du jour de carence ?"
    source = {
        "title": "Congé de maladie du fonctionnaire",
        "text": (
            "Le fonctionnaire peut bénéficier d'un congé de maladie ordinaire. "
            "Le jour de carence s'applique selon les conditions prévues par les textes."
        ),
    }
    assert is_topic_relevant_source(question, source) is True


def test_bereavement_question_rejects_unrelated_cgfp_and_generic_leave_hits():
    question = (
        "Un agent demande une autorisation d'absence après le décès de son grand-père. "
        "La direction peut-elle exiger le livret de famille ?"
    )
    unrelated = [
        {
            "title": "Code général de la fonction publique — article L542-8",
            "article": "L542-8",
            "text": "Dispositions relatives aux emplois fonctionnels et à leur cessation.",
        },
        {
            "title": "Congé de longue durée",
            "text": "Dispositions relatives au congé de longue durée pour raison de santé.",
        },
        {
            "title": "Autorisation spéciale d'absence syndicales",
            "text": "Dispositions relatives aux absences liées à l'exercice du droit syndical.",
        },
    ]
    relevant = {
        "title": "Autorisation d'absence pour décès d'un membre de la famille",
        "text": (
            "Les autorisations d'absence pour décès d'un proche et les justificatifs "
            "du lien familial doivent être examinés selon les dispositions applicables."
        ),
    }
    assert "FAMILY_BEREAVEMENT" in _matched_topic_families(question)
    assert all(is_topic_relevant_source(question, source) is False for source in unrelated)
    assert is_topic_relevant_source(question, relevant) is True


def test_union_assistance_question_rejects_unrelated_union_administration_sources():
    question = (
        "Un agent convoqué par sa hiérarchie peut-il bénéficier d'un accompagnement syndical ?"
    )
    unrelated = {
        "title": "Autorisations spéciales d'absence syndicales",
        "text": "Modalités des absences accordées pour congrès et réunions statutaires.",
    }
    relevant = {
        "title": "Garanties disciplinaires et assistance du fonctionnaire",
        "text": (
            "Dans la procédure disciplinaire, le fonctionnaire peut être assisté "
            "par un défenseur de son choix."
        ),
    }
    assert "UNION_ASSISTANCE" in _matched_topic_families(question)
    assert is_topic_relevant_source(question, unrelated) is False
    assert is_topic_relevant_source(question, relevant) is True


def test_aggression_by_service_user_keeps_functional_protection_but_rejects_disciplinary_report_rules():
    question = (
        "Un agent a été agressé par un usager et son chef refuse de déclarer l'incident. "
        "Quels sont ses droits ?"
    )
    relevant = {
        "title": "Protection fonctionnelle des agents victimes d'une agression",
        "text": "La protection fonctionnelle concerne les agents victimes de violences ou d'agressions.",
    }
    unrelated = {
        "title": "Rapport disciplinaire",
        "text": "Le rapport établi par le supérieur hiérarchique peut être versé au dossier disciplinaire.",
    }
    assert "AGGRESSION_AGENT_PROTECTION" in _matched_topic_families(question)
    assert is_topic_relevant_source(question, relevant) is True
    assert is_topic_relevant_source(question, unrelated) is False


def test_aggression_question_keeps_a_functional_protection_source_without_aggression_wording():
    question = "Un agent a été agressé par un usager. Peut-il demander la protection fonctionnelle ?"
    source = {
        "title": "Protection fonctionnelle des agents publics",
        "text": "L'administration protège l'agent contre les attaques subies dans l'exercice des fonctions.",
    }
    assert is_topic_relevant_source(question, source) is True


def test_union_assistance_question_keeps_disciplinary_defence_source_as_related_context():
    question = "Un agent convoqué par sa hiérarchie peut-il bénéficier d'un accompagnement syndical ?"
    source = {
        "title": "Droits de la défense dans la procédure disciplinaire",
        "text": "Le fonctionnaire peut consulter son dossier et être assisté par un défenseur.",
    }
    assert is_topic_relevant_source(question, source) is True


def test_bereavement_topic_does_not_match_generic_grandparent_family_provisions():
    question = "Après le décès de son grand-père, l'agent demande une autorisation d'absence."
    unrelated = {
        "title": "Aide familiale aux ascendants et grands-parents",
        "text": "Dispositions relatives à l'accompagnement familial des personnes âgées.",
    }
    assert "FAMILY_BEREAVEMENT" in _matched_topic_families(question)
    assert is_topic_relevant_source(question, unrelated) is False


def test_union_assistance_topic_does_not_match_generic_union_representative_rights():
    question = (
        "Un agent convoqué par sa hiérarchie peut-il bénéficier d'un accompagnement syndical ?"
    )
    unrelated = {
        "title": "Droits du représentant syndical",
        "text": "Crédit de temps syndical et autorisations d'absence pour les congrès.",
    }
    assert "UNION_ASSISTANCE" in _matched_topic_families(question)
    assert is_topic_relevant_source(question, unrelated) is False

def test_nbi_question_rejects_unrelated_remuneration_and_national_police_sources():
    question = "C est quoi une NBI et comment son montant est-il calculé ?"
    unrelated = [
        {
            "title": "Code général de la fonction publique — article D444-9",
            "article": "D444-9",
            "text": "Pour le calcul de l'indemnité, sont prises en compte la rémunération globale antérieure et la rémunération résultant de l'intégration.",
        },
        {
            "title": "Code général de la fonction publique — article R213-11",
            "article": "R213-11",
            "text": "Le coût de la rémunération nette d'un agent territorial est déterminé selon un indice médian.",
        },
        {
            "title": "Arrêté fixant la liste des emplois éligibles à la NBI dans la gendarmerie nationale",
            "text": "Nouvelle bonification indiciaire attribuée aux personnels de la gendarmerie nationale.",
        },
    ]
    relevant = {
        "title": "Décret n° 2006-779 du 3 juillet 2006 portant attribution de la NBI à certains personnels de la fonction publique territoriale",
        "text": "Une nouvelle bonification indiciaire est versée aux fonctionnaires territoriaux exerçant les fonctions figurant en annexe.",
    }

    assert "NBI" in _matched_topic_families(question)
    assert all(is_topic_relevant_source(question, source) is False for source in unrelated)
    assert is_topic_relevant_source(question, relevant) is True


def test_nbi_queries_target_fpt_cgfp_and_implementing_decrees_only():
    question = "C est quoi une NBI et comment son montant est-il calculé ?"
    assert _build_targeted_cgfp_article_queries(question, "FPT") == [
        "article L712-12", "article L712-13",
    ]
    assert _build_targeted_cgfp_article_queries(question, "FPE") == []
    queries = _build_targeted_regulatory_queries(question, "FPT")
    assert any("93-863" in query for query in queries)
    assert any("2006-779" in query for query in queries)
    assert any("2006-780" in query for query in queries)
    assert _build_targeted_regulatory_queries(question, "FPE") == []
    assert _build_targeted_regulatory_queries(question, "FPH") == []


def test_health_regulatory_queries_stay_with_the_selected_versant():
    fpe = _build_targeted_regulatory_queries(
        "Un agent demande un temps partiel thérapeutique après un accident de service.",
        "FPE",
    )
    assert any("86-442" in query and "23-1" in query for query in fpe)
    assert any("86-442" in query and "47-1" in query for query in fpe)
    assert not any("87-602" in query or "88-386" in query for query in fpe)

    fph = _build_targeted_regulatory_queries(
        "Un agent demande un temps partiel thérapeutique après un accident de service.",
        "FPH",
    )
    assert any("88-386" in query and "13-1" in query for query in fph)
    assert any("88-386" in query and "35-2" in query for query in fph)
    assert not any("87-602" in query or "86-442" in query for query in fph)

def test_medico_social_ihts_queries_retrieve_specific_20_hour_equivalence_sources():
    queries = _build_targeted_regulatory_queries(
        "Je suis cadre de santé paramédical territorial. Quel est mon contingent mensuel d'IHTS ?",
        "FPT",
    )
    joined = " ".join(queries).casefold()
    assert any("91-875" in query and "annexes 1 et 2" in query for query in queries)
    assert any("98-1057" in query for query in queries)
    assert any("2002-598" in query and "20 heures" in query for query in queries)
    assert any("arrêté du 25 avril 2002" in query for query in queries)
    assert "20 heures" in joined


def test_medico_social_ihts_detection_handles_official_territorial_cadre_wording():
    questions = [
        "Je suis cadre territorial de santé paramédical, quel contingent d'IHTS ?",
        "Je suis puéricultrice territoriale, quelles règles d'heures supplémentaires ?",
    ]
    for question in questions:
        queries = _build_targeted_regulatory_queries(question, "FPT")
        assert any("2002-598" in query for query in queries)
