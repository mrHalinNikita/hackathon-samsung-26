import re
from typing import ClassVar

from src.detectors.base import BaseDetector, PDEntity, DetectionResult
from src.detectors.config import default_config, DetectionConfig


class RegexDetector(BaseDetector):

    PATTERNS: ClassVar[dict[str, dict]] = {
        "passport": {
            "pattern": r'\b(?<!\d)(\d{4})[\s\-]?(\d{6})(?!\d)\b',
            "confidence": 0.95,
            "context_keywords": ["паспорт", "серия", "номер", "документ", "удостоверение"],
        },
        "snils": {
            "pattern": r'\b(?<!\d)(\d{3})[\s\-]?(\d{3})[\s\-]?(\d{3})[\s\-]?(\d{2})(?!\d)\b',
            "confidence": 0.95,
            "context_keywords": ["снилс", "страховой", "пенсионный", "номер"],
        },
        "inn": {
            "pattern": r'\b(?<!\d)(\d{10}|\d{12})(?!\d)\b',
            "confidence": 0.85,
            "context_keywords": ["инн", "налогоплательщик", "налог", "код"],
        },
        "phone": {
            "pattern": r'\b(?:\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}\b',
            "confidence": 0.90,
            "context_keywords": ["телефон", "тел", "моб", "контакт"],
        },
        "email": {
            "pattern": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            "confidence": 0.95,
            "context_keywords": ["email", "почта", "электронная", "адрес"],
        },
        "credit_card": {
            "pattern": r'\b(?:\d{4}[\s\-]?){3}\d{4}\b',
            "confidence": 0.80,
            "context_keywords": ["карта", "card", "оплата", "счет"],
        },
    }
    
    def __init__(self, config: DetectionConfig = None):
        self.config = config or default_config
        self._compiled = {
            name: re.compile(data["pattern"], re.IGNORECASE)
            for name, data in self.PATTERNS.items()
        }
    
    def detect(self, text: str) -> DetectionResult:
        if not text or len(text) > 1_000_000:
            return DetectionResult(warnings=["Text too long for regex detection"])
        
        entities = []
        categories = {}
        
        for entity_type, pattern_obj in self._compiled.items():
            pattern_data = self.PATTERNS[entity_type]
            
            for match in pattern_obj.finditer(text):
                value = match.group(0)
                base_conf = pattern_data["confidence"]
                
                context = self._extract_context(text, match.start(), match.end(), self.config.CONTEXT_WINDOW)
                if any(kw.lower() in context.lower() for kw in pattern_data["context_keywords"]):
                    base_conf = min(1.0, base_conf + 0.05)
                
                if base_conf >= self.config.REGEX_MIN_CONFIDENCE:
                    entity = PDEntity(
                        entity_type=self._normalize_entity_type(entity_type),
                        value=value,
                        confidence=round(base_conf, 2),
                        start_pos=match.start(),
                        end_pos=match.end(),
                        context=context,
                        source="regex",
                        metadata={"pattern_matched": entity_type},
                    )
                    entities.append(entity)
                    
                    cat = entity.entity_type
                    categories[cat] = categories.get(cat, 0) + 1
        
        return DetectionResult(
            entities=entities,
            categories=categories,
        )