from app.ai_provider import SYSTEM_PROMPT


def test_prompt_prioritizes_the_current_question_over_lexical_source_matches():
    assert "PRIORITÉ ABSOLUE À LA QUESTION" in SYSTEM_PROMPT
    assert "un mot commun" in SYSTEM_PROMPT
    assert "N'utilise pas les anciennes questions" in SYSTEM_PROMPT


def test_prompt_requires_understanding_the_request_and_presenting_relevant_texts():
    assert "MÉTHODE DE COMPRÉHENSION ET DE RESTITUTION DES SOURCES" in SYSTEM_PROMPT
    assert "comprendre exactement la demande actuelle" in SYSTEM_PROMPT
    assert "Présente d'abord les références et les dispositions" in SYSTEM_PROMPT
    assert "strictement fidèle au texte ou à la décision citée" in SYSTEM_PROMPT


def test_prompt_forbids_personal_legal_opinions_and_individual_case_judgments():
    assert "Ne donne aucun avis personnel" in SYSTEM_PROMPT
    assert "Ne transforme pas la restitution des textes en consultation juridique" in SYSTEM_PROMPT
    assert "aucune appréciation sur le comportement de l'employeur" in SYSTEM_PROMPT



def test_prompt_claims_must_summarize_sources_without_recommendations():
    assert "restituer une disposition ou un apport jurisprudentiel précis" in SYSTEM_PROMPT
    assert "sans avis, diagnostic de la situation individuelle ni recommandation" in SYSTEM_PROMPT


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

def test_prompt_distinguishes_titular_dismissal_from_abolition_of_post():
    assert "Ne présente jamais la suppression d'un emploi comme entraînant automatiquement la perte de la qualité de fonctionnaire" in SYSTEM_PROMPT
    assert "révocation disciplinaire et licenciement pour insuffisance professionnelle" in SYSTEM_PROMPT



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
    assert "scope_status vaut OUT_OF_SCOPE_FPE" in SYSTEM_PROMPT
    assert "EMPLOYMENT_STATUS_AMBIGUOUS" in SYSTEM_PROMPT
    assert "un CDD ou un CDI mentionné seul ne suffit pas" in SYSTEM_PROMPT


def test_prompt_restricts_later_case_law_to_interpretative_use_for_historical_claims():
    assert "une décision postérieure ne peut jamais être la source directe ou unique" in SYSTEM_PROMPT
    assert "rattache toute conclusion à un texte ou à une décision antérieure" in SYSTEM_PROMPT
