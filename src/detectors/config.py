from pydantic import BaseModel, Field
from typing import Literal


class DetectionConfig(BaseModel):
    
    # Regex
    REGEX_ENABLED: bool = True
    REGEX_MIN_CONFIDENCE: float = 0.8
    
    # NLP
    NLP_ENABLED: bool = True
    NLP_MIN_CONFIDENCE: float = 0.6
    NLP_ENTITY_TYPES: list[str] = ["PER", "ORG", "LOC", "DATE"]
    
    # Fuzzy
    FUZZY_ENABLED: bool = True
    FUZZY_THRESHOLD: int = 85
    FUZZY_CANDIDATES: int = 3
    
    # Context 
    CONTEXT_ENABLED: bool = True
    CONTEXT_WINDOW: int = 50
    CONTEXT_PENALTY: float = 0.2
    
    # Ensemble
    ENSEMBLE_STRATEGY: Literal["max", "weighted", "voting"] = "weighted"
    ENSEMBLE_WEIGHTS: dict[str, float] = {
        "regex": 0.5,
        "nlp": 0.3,
        "fuzzy": 0.2,
    }
    FINAL_MIN_CONFIDENCE: float = 0.7
    
    MAX_ENTITIES_PER_TYPE: int = 100
    MAX_TEXT_LENGTH_FOR_NLP: int = 50000


default_config = DetectionConfig()