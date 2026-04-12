import time
from collections import defaultdict

from src.detectors.base import BaseDetector, PDEntity, DetectionResult
from src.detectors.config import default_config, DetectionConfig
from src.detectors.regex_detector import RegexDetector
from src.detectors.nlp_detector import NLPDetector


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
        all_categories = defaultdict(int)
        all_warnings = []
        
        for name, detector in self._detectors.items():
            try:
                result = detector.detect(text)
                all_entities.extend(result.entities)
                for cat, count in result.categories.items():
                    all_categories[cat] += count
                all_warnings.extend(result.warnings)
            except Exception as e:
                all_warnings.append(f"{name} detector failed: {e}")
        
        merged = self._merge_entities(all_entities)
        
        final_entities = [
            e for e in merged
            if e.confidence >= self.config.FINAL_MIN_CONFIDENCE
        ]
        
        final_categories = defaultdict(int)
        for e in final_entities:
            final_categories[e.entity_type] += 1
        
        processing_time = (time.time() - start_time) * 1000
        
        return DetectionResult(
            entities=final_entities,
            categories=dict(final_categories),
            processing_time_ms=round(processing_time, 2),
            warnings=all_warnings,
        )
    
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