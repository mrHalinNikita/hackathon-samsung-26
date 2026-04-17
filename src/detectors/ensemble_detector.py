import time
from collections import defaultdict

from src.detectors.base import BaseDetector, PDEntity, DetectionResult
from src.detectors.config import default_config, DetectionConfig
from src.detectors.regex_detector import RegexDetector
from src.detectors.nlp_detector import NLPDetector
from src.detectors.base import classify_protection_level


class EnsembleDetector(BaseDetector):
    
    def __init__(self, config: DetectionConfig = None):
        self.config = config or default_config
        self._detectors = {}
        
        if self.config.REGEX_ENABLED:
            self._detectors["regex"] = RegexDetector(self.config)
        if self.config.NLP_ENABLED:
            self._detectors["nlp"] = NLPDetector(self.config)
    
    def detect(self, text: str) -> DetectionResult:
        start_time = time.time()
        
        if not text:
            return DetectionResult()
        
        all_entities = []
        all_warnings = []
        
        regex_result = None
        if "regex" in self._detectors:
            try:
                regex_result = self._detectors["regex"].detect(text)
                all_entities.extend(regex_result.entities)
                all_warnings.extend(regex_result.warnings)
            except Exception as e:
                all_warnings.append(f"regex detector failed: {e}")

        if "nlp" in self._detectors:
            should_run_nlp = self._should_run_nlp(text, regex_result)
            if should_run_nlp:
                try:
                    nlp_result = self._detectors["nlp"].detect(text)
                    all_entities.extend(nlp_result.entities)
                    all_warnings.extend(nlp_result.warnings)
                except Exception as e:
                    all_warnings.append(f"nlp detector failed: {e}")
            else:
                all_warnings.append("nlp skipped by suspicious prefilter")
        
        merged = self._merge_entities(all_entities)
        
        final_entities = [
            e for e in merged
            if e.confidence >= self.config.FINAL_MIN_CONFIDENCE
        ]
        
        final_categories = defaultdict(int)
        for e in final_entities:
            final_categories[e.entity_type] += 1
        
        processing_time = (time.time() - start_time) * 1000
        
        result = DetectionResult(
            entities=final_entities,
            categories=dict(final_categories),
            processing_time_ms=round(processing_time, 2),
            warnings=all_warnings,
        )

        classify_protection_level(result)
    
        return result
    
    def _should_run_nlp(self, text: str, regex_result: DetectionResult | None) -> bool:
        """
        Снижает нагрузку: запускаем NLP только на "подозрительных" чанках.
        """

        if self.config.NLP_RUN_MODE == "always":
            return True

        regex_hits = len(regex_result.entities) if regex_result else 0
        if regex_hits >= self.config.NLP_PREFILTER_MIN_REGEX_ENTITIES:
            return True

        if len(text) < self.config.NLP_PREFILTER_MIN_TEXT_LENGTH:
            return False

        lowered = text.lower()
        return any(keyword in lowered for keyword in self.config.NLP_PREFILTER_KEYWORDS)
    
    def _merge_entities(self, entities: list[PDEntity]) -> list[PDEntity]:

        groups = defaultdict(list)
        
        for entity in entities:
            key = (
                entity.entity_type,
                entity.value.strip().lower(),
                entity.start_pos // 10 if entity.start_pos else None,
            )
            groups[key].append(entity)
        
        merged = []
        for key, group in groups.items():
            if len(group) == 1:
                merged.append(group[0])
            else:
                merged.append(self._aggregate_confidence(group))
        
        return merged
    
    def _aggregate_confidence(self, entities: list[PDEntity]) -> PDEntity:

        if self.config.ENSEMBLE_STRATEGY == "max":
            best = max(entities, key=lambda e: e.confidence)
            return PDEntity(
                **{k: getattr(best, k) for k in ["entity_type", "value", "start_pos", "end_pos", "context"]},
                confidence=best.confidence,
                source="ensemble",
                metadata={"sources": [e.source for e in entities]},
            )
        
        elif self.config.ENSEMBLE_STRATEGY == "weighted":
            weighted_sum = sum(
                e.confidence * self.config.ENSEMBLE_WEIGHTS.get(e.source, 0.1)
                for e in entities
            )
            total_weight = sum(
                self.config.ENSEMBLE_WEIGHTS.get(e.source, 0.1)
                for e in entities
            )
            avg_conf = weighted_sum / total_weight if total_weight > 0 else 0
            
            best = max(entities, key=lambda e: e.confidence)
            return PDEntity(
                **{k: getattr(best, k) for k in ["entity_type", "value", "start_pos", "end_pos", "context"]},
                confidence=round(min(1.0, avg_conf), 2),
                source="ensemble",
                metadata={"sources": [e.source for e in entities], "aggregated": True},
            )
        
        else:
            sources = set(e.source for e in entities)
            if len(sources) >= 2:
                best = max(entities, key=lambda e: e.confidence)
                return PDEntity(
                    **{k: getattr(best, k) for k in ["entity_type", "value", "start_pos", "end_pos", "context"]},
                    confidence=round(min(1.0, best.confidence + 0.1), 2),
                    source="ensemble",
                    metadata={"sources": list(sources), "voting": True},
                )
            else:
                return max(entities, key=lambda e: e.confidence)