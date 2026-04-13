import time
from typing import Optional

from src.detectors.base import BaseDetector, PDEntity, DetectionResult
from src.detectors.config import default_config, DetectionConfig


class NLPDetector(BaseDetector):
    
    def __init__(self, config: DetectionConfig = None):
        self.config = config or default_config
        self._ner = None
        self._morph = None
    
    def _init_models(self):

        if self._ner is None:
            from natasha import (
                Segmenter, MorphVocab, NewsEmbedding,
                NewsMorphTagger, NewsNERTagger, Doc
            )
            
            self._segmenter = Segmenter()
            self._morph_vocab = MorphVocab()
            self._emb = NewsEmbedding()
            self._morph_tagger = NewsMorphTagger(self._emb)
            self._ner_tagger = NewsNERTagger(self._emb)
    
    def detect(self, text: str) -> DetectionResult:
        start_time = time.time()
        
        if not text:
            return DetectionResult()
        
        if len(text) > self.config.MAX_TEXT_LENGTH_FOR_NLP:
            text = text[:self.config.MAX_TEXT_LENGTH_FOR_NLP]
            warning = f"Text truncated to {self.config.MAX_TEXT_LENGTH_FOR_NLP} chars for NLP"
        else:
            warning = None
        
        try:
            self._init_models()
        except ImportError:
            return DetectionResult(warnings=["NLP models not available (install natasha)"])
        
        entities = []
        categories = {}
        
        from natasha import Doc
        doc = Doc(text)
        doc.segment(self._segmenter)
        doc.tag_morph(self._morph_tagger)
        doc.tag_ner(self._ner_tagger)
        
        for span in doc.spans:
            if span.type not in self.config.NLP_ENTITY_TYPES:
                continue
            
            value = span.text
            entity_type = self._normalize_entity_type(span.type)
            
            base_conf = 0.65
            
            if span.type == "PER" and self._looks_like_name(value):
                base_conf += 0.15
            elif span.type == "ORG" and len(value) > 3:
                base_conf += 0.10
            
            if base_conf >= self.config.NLP_MIN_CONFIDENCE:
                context = self._extract_context(text, span.start, span.stop, self.config.CONTEXT_WINDOW)
                
                entity = PDEntity(
                    entity_type=entity_type,
                    value=value,
                    confidence=round(min(1.0, base_conf), 2),
                    start_pos=span.start,
                    end_pos=span.stop,
                    context=context,
                    source="nlp",
                    metadata={"ner_type": span.type},
                )
                entities.append(entity)
                
                cat = entity.entity_type
                categories[cat] = categories.get(cat, 0) + 1
        
        processing_time = (time.time() - start_time) * 1000
        
        result = DetectionResult(
            entities=entities,
            categories=categories,
            processing_time_ms=round(processing_time, 2),
        )
        if warning:
            result.warnings.append(warning)
        
        return result
    
    def _looks_like_name(self, text: str) -> bool:

        if not text or len(text) < 3:
            return False
        
        parts = text.strip().split()
        if 2 <= len(parts) <= 4:
            if all(p[0].isupper() and p[1:].islower() for p in parts if p):
                return True
        
        return False