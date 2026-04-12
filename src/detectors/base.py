from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Literal
import re


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


@dataclass
class DetectionResult:
    
    text_hash: Optional[str] = None
    entities: list[PDEntity] = field(default_factory=list)
    categories: dict[str, int] = field(default_factory=dict)
    processing_time_ms: float = 0.0
    warnings: list[str] = field(default_factory=list)
    
    @property
    def has_sensitive_data(self) -> bool:
        sensitive = {"passport", "snils", "inn", "credit_card", "bank_account"}
        return any(cat in sensitive for cat in self.categories)
    
    @property
    def entity_count(self) -> int:
        return len(self.entities)


class BaseDetector(ABC):
    
    @abstractmethod
    def detect(self, text: str) -> DetectionResult:
        pass
    
    @staticmethod
    def _normalize_entity_type(entity_type: str) -> str:

        mapping = {
            "PER": "person_name",
            "ORG": "organization",
            "LOC": "location",
            "DATE": "date",
            "passport": "passport",
            "snils": "snils",
            "inn_individual": "inn",
            "inn_legal": "inn",
            "phone_ru": "phone",
            "email": "email",
        }
        return mapping.get(entity_type, entity_type.lower())
    
    @staticmethod
    def _extract_context(text: str, start: int, end: int, window: int = 50) -> str:

        ctx_start = max(0, start - window)
        ctx_end = min(len(text), end + window)
        return text[ctx_start:ctx_end].strip()