from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Literal
from src.detectors.config import (
    SMALL_VOLUME_THRESHOLD, LARGE_VOLUME_THRESHOLD,
    BIOMETRIC_CATEGORIES, SPECIAL_CATEGORIES, PAYMENT_CATEGORIES,
    GOVERNMENT_IDENTIFIERS, REGULAR_PDN
)


@dataclass(frozen=True)
class PDEntity:
    entity_type: str
    value: str
    confidence: float
    start_pos: Optional[int] = None
    end_pos: Optional[int] = None
    context: Optional[str] = None
    source: Literal["regex", "nlp", "fuzzy", "ensemble"] = "ensemble"
    metadata: dict = field(default_factory=dict)
    
    def __post_init__(self):
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be in [0, 1], got {self.confidence}")


class BaseDetector(ABC):

    @abstractmethod
    def detect(self, text: str) -> 'DetectionResult':
        pass
    
    @staticmethod
    def _normalize_entity_type(entity_type: str) -> str:
        mapping = {
            "PER": "person_name", "ORG": "organization", "LOC": "location", "DATE": "date",
            "passport": "passport", "snils": "snils", "inn_individual": "inn",
            "inn_legal": "inn", "phone_ru": "phone", "email": "email",
        }
        return mapping.get(entity_type, entity_type.lower())
    
    @staticmethod
    def _extract_context(text: str, start: int, end: int, window: int = 50) -> str:
        ctx_start = max(0, start - window)
        ctx_end = min(len(text), end + window)
        return text[ctx_start:ctx_end].strip()


@dataclass
class DetectionResult:
    text_hash: Optional[str] = None
    entities: list[PDEntity] = field(default_factory=list)
    categories: dict[str, int] = field(default_factory=dict)
    processing_time_ms: float = 0.0
    warnings: list[str] = field(default_factory=list)
    document_assessment: Optional[dict] = None
    
    protection_level: Optional[str] = None
    protection_level_reason: Optional[str] = None
    
    @property
    def has_sensitive_data(self) -> bool:
        sensitive = {"passport", "snils", "inn", "credit_card", "bank_account"}
        return any(cat in sensitive for cat in self.categories) or \
               self.protection_level in {"УЗ-1", "УЗ-2", "УЗ-3"}
    
    @property
    def entity_count(self) -> int:
        return len(self.entities)


def classify_protection_level(result: DetectionResult) -> DetectionResult:

    cats = result.categories
    biometric = sum(v for k, v in cats.items() if k in BIOMETRIC_CATEGORIES)
    special = sum(v for k, v in cats.items() if k in SPECIAL_CATEGORIES)
    payment = sum(v for k, v in cats.items() if k in PAYMENT_CATEGORIES)
    gov = sum(v for k, v in cats.items() if k in GOVERNMENT_IDENTIFIERS)
    regular = sum(v for k, v in cats.items() if k in REGULAR_PDN)
    total = sum(cats.values())

    if biometric > 0 or special > 0:
        result.protection_level = "УЗ-1"
        result.protection_level_reason = "Специальные/биометрические данные (высокий риск)"
    elif payment >= LARGE_VOLUME_THRESHOLD or gov >= LARGE_VOLUME_THRESHOLD:
        result.protection_level = "УЗ-2"
        result.protection_level_reason = "Платежные/гос. данные в больших объемах"
    elif 0 < gov < LARGE_VOLUME_THRESHOLD or regular >= LARGE_VOLUME_THRESHOLD:
        result.protection_level = "УЗ-3"
        result.protection_level_reason = "Гос. идентификаторы или обычные ПДн"
    elif total > 0:
        result.protection_level = "УЗ-4"
        result.protection_level_reason = "Обычные ПДн в небольших объемах"
    else:
        result.protection_level = "УЗ-0"
        result.protection_level_reason = "ПДн не обнаружены"
        
    return result