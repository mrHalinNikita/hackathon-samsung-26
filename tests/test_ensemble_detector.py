from src.detectors import EnsembleDetector
from src.detectors.base import DetectionResult
from src.detectors.config import DetectionConfig


class DummyNLP:
    def __init__(self):
        self.called = 0

    def detect(self, text: str) -> DetectionResult:
        self.called += 1
        return DetectionResult()


def test_strict_profile_uses_rule_engine_by_default():
    detector = EnsembleDetector(DetectionConfig())
    result = detector.detect("Иванов Иван Иванович")
    assert result.document_assessment is not None
    assert result.document_assessment["has_personal_data"] is False


def test_nlp_optional_when_enabled():
    config = DetectionConfig(NLP_ENABLED=True, RULE_ENGINE_ENABLED=False, NLP_RUN_MODE="always")
    detector = EnsembleDetector(config)
    dummy = DummyNLP()
    detector._detectors["nlp"] = dummy

    detector.detect("пациент поступил в отделение")

    assert dummy.called == 1


def test_ensemble_returns_document_assessment_from_rule_engine():
    detector = EnsembleDetector(DetectionConfig(NLP_ENABLED=False, REGEX_ENABLED=False, RULE_ENGINE_ENABLED=True))
    result = detector.detect("ФИО: Иванов Иван Иванович email: ivanov@gmail.com тел: +7 999 1112233")

    assert result.document_assessment is not None
    assert result.document_assessment["has_personal_data"] is True
