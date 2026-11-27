from app.ai_provider import SYSTEM_PROMPT, _system_prompt_for_versant


def test_prompt_prioritizes_understanding_the_current_request_over_lexical_matches():
    assert "MÉTHODE DE COMPRÉHENSION ET DE RESTITUTION DES SOURCES" in SYSTEM_PROMPT
    assert "comprendre exactement la demande actuelle" in SYSTEM_PROMPT
    assert "Écarte les sources qui ne répondent pas au sujet précis" in SYSTEM_PROMPT
    assert "Tu ne rends pas de décision opposable" in SYSTEM_PROMPT


def test_prompt_requires_understanding_the_request_and_presenting_relevant_texts():
    assert "MÉTHODE DE COMPRÉHENSION ET DE RESTITUTION DES SOURCES" in SYSTEM_PROMPT
    assert "comprendre exactement la demande actuelle" in SYSTEM_PROMPT
    assert "Présente d'abord les références et les dispositions" in SYSTEM_PROMPT
    assert "strictement fidèle au texte ou à la décision citée" in SYSTEM_PROMPT


def test_prompt_allows_cautious_case_analysis_without_overstating_legal_certainty():
    assert "apprécier prudemment la conformité apparente" in SYSTEM_PROMPT
    assert "les faits retenus, les incertitudes et les limites" in SYSTEM_PROMPT
    assert "les conséquences juridiques possibles" in SYSTEM_PROMPT
    assert "les voies de recours documentées" in SYSTEM_PROMPT

def test_prompt_claims_can_explain_legal_effect_and_apply_rules_to_declared_facts():
    assert "interprétation fidèle" in SYSTEM_PROMPT
    assert "application prudente aux faits déclarés" in SYSTEM_PROMPT
    assert "incidence possible sur la situation" in SYSTEM_PROMPT
    assert "signaler les éléments manquants" in SYSTEM_PROMPT

def test_prompt_enforces_the_territorial_public_service_legal_hierarchy():
    assert "RÈGLES DE QUALIFICATION JURIDIQUE FPT" in SYSTEM_PROMPT
    assert "Le Code du travail n'est jamais le régime de droit commun des agents territoriaux" in SYSTEM_PROMPT
    assert "ne transpose jamais automatiquement le droit du secteur privé" in SYSTEM_PROMPT
    assert "renvoi législatif ou réglementaire vérifié" in SYSTEM_PROMPT
    assert "fonctionnaire titulaire, stagiaire ou agent contractuel" in SYSTEM_PROMPT


def test_prompt_requires_local_deliberation_when_national_text_refers_to_it():
    assert "acte local applicable et validé" in SYSTEM_PROMPT
    assert "ne conclus pas sur le droit individuel, le montant ou les modalités" in SYSTEM_PROMPT


def test_prompt_prevents_current_application_of_repealed_fpt_union_decree():
    assert "décret n° 85-397 du 3 avril 1985" in SYSTEM_PROMPT
    assert "abrogé à compter du 1er février 2025" in SYSTEM_PROMPT
    assert "article 29 du décret n° 2024-1038" in SYSTEM_PROMPT
    assert "Ne présume pas que les anciennes dispositions ont toutes été reprises à l'identique" in SYSTEM_PROMPT


def test_prompt_explains_administrative_open_data_publication_codes():
    from app.ai_provider import SYSTEM_PROMPT
    assert "code de publication A" in SYSTEM_PROMPT
    assert "jamais comme une hiérarchie normative" in SYSTEM_PROMPT
    assert "Une décision C, D ou Z peut éclairer" in SYSTEM_PROMPT


def test_prompt_warns_that_case_law_excerpts_may_be_partial():
    from app.ai_provider import SYSTEM_PROMPT
    assert "Les extraits d'une décision peuvent être partiels" in SYSTEM_PROMPT
    assert "n'infère pas le dispositif" in SYSTEM_PROMPT

def test_prompt_documents_titular_termination_mechanisms_without_judging_individual_cases():
    assert "Pour une question demandant si une collectivité peut mettre fin aux fonctions d'un titulaire" in SYSTEM_PROMPT
    assert "Présente leurs motifs, conditions et procédures tels qu'ils figurent dans les sources" in SYSTEM_PROMPT
    assert "sans apprécier le cas individuel" in SYSTEM_PROMPT



def test_prompt_locks_the_assistant_to_fpt_and_blocks_cross_versant_transposition():
    assert "exclusivement la fonction publique territoriale (FPT)" in SYSTEM_PROMPT
    assert "ne transpose jamais automatiquement" in SYSTEM_PROMPT
    assert "sort du périmètre de Dikévia" in SYSTEM_PROMPT
    assert "s'applique aussi aux agents territoriaux" in SYSTEM_PROMPT



def test_prompt_uses_the_whole_cgfp_index_as_discovery_and_requires_live_article_verification():
    assert "référentiel article par article du snapshot CGFP" in SYSTEM_PROMPT
    assert "explorer l'ensemble du code" in SYSTEM_PROMPT
    assert "vérifie ensuite sa rédaction intégrale sur Légifrance" in SYSTEM_PROMPT
    assert "Le classement lexical ou conceptuel" in SYSTEM_PROMPT
    assert "ne suffit pas toujours à résoudre seul la question" in SYSTEM_PROMPT


def test_prompt_obeys_structured_scope_and_ambiguous_contract_status():
    assert "scope_status signale la présence d'indices lexicaux" in SYSTEM_PROMPT
    assert "ne déduis jamais le versant personnel d'une simple mention comparative ou d'un tiers" in SYSTEM_PROMPT
    assert "EMPLOYMENT_STATUS_AMBIGUOUS" in SYSTEM_PROMPT
    assert "un CDD ou un CDI mentionné seul ne suffit pas" in SYSTEM_PROMPT


def test_prompt_restricts_later_case_law_to_interpretative_use_for_historical_claims():
    assert "une décision postérieure ne peut jamais être la source directe ou unique" in SYSTEM_PROMPT
    assert "rattache toute conclusion à un texte ou à une décision antérieure" in SYSTEM_PROMPT


def test_personal_case_without_date_allows_current_law_analysis_with_explicit_limits():
    assert "PERSONAL_CASE_WITHOUT_FACTS_DATE" in SYSTEM_PROMPT
    assert "confronte prudemment les faits déclarés aux conditions" in SYSTEM_PROMPT
    assert "ne présente jamais un droit comme acquis" in SYSTEM_PROMPT

def test_prompt_requires_coverage_of_each_retrieval_axis():
    assert "axes_recherche_documentaire" in SYSTEM_PROMPT
    assert "n'en omets aucun silencieusement" in SYSTEM_PROMPT
    assert "indique-le dans uncovered_axes" in SYSTEM_PROMPT
    assert "conserve néanmoins les affirmations indépendantes" in SYSTEM_PROMPT

def test_prompt_distinguishes_current_general_information_from_undated_personal_cases():
    assert "GENERAL_CURRENT_LAW_WITHOUT_FACTS_DATE" in SYSTEM_PROMPT
    assert "PERSONAL_CASE_WITHOUT_FACTS_DATE" in SYSTEM_PROMPT
    assert "réponds à la question générale à partir des règles actuelles documentées" in SYSTEM_PROMPT
    assert "confronte prudemment les faits déclarés aux conditions des règles actuelles documentées" in SYSTEM_PROMPT
    assert "Ne bloque pas la recherche au seul motif que la date des faits manque" in SYSTEM_PROMPT
    assert "une vérification historique sera nécessaire uniquement si la date peut modifier les dispositions applicables" in SYSTEM_PROMPT
    assert "Ne demande pas automatiquement la date des faits" in SYSTEM_PROMPT

def test_prompt_never_assumes_generic_public_service_sources_apply_to_fpt():
    assert "GENERAL_PUBLIC_SERVICE" in SYSTEM_PROMPT
    assert "simple contexte de recherche" in SYSTEM_PROMPT
    assert "ne l'utilise jamais pour soutenir une affirmation applicable à un agent territorial" in SYSTEM_PROMPT
    assert "COMMON_PUBLIC_SERVICE" in SYSTEM_PROMPT
    assert "établit explicitement qu'il vise les trois versants" in SYSTEM_PROMPT




def test_fpt_prompt_requires_pedagogical_explanations_not_a_bare_list_of_references():
    from app.ai_provider import SYSTEM_PROMPT

    assert "explication pédagogique autonome" in SYSTEM_PROMPT
    assert "termes juridiques indispensables" in SYSTEM_PROMPT
    assert "Évite de répéter une règle" in SYSTEM_PROMPT
    assert "liste de références sans explication" in SYSTEM_PROMPT


def test_prompt_requires_each_claim_to_be_bound_to_an_exact_research_axis():
    assert '"axis": "valeur exacte d\'un axe de axes_recherche_documentaire"' in SYSTEM_PROMPT
    assert '"uncovered_axes": []' in SYSTEM_PROMPT
    assert "Aucun axe ne doit être omis" in SYSTEM_PROMPT



def test_entailment_prompt_checks_legal_rule_and_application_to_user_facts():
    from app.ai_provider import ENTAILMENT_SYSTEM_PROMPT

    assert "le noyau juridique de la proposition" in ENTAILMENT_SYSTEM_PROMPT
    assert "faits explicitement décrits dans la question actuelle" in ENTAILMENT_SYSTEM_PROMPT
    assert "N'exige pas que les faits de l'utilisateur figurent dans le texte juridique" in ENTAILMENT_SYSTEM_PROMPT
    assert "Lorsqu'un axe de recherche est fourni" in ENTAILMENT_SYSTEM_PROMPT


def test_prompt_allows_single_topic_questions_without_synthetic_axes():
    assert "Lorsque la liste est vide, mets axis à une chaîne vide" in SYSTEM_PROMPT


def test_ai_analysis_prompt_changes_with_the_selected_public_service():
    from app.ai_provider import _system_prompt_for_versant

    fpt = _system_prompt_for_versant("FPT")
    fpe = _system_prompt_for_versant("FPE")
    fph = _system_prompt_for_versant("FPH")
    assert "exclusivement FPE" in fpe
    assert "exclusivement FPH" in fph
    assert "fonction publique de l'État" in fpe
    assert "fonction publique hospitalière" in fph
    assert "RÈGLES DE QUALIFICATION JURIDIQUE FPT" not in fpe
    assert "RÈGLES DE QUALIFICATION JURIDIQUE FPT" not in fph
    assert "RÈGLES DE QUALIFICATION JURIDIQUE FPT" in fpt


def test_non_fpt_prompt_requires_explicit_scope_and_blocks_context_only_sources():
    from app.ai_provider import _system_prompt_for_versant, ENTAILMENT_SYSTEM_PROMPT

    prompt = _system_prompt_for_versant("FPH")
    assert "scope_status signale la présence d'indices lexicaux" in prompt
    assert "ne déduis jamais le versant personnel d'une simple mention comparative ou d'un tiers" in prompt
    assert "GENERAL_PUBLIC_SERVICE" in prompt
    assert "portée commune" in prompt
    assert "la situation de la personne dont les droits sont demandés" in prompt
    assert "une mention comparative ou une question portant sur un tiers ne suffit pas" in prompt
    assert "versant_selectionne" in ENTAILMENT_SYSTEM_PROMPT
    assert "Une source propre à un autre versant ne peut pas soutenir une affirmation" in ENTAILMENT_SYSTEM_PROMPT



def test_non_fpt_prompts_preserve_the_same_structured_evidence_contract():
    from app.ai_provider import _system_prompt_for_versant

    for versant in ("FPE", "FPH"):
        prompt = _system_prompt_for_versant(versant)
        assert "FORMAT DE SORTIE OBLIGATOIRE — JSON STRICT" in prompt
        assert '"claims"' in prompt
        assert '"source_id"' in prompt
        assert '"axis"' in prompt
        assert '"quote"' in prompt
        assert '"uncovered_axes"' in prompt
        assert "MÉTHODE DE COMPRÉHENSION ET DE RESTITUTION" in prompt
        assert "chaque proposition juridique doit rester rattachée à un extrait précis" in prompt

def test_research_planner_distinguishes_the_user_from_comparative_or_third_party_mentions():
    import inspect
    from app.ai_provider import plan_legal_research

    prompt_source = inspect.getsource(plan_legal_research)
    assert "Une mention d'un autre versant dans une comparaison ou à propos d'un tiers" in prompt_source
    assert "distingue toujours le sujet de la question et la personne dont la situation est décrite" in prompt_source

def test_all_versants_allow_documented_application_and_options_without_overclaiming():
    for versant in ("FPT", "FPE", "FPH"):
        prompt = _system_prompt_for_versant(versant)
        assert "PERSONAL_CASE_WITHOUT_FACTS_DATE" in prompt
        assert "confronte prudemment les faits déclarés" in prompt
        assert "options documentées" in prompt
        assert "Ne demande pas automatiquement la date des faits" in prompt

def test_fpt_prompt_explains_procedures_as_options_and_preserves_agent_choice():
    assert "même si l'utilisateur n'a pas explicitement demandé" in SYSTEM_PROMPT
    assert "l'autorité compétente" in SYSTEM_PROMPT
    assert "présente les démarches et recours juridiquement possibles comme des options" in SYSTEM_PROMPT
    assert "ne prétends pas choisir à la place de l'agent" in SYSTEM_PROMPT

def test_fpe_and_fph_prompts_explain_procedures_as_documented_options():
    for versant in ("FPE", "FPH"):
        prompt = _system_prompt_for_versant(versant)
        assert "même sans demande explicite de démarches" in prompt
        assert "l'autorité compétente" in prompt
        assert "présente les voies possibles et leurs conditions comme des options" in prompt
