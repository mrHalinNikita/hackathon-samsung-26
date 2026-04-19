from src.detectors.rule_based_detector import RuleBasedDetector


def test_date_alone_not_positive():
    result = RuleBasedDetector().detect("Документ создан 12.03.2020")
    assessment = result.document_assessment
    assert assessment is not None
    assert assessment["has_personal_data"] is False


def test_fio_alone_not_positive():
    result = RuleBasedDetector().detect("Иванов Иван Иванович")
    assessment = result.document_assessment
    assert assessment is not None
    assert assessment["has_personal_data"] is False


def test_snils_requires_context_and_checksum():
    text = "СНИЛС: 112-233-445 95"
    result = RuleBasedDetector().detect(text)
    assessment = result.document_assessment
    assert assessment is not None
    assert assessment["has_personal_data"] is True
    assert any(e.entity_type == "snils" for e in result.entities)


def test_invalid_card_number_not_detected():
    text = "карта 4111 1111 1111 1112"
    result = RuleBasedDetector().detect(text)
    assert result.document_assessment is not None
    assert result.document_assessment["has_personal_data"] is False


def test_medium_signals_same_scope_are_positive():
    text = "ФИО: Иванов Иван Иванович | email: ivanov@gmail.com | тел: +7 999 111-22-33"
    result = RuleBasedDetector().detect(text)
    assessment = result.document_assessment
    assert assessment is not None
    assert assessment["has_personal_data"] is True
    assert assessment["hit_count"] >= 2
