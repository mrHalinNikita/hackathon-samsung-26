from src.detectors.base import DetectionResult, classify_protection_level


def test_payment_data_always_sets_uz2():
    result = DetectionResult(categories={"credit_card": 1, "email": 1})

    classify_protection_level(result)

    assert result.protection_level == "УЗ-2"


def test_regular_small_volume_sets_uz4():
    result = DetectionResult(categories={"email": 3, "phone": 2})

    classify_protection_level(result)

    assert result.protection_level == "УЗ-4"


def test_no_personal_data_defaults_to_uz4():
    result = DetectionResult(categories={})

    classify_protection_level(result)

    assert result.protection_level == "УЗ-0"