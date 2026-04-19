from typing import Literal

from pydantic import BaseModel


class DetectionConfig(BaseModel):
    PROFILE: Literal["strict", "balanced"] = "strict"

    # Pipeline toggles
    RULE_ENGINE_ENABLED: bool = True
    REGEX_ENABLED: bool = False
    NLP_ENABLED: bool = False

    # Context + aggregation
    CONTEXT_WINDOW: int = 80
    LOCAL_SCOPE_WINDOW: int = 260
    MIN_MEDIUM_PER_SCOPE: int = 2

    # Structured heuristics
    STRUCTURED_MIN_ROWS: int = 3
    STRUCTURED_VALIDATOR_PASS_RATE: float = 0.6

    # Volume thresholds for УЗ
    SMALL_VOLUME_THRESHOLD: int = 10
    LARGE_VOLUME_THRESHOLD: int = 100

    # Optional compatibility knobs for legacy detectors
    REGEX_MIN_CONFIDENCE: float = 0.75
    NLP_MIN_CONFIDENCE: float = 0.7
    NLP_ENTITY_TYPES: list[str] = ["PER", "ORG", "LOC", "DATE"]
    NLP_RUN_MODE: Literal["always", "suspicious_only"] = "suspicious_only"
    NLP_PREFILTER_MIN_REGEX_ENTITIES: int = 1
    NLP_PREFILTER_MIN_TEXT_LENGTH: int = 120
    NLP_PREFILTER_KEYWORDS: list[str] = [
        "фио",
        "дата рождения",
        "паспорт",
        "снилс",
        "инн",
        "адрес",
        "тел",
        "email",
    ]
    MAX_TEXT_LENGTH_FOR_NLP: int = 50000
    ENSEMBLE_STRATEGY: Literal["max", "weighted", "voting"] = "max"
    ENSEMBLE_WEIGHTS: dict[str, float] = {"regex": 0.5, "nlp": 0.3, "rule": 0.2}
    FINAL_MIN_CONFIDENCE: float = 0.5

    # Reporting limits
    MAX_ENTITIES_PER_TYPE: int = 100

    # Diagnostics
    DIAGNOSTIC_MODE: bool = False


STRICT_CONFIG = DetectionConfig()
BALANCED_CONFIG = DetectionConfig(
    PROFILE="balanced",
    REGEX_ENABLED=False,
    NLP_ENABLED=False,
    MIN_MEDIUM_PER_SCOPE=2,
    STRUCTURED_VALIDATOR_PASS_RATE=0.5,
)

default_config = STRICT_CONFIG


BIOMETRIC_CATEGORIES = {"fingerprint", "iris", "voice_sample", "face_geometry", "dna"}

SPECIAL_CATEGORIES = {
    "health",
    "religion",
    "political_views",
    "race",
    "nationality",
}

PAYMENT_CATEGORIES = {
    "credit_card",
    "bank_account",
    "payment_card_number",
    "cvv",
}

GOVERNMENT_IDENTIFIERS = {
    "passport",
    "snils",
    "inn",
    "driver_license",
    "military_id",
}

REGULAR_PDN = {
    "person_name",
    "email",
    "phone",
    "address",
    "date_of_birth",
    "organization",
    "location",
}
