from src.detectors.config import DetectionConfig, default_config
from src.detectors.base import PDEntity, DetectionResult, BaseDetector
from src.detectors.regex_detector import RegexDetector
from src.detectors.nlp_detector import NLPDetector
from src.detectors.ensemble_detector import EnsembleDetector


def detect_personal_data(text: str, config: DetectionConfig = None, use_ensemble: bool = True,) -> dict:

    config = config or default_config
    
    if use_ensemble:
        detector = EnsembleDetector(config)
    else:
        from src.detectors.regex_detector import RegexDetector
        detector = RegexDetector(config)
    
    result = detector.detect(text)
    
    return {
        "detected": result.has_sensitive_data,
        "categories": result.categories,
        "entities": [
            {
                "type": e.entity_type,
                "value": e.value,
                "confidence": e.confidence,
                "context": e.context,
                "source": e.source,
            }
            for e in result.entities[:config.MAX_ENTITIES_PER_TYPE]
        ],
        "entity_count": result.entity_count,
        "processing_time_ms": result.processing_time_ms,
        "warnings": result.warnings,
    }


__all__ = [
    "DetectionConfig",
    "default_config",
    "PDEntity",
    "DetectionResult",
    "EnsembleDetector",
    "RegexDetector",
    "NLPDetector", 
]