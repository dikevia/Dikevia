from app.ai_provider import SYSTEM_PROMPT


def test_prompt_prioritizes_the_current_question_over_lexical_source_matches():
    assert "PRIORITÉ ABSOLUE À LA QUESTION" in SYSTEM_PROMPT
    assert "un mot commun" in SYSTEM_PROMPT
    assert "N'utilise pas les anciennes questions" in SYSTEM_PROMPT


def test_prompt_requires_a_direct_plain_language_answer_before_references():
    assert "RÉPONSE AVANT RÉFÉRENCES" in SYSTEM_PROMPT
    assert "ne commence jamais par le numéro d'un article" in SYSTEM_PROMPT
    assert "conséquence pratique pour l'agent" in SYSTEM_PROMPT


def test_prompt_requires_a_final_question_answer_coherence_check():
    assert "CONTRÔLE FINAL OBLIGATOIRE" in SYSTEM_PROMPT
    assert "Si les sources pertinentes ne permettent aucune réponse utile" in SYSTEM_PROMPT



def test_prompt_requires_the_first_claim_to_be_the_direct_answer():
    assert "ORDRE DES AFFIRMATIONS" in SYSTEM_PROMPT
    assert "le premier élément de claims doit être la réponse directe" in SYSTEM_PROMPT


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
