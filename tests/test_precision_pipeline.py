from src.detectors.rule_based_detector import RuleBasedDetector


def test_hard_negative_policy_text():
    text = "Политика обработки ПДн: укажите <ФИО> и <дата рождения> в шаблоне"
    result = RuleBasedDetector().detect(text)
    assert result.document_assessment is not None
    assert result.document_assessment["has_personal_data"] is False


def test_hard_positive_inn_with_context_and_checksum():
    text = "ИНН: 500100732259"
    result = RuleBasedDetector().detect(text)
    assert result.document_assessment is not None
    assert result.document_assessment["has_personal_data"] is True


def test_hard_negative_footer_contacts_only():
    text = "support@example.com\n+7 (800) 555-35-35"
    result = RuleBasedDetector().detect(text)
    assert result.document_assessment is not None
    assert result.document_assessment["has_personal_data"] is False
