from src.detectors.rule_based_detector import RuleBasedDetector


def test_detects_fio_dob_address_bundle_high_risk():
    text = (
        "ФИО: Иванов Иван Иванович, дата рождения 12.03.1988, "
        "адрес регистрации: г. Москва, ул. Ленина, д. 1, кв. 7"
    )
    result = RuleBasedDetector().detect(text)
    assessment = result.document_assessment

    assert assessment is not None
    assert assessment["has_personal_data"] is True
    assert assessment["overall_risk_score"] >= 60
    assert "BASIC_PERSONAL_DATA" in assessment["detected_categories"]
    assert "CONTACT_DATA" in assessment["detected_categories"]


def test_special_category_detection():
    text = "Пациент: Петров Петр Петрович. Диагноз: хронический бронхит."
    result = RuleBasedDetector().detect(text)
    assessment = result.document_assessment

    assert assessment is not None
    assert "special" in assessment["legal_buckets_present"]
    assert assessment["overall_risk_score"] >= 35


def test_biometric_detection():
    text = "В системе хранится face embedding и voiceprint пользователя."
    result = RuleBasedDetector().detect(text)
    assessment = result.document_assessment

    assert assessment is not None
    assert "biometric" in assessment["legal_buckets_present"]
    assert any(e.entity_type == "face_image_context" for e in result.entities)


def test_noise_numbers_not_personal_data():
    text = "Номер договора 1234567890, сумма 500000, счетчик 889911."
    result = RuleBasedDetector().detect(text)
    assessment = result.document_assessment

    assert assessment is not None
    assert assessment["overall_risk_score"] < 20
    assert assessment["has_personal_data"] is False


def test_ocr_noise_and_spaces_normalized_for_snils():
    text = "С Н И Л С : 112  233  445   95"
    result = RuleBasedDetector().detect(text)

    assert any(e.entity_type == "snils" for e in result.entities)
    assert any("***" in e.value for e in result.entities if e.entity_type == "snils")