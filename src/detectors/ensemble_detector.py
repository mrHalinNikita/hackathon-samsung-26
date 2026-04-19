import time
from collections import defaultdict

from src.detectors.base import BaseDetector, DetectionResult, PDEntity, classify_protection_level
from src.detectors.config import DetectionConfig, default_config
from src.detectors.nlp_detector import NLPDetector
from src.detectors.regex_detector import RegexDetector
from src.detectors.rule_based_detector import RuleBasedDetector


class EnsembleDetector(BaseDetector):
    def __init__(self, config: DetectionConfig = None):
        self.config = config or default_config
        self._detectors = {}

        if self.config.RULE_ENGINE_ENABLED:
            self._detectors["rule_engine"] = RuleBasedDetector(self.config.CONTEXT_WINDOW, config=self.config)
        if self.config.REGEX_ENABLED:
            self._detectors["regex"] = RegexDetector(self.config)
        if self.config.NLP_ENABLED:
            self._detectors["nlp"] = NLPDetector(self.config)

    def detect(self, text: str) -> DetectionResult:
        start_time = time.time()
        if not text:
            return DetectionResult()

        all_entities: list[PDEntity] = []
        warnings: list[str] = []
        merged_assessment = None

        regex_result = None
        if "regex" in self._detectors:
            try:
                regex_result = self._detectors["regex"].detect(text)
                all_entities.extend(regex_result.entities)
                warnings.extend(regex_result.warnings)
            except Exception as exc:
                warnings.append(f"regex detector failed: {exc}")

        if "nlp" in self._detectors:
            if self._should_run_nlp(text, regex_result):
                try:
                    nlp_res = self._detectors["nlp"].detect(text)
                    all_entities.extend(nlp_res.entities)
                    warnings.extend(nlp_res.warnings)
                except Exception as exc:
                    warnings.append(f"nlp detector failed: {exc}")
            else:
                warnings.append("nlp skipped by suspicious prefilter")

        if "rule_engine" in self._detectors:
            try:
                res = self._detectors["rule_engine"].detect(text)
                all_entities.extend(res.entities)
                warnings.extend(res.warnings)
                merged_assessment = res.document_assessment
            except Exception as exc:
                warnings.append(f"rule_engine detector failed: {exc}")

        merged = self._merge_entities(all_entities)
        categories = defaultdict(int)
        for entity in merged:
            categories[entity.entity_type] += 1

        result = DetectionResult(
            entities=merged,
            categories=dict(categories),
            processing_time_ms=round((time.time() - start_time) * 1000, 2),
            warnings=warnings,
            document_assessment=merged_assessment or self._fallback_assessment(merged),
        )
        classify_protection_level(result)
        return result

    def _should_run_nlp(self, text: str, regex_result: DetectionResult | None) -> bool:
        if self.config.NLP_RUN_MODE == "always":
            return True

        regex_hits = len(regex_result.entities) if regex_result else 0
        if regex_hits >= self.config.NLP_PREFILTER_MIN_REGEX_ENTITIES:
            return True

        lowered = text.lower()
        if any(keyword in lowered for keyword in self.config.NLP_PREFILTER_KEYWORDS):
            return True

        if len(text) < self.config.NLP_PREFILTER_MIN_TEXT_LENGTH:
            return False

        return False

    def _fallback_assessment(self, entities: list[PDEntity]) -> dict:
        return {
            "has_personal_data": bool(entities),
            "overall_confidence": "medium" if entities else "no_pd_or_weak",
            "overall_risk_score": 40 if entities else 0,
            "detected_categories": sorted({e.entity_type for e in entities}),
            "legal_buckets_present": ["ordinary"] if entities else [],
            "strongest_category": entities[0].entity_type if entities else None,
            "short_reason": "Найдены подтвержденные сущности" if entities else "Сигналы ПДн не обнаружены",
            "long_reason": "Fallback assessment",
            "hit_count": len(entities),
        }

    def _merge_entities(self, entities: list[PDEntity]) -> list[PDEntity]:
        grouped = {}
        for entity in entities:
            key = (entity.entity_type, entity.value, entity.start_pos)
            best = grouped.get(key)
            if not best or entity.confidence > best.confidence:
                grouped[key] = entity
        return list(grouped.values())
