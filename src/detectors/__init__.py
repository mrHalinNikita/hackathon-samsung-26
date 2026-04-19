from src.detectors.base import BaseDetector, DetectionResult, PDEntity
from src.detectors.config import DetectionConfig, default_config
from src.detectors.ensemble_detector import EnsembleDetector
from src.detectors.nlp_detector import NLPDetector
from src.detectors.regex_detector import RegexDetector
from src.detectors.rule_based_detector import RuleBasedDetector


def detect_personal_data(text: str, config: DetectionConfig = None, use_ensemble: bool = True) -> dict:
    config = config or default_config

    detector: BaseDetector
    if use_ensemble:
        detector = EnsembleDetector(config)
    else:
        detector = RuleBasedDetector(config.CONTEXT_WINDOW)
    
    result = detector.detect(text)
    assessment = result.document_assessment or {}
    
    return {
       "detected": assessment.get("has_personal_data", result.has_sensitive_data),
        "has_personal_data": assessment.get("has_personal_data", result.has_sensitive_data),
        "overall_confidence": assessment.get("overall_confidence", "no_pd_or_weak"),
        "overall_risk_score": assessment.get("overall_risk_score", 0),
        "detected_categories": assessment.get("detected_categories", list(result.categories.keys())),
        "legal_buckets_present": assessment.get("legal_buckets_present", []),
        "strongest_category": assessment.get("strongest_category"),
        "short_reason": assessment.get("short_reason", ""),
        "long_reason": assessment.get("long_reason", ""),
        "protection_level": result.protection_level,
        "protection_level_reason": result.protection_level_reason,
        "categories": result.categories,
        "entities": [
            {
                "category": e.metadata.get("category"),
                "type": e.entity_type,
                "subtype": e.metadata.get("subtype", e.entity_type),
                "matched_text_redacted": e.metadata.get("matched_text_redacted", "***"),
                "normalized_value_if_safe": e.metadata.get("normalized_value_if_safe", e.metadata.get("matched_text_redacted", "***")),
                "start": e.start_pos,
                "end": e.end_pos,
                "context_snippet": e.context,
                "confidence": e.confidence,
                "reasons": e.metadata.get("reasons", []),
                "legal_bucket": e.metadata.get("legal_bucket", "ordinary"),
                "source": e.source,
            }
            for e in result.entities[: config.MAX_ENTITIES_PER_TYPE]
        ],
        "entity_count": result.entity_count,
        "hit_count": assessment.get("hit_count", result.entity_count),
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
    "RuleBasedDetector",
    "detect_personal_data",
]