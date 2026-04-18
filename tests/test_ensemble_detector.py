from src.detectors import EnsembleDetector
from src.detectors.base import DetectionResult
from src.detectors.config import DetectionConfig


class DummyNLP:
    def __init__(self):
        self.called = 0

    def detect(self, text: str) -> DetectionResult:
        self.called += 1
        return DetectionResult()


def test_nlp_prefilter_skips_short_non_suspicious_text():
    config = DetectionConfig(
        NLP_ENABLED=True,
        RULE_ENGINE_ENABLED=False,
        NLP_RUN_MODE="suspicious_only",
        NLP_PREFILTER_MIN_TEXT_LENGTH=200,
    )
    detector = EnsembleDetector(config)
    dummy = DummyNLP()
    detector._detectors["nlp"] = dummy

    result = detector.detect("просто короткий технический лог без персональных данных")

    assert dummy.called == 0
    assert "nlp skipped by suspicious prefilter" in result.warnings


def test_nlp_prefilter_runs_on_keyword_match():
    config = DetectionConfig(
        NLP_ENABLED=True,
        RULE_ENGINE_ENABLED=False,
        NLP_RUN_MODE="suspicious_only",
        NLP_PREFILTER_MIN_TEXT_LENGTH=500,
        NLP_PREFILTER_KEYWORDS=["пациент"],
    )
    detector = EnsembleDetector(config)
    dummy = DummyNLP()
    detector._detectors["nlp"] = dummy

    detector.detect("пациент поступил в отделение")

    assert dummy.called == 1


def test_ensemble_returns_document_assessment_from_rule_engine():
    detector = EnsembleDetector(DetectionConfig(NLP_ENABLED=False, REGEX_ENABLED=False, RULE_ENGINE_ENABLED=True))
    result = detector.detect("ФИО: Иванов Иван Иванович дата рождения 01.01.1990")

    assert result.document_assessment is not None
    assert result.document_assessment["has_personal_data"] is True
    assert result.document_assessment["overall_risk_score"] >= 20