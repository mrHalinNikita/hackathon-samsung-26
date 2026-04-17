import unittest

from src.detectors.base import DetectionResult, PDEntity
from src.detectors.config import DetectionConfig
from src.detectors.ensemble_detector import EnsembleDetector


class StubRegexDetector:
    def __init__(self, entities=None):
        self.entities = entities or []
        self.calls = 0

    def detect(self, text: str) -> DetectionResult:
        self.calls += 1
        return DetectionResult(entities=self.entities, categories={e.entity_type: 1 for e in self.entities})


class StubNLPDetector:
    def __init__(self):
        self.calls = 0

    def detect(self, text: str) -> DetectionResult:
        self.calls += 1
        return DetectionResult(
            entities=[
                PDEntity(
                    entity_type="person_name",
                    value="Иван Иванов",
                    confidence=0.8,
                    start_pos=0,
                    end_pos=11,
                    source="nlp",
                )
            ],
            categories={"person_name": 1},
        )


class NLPPrefilterTests(unittest.TestCase):
    def test_nlp_skipped_for_non_suspicious_text(self):
        config = DetectionConfig(
            NLP_RUN_MODE="suspicious_only",
            NLP_PREFILTER_MIN_REGEX_ENTITIES=1,
            NLP_PREFILTER_MIN_TEXT_LENGTH=50,
            NLP_PREFILTER_KEYWORDS=["паспорт"],
        )
        detector = EnsembleDetector(config)
        detector._detectors["regex"] = StubRegexDetector(entities=[])
        detector._detectors["nlp"] = StubNLPDetector()

        text = "Просто обычный текст без персональных маркеров." * 2
        result = detector.detect(text)

        self.assertIn("nlp skipped by suspicious prefilter", result.warnings)
        self.assertEqual(detector._detectors["nlp"].calls, 0)

    def test_nlp_runs_when_regex_found_entities(self):
        config = DetectionConfig(
            NLP_RUN_MODE="suspicious_only",
            NLP_PREFILTER_MIN_REGEX_ENTITIES=1,
        )
        detector = EnsembleDetector(config)
        detector._detectors["regex"] = StubRegexDetector(
            entities=[
                PDEntity(
                    entity_type="email",
                    value="demo@test.com",
                    confidence=0.9,
                    start_pos=10,
                    end_pos=23,
                    source="regex",
                )
            ]
        )
        detector._detectors["nlp"] = StubNLPDetector()

        detector.detect("Контакты: demo@test.com и Иван Иванов.")
        self.assertEqual(detector._detectors["nlp"].calls, 1)

    def test_nlp_runs_when_keyword_present(self):
        config = DetectionConfig(
            NLP_RUN_MODE="suspicious_only",
            NLP_PREFILTER_MIN_REGEX_ENTITIES=1,
            NLP_PREFILTER_MIN_TEXT_LENGTH=10,
            NLP_PREFILTER_KEYWORDS=["персональные данные"],
        )
        detector = EnsembleDetector(config)
        detector._detectors["regex"] = StubRegexDetector(entities=[])
        detector._detectors["nlp"] = StubNLPDetector()

        detector.detect("В документе могут содержаться персональные данные сотрудников.")
        self.assertEqual(detector._detectors["nlp"].calls, 1)


if __name__ == "__main__":
    unittest.main()