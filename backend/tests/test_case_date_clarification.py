from app.orchestrator import classify_question_intent, question_needs_case_date


def test_general_information_question_does_not_require_facts_date():
    assert question_needs_case_date("Quels sont mes droits aux congés annuels ?") is False
    assert question_needs_case_date("Comment fonctionne le télétravail dans la FPT ?") is False


def test_concrete_personal_dispute_requests_facts_date():
    assert question_needs_case_date("On ne me paie pas mes heures supplémentaires.") is True
    assert question_needs_case_date("J'ai été sanctionné par ma collectivité.") is True
    assert question_needs_case_date("Dans mon cas, puis-je contester cette décision ?") is True


def test_general_question_about_employer_powers_is_not_automatically_case_specific():
    assert question_needs_case_date("Mon employeur peut-il refuser le télétravail ?") is False

def test_personal_nonpayment_dispute_requests_facts_date():
    assert question_needs_case_date("Mon employeur refuse de me payer mes heures supplémentaires.") is True
    assert question_needs_case_date("Je n'ai pas été payé depuis le mois dernier.") is True


def test_personal_decision_wording_requests_facts_date():
    assert question_needs_case_date("Mon congé maladie a été refusé par la collectivité.") is True
    assert question_needs_case_date("Ma demande de télétravail a été rejetée.") is True
    assert question_needs_case_date("J'ai reçu une décision de refus de ma rémunération.") is True


def test_hypothetical_or_general_refusal_questions_do_not_request_facts_date():
    assert question_needs_case_date("Un employeur peut-il refuser un congé maladie ?") is False
    assert question_needs_case_date("Dans quels cas une demande de télétravail peut-elle être rejetée ?") is False


def test_intent_classifier_distinguishes_personal_events_from_general_rules():
    assert classify_question_intent("Mon employeur peut-il refuser le télétravail ?") == "GENERAL_INFORMATION"
    assert classify_question_intent("Un employeur peut-il refuser un congé maladie ?") == "GENERAL_INFORMATION"
    assert classify_question_intent("Ma demande de télétravail a été rejetée.") == "PERSONAL_CASE"
    assert classify_question_intent("Mon congé maladie a été refusé par la collectivité.") == "PERSONAL_CASE"


def test_general_first_person_rights_question_does_not_trigger_case_date():
    assert question_needs_case_date("Ai-je droit aux congés annuels quand je suis contractuel ?") is False
    assert question_needs_case_date("Quels sont mes droits si mon employeur refuse le télétravail ?") is False
