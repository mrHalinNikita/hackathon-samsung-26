import re
import unicodedata
from dataclasses import dataclass, field
from typing import ClassVar

from src.detectors.base import BaseDetector, DetectionResult, PDEntity, classify_protection_level


@dataclass(frozen=True)
class CategoryDefinition:
    category: str
    subtype: str
    legal_bucket: str
    base_score: int
    description: str
    is_strong_identifier: bool = False


@dataclass
class MatchEvidence:
    category: str
    subtype: str
    value: str
    start: int
    end: int
    reasons: list[str] = field(default_factory=list)
    confidence: float = 0.0
    score: int = 0
    legal_bucket: str = "ordinary"


@dataclass(frozen=True)
class CompositeRule:
    rule_id: str
    description: str
    required_subtypes: tuple[str, ...]
    score_bonus: int


class RiskScorer:
    CONFIDENCE_BOUNDS: ClassVar[list[tuple[int, str]]] = [
        (20, "low"),
        (40, "medium"),
        (60, "high"),
        (80, "very_high"),
    ]

    @classmethod
    def confidence_from_score(cls, score: int) -> str:
        if score < 20:
            return "no_pd_or_weak"
        if score < 40:
            return "low"
        if score < 60:
            return "medium"
        if score < 80:
            return "high"
        return "very_high"


class RuleBasedDetector(BaseDetector):
    """Cascade detector with normalization, patterns, context, composite rules and document scoring."""

    CATEGORY_REGISTRY: ClassVar[dict[str, CategoryDefinition]] = {
        "passport_rf": CategoryDefinition("DIRECT_IDENTIFIERS", "passport_rf", "ordinary", 40, "Паспорт РФ", True),
        "snils": CategoryDefinition("DIRECT_IDENTIFIERS", "snils", "ordinary", 40, "СНИЛС", True),
        "inn": CategoryDefinition("DIRECT_IDENTIFIERS", "inn", "ordinary", 35, "ИНН физлица", True),
        "driver_license": CategoryDefinition("DIRECT_IDENTIFIERS", "driver_license", "ordinary", 35, "ВУ/права", True),
        "phone_ru": CategoryDefinition("CONTACT_DATA", "phone_ru", "ordinary", 20, "Телефон РФ"),
        "phone_international": CategoryDefinition("CONTACT_DATA", "phone_international", "ordinary", 20, "Международный телефон"),
        "email": CategoryDefinition("CONTACT_DATA", "email", "ordinary", 20, "Email"),
        "postal_address": CategoryDefinition("CONTACT_DATA", "postal_address", "ordinary", 20, "Почтовый/регистрационный адрес"),
        "full_name": CategoryDefinition("BASIC_PERSONAL_DATA", "full_name", "ordinary", 20, "ФИО"),
        "first_name_last_name": CategoryDefinition("BASIC_PERSONAL_DATA", "first_name_last_name", "ordinary", 15, "Имя Фамилия"),
        "initials_plus_last_name": CategoryDefinition("BASIC_PERSONAL_DATA", "initials_plus_last_name", "ordinary", 12, "Фамилия И.О."),
        "date_of_birth": CategoryDefinition("BASIC_PERSONAL_DATA", "date_of_birth", "ordinary", 20, "Дата рождения"),
        "place_of_birth": CategoryDefinition("BASIC_PERSONAL_DATA", "place_of_birth", "ordinary", 15, "Место рождения"),
        "health_data": CategoryDefinition("SPECIAL_CATEGORIES_152FZ", "health_data", "special", 35, "Медицинские сведения"),
        "disability_data": CategoryDefinition("SPECIAL_CATEGORIES_152FZ", "disability_data", "special", 35, "Инвалидность"),
        "racial_or_ethnic_origin": CategoryDefinition("SPECIAL_CATEGORIES_152FZ", "racial_or_ethnic_origin", "special", 30, "Национальность/этнос"),
        "religious_or_philosophical_beliefs": CategoryDefinition("SPECIAL_CATEGORIES_152FZ", "religious_or_philosophical_beliefs", "special", 30, "Религиозные убеждения"),
        "political_views": CategoryDefinition("SPECIAL_CATEGORIES_152FZ", "political_views", "special", 30, "Политические взгляды"),
        "union_membership": CategoryDefinition("SPECIAL_CATEGORIES_152FZ", "union_membership", "special", 30, "Членство в профсоюзе"),
        "face_image_context": CategoryDefinition("BIOMETRIC_DATA", "face_image_context", "biometric", 40, "Биометрия лица"),
        "voice_biometric_context": CategoryDefinition("BIOMETRIC_DATA", "voice_biometric_context", "biometric", 40, "Голосовая биометрия"),
        "fingerprint_context": CategoryDefinition("BIOMETRIC_DATA", "fingerprint_context", "biometric", 40, "Отпечатки"),
        "retina_context": CategoryDefinition("BIOMETRIC_DATA", "retina_context", "biometric", 40, "Сетчатка"),
        "age": CategoryDefinition("LINKAGE_SIGNALS", "age", "weak_signal", 8, "Возраст"),
        "exact_date": CategoryDefinition("LINKAGE_SIGNALS", "exact_date", "weak_signal", 8, "Точная дата"),
        "relative_relation": CategoryDefinition("LINKAGE_SIGNALS", "relative_relation", "weak_signal", 8, "Родственные связи"),
        "account_number_with_person_context": CategoryDefinition("LINKAGE_SIGNALS", "account_number_with_person_context", "weak_signal", 10, "Счет/реквизиты"),
        "car_number_with_owner_context": CategoryDefinition("LINKAGE_SIGNALS", "car_number_with_owner_context", "weak_signal", 10, "Госномер авто"),
        "ip_with_user_context": CategoryDefinition("LINKAGE_SIGNALS", "ip_with_user_context", "weak_signal", 8, "IP с контекстом пользователя"),
    }

    COMPOSITE_RULES: ClassVar[list[CompositeRule]] = [
        CompositeRule("fio_dob", "ФИО + дата рождения", ("full_name", "date_of_birth"), 20),
        CompositeRule("fio_address", "ФИО + адрес", ("full_name", "postal_address"), 20),
        CompositeRule("name_contact", "Имя + контакт", ("full_name", "phone_ru"), 15),
        CompositeRule("name_email", "ФИО + email", ("full_name", "email"), 15),
        CompositeRule("doc_plus_name", "Идентификатор + ФИО", ("full_name", "passport_rf"), 20),
    ]

    PATTERNS: ClassVar[dict[str, str]] = {
        "passport_rf": r"(?:паспорт(?:\s*рф)?|серия\s*и\s*номер|серия\s*номер)?\s*[:№-]*\s*\b\d{2}\s?\d{2}\s?\d{6}\b",
        "snils": r"\b\d{3}[\s\-]?\d{3}[\s\-]?\d{3}[\s\-]?\d{2}\b",
        "inn": r"\b\d{12}\b",
        "driver_license": r"(?:водительск\w+\s+удостоверени\w+|права)[:\s№-]*\b\d{2}\s?\d{2}\s?\d{6}\b",
        "phone_ru": r"(?:\+7|8)\s*\(?\d{3}\)?[\s\-]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}",
        "phone_international": r"\+\d{1,3}[\s\-\(]*\d{2,4}[\)\s\-]*\d{2,4}[\s\-]*\d{2,4}[\s\-]*\d{0,4}",
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        "full_name": r"\b[А-ЯЁ][а-яё]{2,}\s+[А-ЯЁ][а-яё]{2,}\s+[А-ЯЁ][а-яё]{2,}\b",
        "first_name_last_name": r"\b[А-ЯЁ][а-яё]{2,}\s+[А-ЯЁ][а-яё]{2,}\b",
        "initials_plus_last_name": r"\b[А-ЯЁ][а-яё]{2,}\s+[А-ЯЁ]\.\s?[А-ЯЁ]\.\b",
        "date_of_birth": r"(?:дата\s*рождения|д\.?р\.?)?\s*[:\-]?\s*\b(?:0?[1-9]|[12]\d|3[01])[\.\-/](?:0?[1-9]|1[0-2])[\.\-/](?:19\d{2}|20\d{2})\b",
        "place_of_birth": r"(?:место\s+рождения)\s*[:\-]?\s*[А-ЯЁ][^\n,;]{2,40}",
        "postal_address": r"(?:адрес|зарегистрирован|проживает)[:\s\-]*[^\n]{6,160}",
        "age": r"\b(?:возраст|лет)\s*[:\-]?\s*\d{1,3}\b",
        "exact_date": r"\b(?:0?[1-9]|[12]\d|3[01])[\.\-/](?:0?[1-9]|1[0-2])[\.\-/](?:19\d{2}|20\d{2})\b",
        "relative_relation": r"\b(сын|дочь|мать|отец|супруг|супруга|родственник)\b",
        "account_number_with_person_context": r"\b(?:счет|р/с|расчетный\s+счет|iban)[:\s\-]*[A-Z0-9]{10,34}\b",
        "car_number_with_owner_context": r"\b[АВЕКМНОРСТУХABEKMHOPCTYX]\d{3}[АВЕКМНОРСТУХABEKMHOPCTYX]{2}\d{2,3}\b",
        "ip_with_user_context": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    }

    SPECIAL_CONTEXT: ClassVar[dict[str, list[str]]] = {
        "health_data": ["пациент", "диагноз", "жалобы", "заключение врача", "анамнез", "медкарта"],
        "disability_data": ["инвалид", "инвалидность", "группа инвалидности"],
        "racial_or_ethnic_origin": ["национальность", "этничес", "раса"],
        "religious_or_philosophical_beliefs": ["религия", "вероисповедание", "атеист"],
        "political_views": ["политическ", "партийная принадлежность", "оппозиция"],
        "union_membership": ["профсоюз", "членство в профсоюзе"],
    }

    BIOMETRIC_CONTEXT: ClassVar[dict[str, list[str]]] = {
        "face_image_context": ["фото лица", "изображение лица", "face embedding", "биометрия лица"],
        "voice_biometric_context": ["voiceprint", "голосовой слепок", "образец голоса"],
        "fingerprint_context": ["отпечаток пальца", "дактилоскоп"],
        "retina_context": ["сетчатк", "iris", "радужк"],
    }

    PERSON_MARKERS: ClassVar[list[str]] = ["фио", "сотрудник", "гражданин", "пациент", "работник", "student", "студент"]
    STRICT_CONTEXT_REQUIRED: ClassVar[dict[str, list[str]]] = {
        "passport_rf": ["паспорт", "серия", "выдан"],
        "driver_license": ["водитель", "удостоверени", "права"],
        "inn": ["инн", "налог"],
        "snils": ["снилс", "страх"],
    }

    def __init__(self, context_window: int = 80):
        self.context_window = context_window
        self._compiled = {k: re.compile(v, re.IGNORECASE) for k, v in self.PATTERNS.items()}

    def detect(self, text: str) -> DetectionResult:
        normalized = self._normalize_text(text)
        evidences: list[MatchEvidence] = []

        evidences.extend(self._pattern_layer(normalized))
        evidences.extend(self._context_layer(normalized))
        self._apply_composite_rules(evidences)

        entities = [self._to_entity(normalized, ev) for ev in evidences if ev.confidence >= 0.25]
        categories: dict[str, int] = {}
        for entity in entities:
            categories[entity.entity_type] = categories.get(entity.entity_type, 0) + 1

        assessment = self._assess_document(evidences)

        result = DetectionResult(
            entities=entities,
            categories=categories,
            warnings=[],
            document_assessment=assessment,
        )
        classify_protection_level(result)
        return result

    def _normalize_text(self, text: str) -> str:
        text = unicodedata.normalize("NFKC", text or "")
        text = text.replace("\xa0", " ")
        text = text.replace("−", "-").replace("—", "-").replace("–", "-")
        text = re.sub(r"\bС\s*Н\s*И\s*Л\s*С\b", "СНИЛС", text, flags=re.IGNORECASE)
        text = re.sub(r"\bИ\s*Н\s*Н\b", "ИНН", text, flags=re.IGNORECASE)
        text = re.sub(r"(?<=\d)\s+(?=\d)", "", text)
        text = re.sub(r"([A-Za-zА-Яа-яЁё])\s{2,}([A-Za-zА-Яа-яЁё])", r"\1 \2", text)
        return text

    def _pattern_layer(self, text: str) -> list[MatchEvidence]:
        evidences: list[MatchEvidence] = []
        for subtype, pattern in self._compiled.items():
            definition = self.CATEGORY_REGISTRY.get(subtype)
            if not definition:
                continue
            for match in pattern.finditer(text):
                value = match.group(0)
                if subtype == "phone_international" and value.startswith(("+7", "8")):
                    continue
                context = self._context_snippet(text, match.start(), match.end()).lower()
                required_context = self.STRICT_CONTEXT_REQUIRED.get(subtype)
                if required_context and not any(marker in context for marker in required_context):
                    continue
                reasons = [f"pattern:{subtype}"]
                if any(marker in context.lower() for marker in self.PERSON_MARKERS):
                    reasons.append("person_context_marker")
                score = definition.base_score + (5 if "person_context_marker" in reasons else 0)
                confidence = min(1.0, score / 80)
                evidences.append(
                    MatchEvidence(
                        category=definition.category,
                        subtype=subtype,
                        value=value,
                        start=match.start(),
                        end=match.end(),
                        reasons=reasons,
                        confidence=round(confidence, 2),
                        score=score,
                        legal_bucket=definition.legal_bucket,
                    )
                )
        return evidences

    def _context_layer(self, text: str) -> list[MatchEvidence]:
        evidences: list[MatchEvidence] = []
        low_text = text.lower()
        for subtype, keywords in self.SPECIAL_CONTEXT.items():
            for kw in keywords:
                idx = low_text.find(kw)
                if idx >= 0:
                    definition = self.CATEGORY_REGISTRY[subtype]
                    score = definition.base_score
                    evidences.append(MatchEvidence(
                        category=definition.category,
                        subtype=subtype,
                        value=text[idx:idx + len(kw)],
                        start=idx,
                        end=idx + len(kw),
                        reasons=["special_context_keyword"],
                        confidence=round(min(1.0, score / 80), 2),
                        score=score,
                        legal_bucket=definition.legal_bucket,
                    ))
        for subtype, keywords in self.BIOMETRIC_CONTEXT.items():
            for kw in keywords:
                idx = low_text.find(kw)
                if idx >= 0:
                    definition = self.CATEGORY_REGISTRY[subtype]
                    score = definition.base_score
                    evidences.append(MatchEvidence(
                        category=definition.category,
                        subtype=subtype,
                        value=text[idx:idx + len(kw)],
                        start=idx,
                        end=idx + len(kw),
                        reasons=["biometric_context_keyword"],
                        confidence=round(min(1.0, score / 80), 2),
                        score=score,
                        legal_bucket=definition.legal_bucket,
                    ))
        return evidences

    def _apply_composite_rules(self, evidences: list[MatchEvidence]) -> None:
        positions_by_subtype: dict[str, list[int]] = {}
        for ev in evidences:
            positions_by_subtype.setdefault(ev.subtype, []).append(ev.start)

        for rule in self.COMPOSITE_RULES:
            if not all(req in positions_by_subtype for req in rule.required_subtypes):
                continue
            for ev in evidences:
                if ev.subtype in rule.required_subtypes:
                    ev.score += rule.score_bonus
                    ev.confidence = round(min(1.0, ev.score / 80), 2)
                    ev.reasons.append(f"composite:{rule.rule_id}")

    def _assess_document(self, evidences: list[MatchEvidence]) -> dict:
        if not evidences:
            return {
                "has_personal_data": False,
                "overall_confidence": "no_pd_or_weak",
                "overall_risk_score": 0,
                "detected_categories": [],
                "legal_buckets_present": [],
                "strongest_category": None,
                "short_reason": "Сигналы ПДн не обнаружены",
                "long_reason": "По правилам детектора не найдено достаточных индикаторов персональных данных.",
            }

        category_scores: dict[str, int] = {}
        legal_buckets: set[str] = set()
        subtypes = set()
        for ev in evidences:
            category_scores[ev.category] = category_scores.get(ev.category, 0) + ev.score
            legal_buckets.add(ev.legal_bucket)
            subtypes.add(ev.subtype)

        strongest_category = max(category_scores, key=category_scores.get)
        bundle_bonus = 0
        if {"full_name", "date_of_birth"}.issubset(subtypes):
            bundle_bonus += 15
        if {"full_name", "postal_address"}.issubset(subtypes):
            bundle_bonus += 15
        if "special" in legal_buckets:
            bundle_bonus += 10
        if "biometric" in legal_buckets:
            bundle_bonus += 10

        risk_score = min(100, sum(sorted((ev.score for ev in evidences), reverse=True)[:5]) + bundle_bonus)
        confidence = RiskScorer.confidence_from_score(risk_score)

        short_reason = self._short_reason(subtypes, legal_buckets)
        long_reason = self._long_reason(subtypes, legal_buckets)

        return {
            "has_personal_data": risk_score >= 20,
            "overall_confidence": confidence,
            "overall_risk_score": risk_score,
            "detected_categories": sorted(category_scores.keys()),
            "legal_buckets_present": sorted(legal_buckets),
            "strongest_category": strongest_category,
            "short_reason": short_reason,
            "long_reason": long_reason,
            "hit_count": len(evidences),
            "number_of_hits": len(evidences),
            "diversity_of_categories": len(category_scores.keys()),
            "special_or_biometric_present": bool({"special", "biometric"} & legal_buckets),
        }

    def _short_reason(self, subtypes: set[str], legal_buckets: set[str]) -> str:
        reasons = []
        if {"full_name", "date_of_birth"}.issubset(subtypes):
            reasons.append("ФИО + дата рождения")
        if "postal_address" in subtypes:
            reasons.append("адрес")
        if "special" in legal_buckets:
            reasons.append("специальные категории")
        if "biometric" in legal_buckets:
            reasons.append("биометрические признаки")
        return " + ".join(reasons) if reasons else "Обнаружены потенциальные персональные данные"

    def _long_reason(self, subtypes: set[str], legal_buckets: set[str]) -> str:
        base = "Обнаружены признаки идентификации физического лица на основе набора идентификаторов и контекстных сигналов."
        if "special" in legal_buckets:
            base += " Выявлен медицинский/чувствительный контекст, отнесенный к специальным категориям ПДн."
        if "biometric" in legal_buckets:
            base += " Найден биометрический контекст (лицо/голос/отпечатки/сетчатка)."
        if "full_name" in subtypes and "date_of_birth" in subtypes:
            base += " Комбинация ФИО и даты рождения повышает вероятность однозначной идентификации."
        return base

    def _to_entity(self, text: str, ev: MatchEvidence) -> PDEntity:
        redacted = self._redact(ev.subtype, ev.value)
        return PDEntity(
            entity_type=ev.subtype,
            value=redacted,
            confidence=ev.confidence,
            start_pos=ev.start,
            end_pos=ev.end,
            context=self._context_snippet(text, ev.start, ev.end),
            source="ensemble",
            metadata={
                "category": ev.category,
                "subtype": ev.subtype,
                "matched_text_redacted": redacted,
                "normalized_value_if_safe": self._safe_normalized(ev.subtype, ev.value),
                "reasons": ev.reasons,
                "legal_bucket": ev.legal_bucket,
            },
        )

    def _context_snippet(self, text: str, start: int, end: int) -> str:
        left = max(0, start - self.context_window)
        right = min(len(text), end + self.context_window)
        return text[left:right].strip()

    def _safe_normalized(self, subtype: str, value: str) -> str | None:
        if subtype in {"phone_ru", "phone_international", "passport_rf", "snils", "inn", "email"}:
            return None
        return " ".join(value.split())[:120]

    def _redact(self, subtype: str, value: str) -> str:
        digits = re.sub(r"\D", "", value)
        if subtype in {"passport_rf", "driver_license"} and len(digits) >= 10:
            return f"{digits[:4]} ******"
        if subtype == "snils" and len(digits) >= 11:
            return f"{digits[:3]}-***-*** {digits[-2:]}"
        if subtype in {"phone_ru", "phone_international"} and len(digits) >= 6:
            return f"+* (***) ***-**-{digits[-2:]}"
        if subtype == "email" and "@" in value:
            user, domain = value.split("@", 1)
            return f"{user[:2]}***@***.{domain.split('.')[-1]}"
        return value[:2] + "***" if len(value) > 4 else "***"