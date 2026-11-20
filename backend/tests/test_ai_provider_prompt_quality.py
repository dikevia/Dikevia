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
