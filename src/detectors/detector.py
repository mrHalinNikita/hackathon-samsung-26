import re
import structlog
from dataclasses import dataclass, field
from typing import Optional

logger = structlog.get_logger("detector")


@dataclass
class PDEntity:
    
    entity_type: str
    value: str
    confidence: float
    position: Optional[tuple[int, int]] = None
    context: Optional[str] = None


@dataclass
class DetectionResult:
    
    detected: bool
    categories: dict[str, int] = field(default_factory=dict)
    entities: list[PDEntity] = field(default_factory=list)
    text_hash: Optional[str] = None
    
    @property
    def has_sensitive_data(self) -> bool:
        sensitive_categories = {"passport", "snils", "inn", "credit_card"}
        return any(cat in sensitive_categories for cat in self.categories)


class PersonalDataDetector:

    PATTERNS = {
        "passport": r'\b\d{4}[\s\-]?\d{6}\b',
        "snils": r'\b\d{3}[\s\-]?\d{3}[\s\-]?\d{3}[\s\-]?\d{2}\b',
        "inn_individual": r'\b\d{10}\b',
        "inn_legal": r'\b\d{12}\b',
        "phone_ru": r'\b(?:\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}\b',
        "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    }
    
    def __init__(self, min_confidence: float = 0.7):
        self.min_confidence = min_confidence
        self._compiled_patterns = {
            name: re.compile(pattern, re.IGNORECASE)
            for name, pattern in self.PATTERNS.items()
        }
        logger.debug("PersonalDataDetector initialized", patterns=len(self.PATTERNS))
    
    def detect(self, text: str, max_entities: int = 100) -> DetectionResult:

        if not text:
            return DetectionResult(detected=False)
        
        entities = []
        categories = {}
        
        for entity_type, pattern in self._compiled_patterns.items():
            for match in pattern.finditer(text):
                if len(entities) >= max_entities:
                    break
                
                value = match.group(0)
                
                confidence = self._calculate_confidence(entity_type, value, match, text)
                
                if confidence >= self.min_confidence:
                    entity = PDEntity(
                        entity_type=entity_type,
                        value=value,
                        confidence=confidence,
                        position=(match.start(), match.end()),
                        context=self._get_context(text, match.start(), match.end(), radius=50),
                    )
                    entities.append(entity)
                    
                    category = entity_type.replace("_individual", "").replace("_legal", "")
                    categories[category] = categories.get(category, 0) + 1
        
        result = DetectionResult(
            detected=len(entities) > 0,
            categories=categories,
            entities=entities,
        )
        
        if result.detected:
            logger.debug(
                "Personal data detected",
                categories=categories,
                entity_count=len(entities),
            )
        
        return result
    
    def _calculate_confidence(
        self,
        entity_type: str,
        value: str,
        match: re.Match,
        full_text: str,
    ) -> float:

        base_confidence = 0.8
        
        context = full_text[max(0, match.start()-30):match.end()+30].lower()
        
        context_boosters = {
            "passport": ["паспорт", "серия", "номер", "документ"],
            "snils": ["снилс", "страховой", "пенсионный"],
            "inn": ["инн", "налогоплательщик", "налог"],
            "phone": ["телефон", "тел", "моб", "+7", "8 (9"],
            "email": ["email", "почта", "электронная"],
        }
        
        if entity_type in context_boosters:
            if any(keyword in context for keyword in context_boosters[entity_type]):
                base_confidence += 0.15
        
        if len(value) < 5 or len(value) > 30:
            base_confidence -= 0.1
        
        return min(1.0, max(0.0, base_confidence))
    
    def _get_context(self, text: str, start: int, end: int, radius: int = 50) -> str:
        ctx_start = max(0, start - radius)
        ctx_end = min(len(text), end + radius)
        return text[ctx_start:ctx_end].strip()


_default_detector: Optional[PersonalDataDetector] = None


def get_detector(min_confidence: float = 0.7) -> PersonalDataDetector:

    global _default_detector
    if _default_detector is None:
        _default_detector = PersonalDataDetector(min_confidence=min_confidence)
    return _default_detector


def detect_personal_data(text: str, min_confidence: float = 0.7) -> dict:

    detector = get_detector(min_confidence)
    result = detector.detect(text)
    
    return {
        "detected": result.detected,
        "categories": result.categories,
        "entities": [
            {
                "type": e.entity_type,
                "value": e.value,
                "confidence": e.confidence,
                "context": e.context,
            }
            for e in result.entities[:20]
        ],
        "has_sensitive_data": result.has_sensitive_data,
    }