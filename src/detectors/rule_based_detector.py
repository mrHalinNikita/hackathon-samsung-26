import hashlib
import re
import time
from collections import defaultdict
from dataclasses import dataclass

from src.detectors.base import BaseDetector, DetectionResult, PDEntity, classify_protection_level
from src.detectors.config import DetectionConfig, default_config


@dataclass
class Scope:
    scope_id: str
    text: str
    offset: int
    scope_type: str


@dataclass
class Evidence:
    entity_type: str
    subtype: str
    value: str
    masked_value: str
    strength: str
    confidence: float
    start: int
    end: int
    scope_id: str
    reasons: list[str]
    legal_bucket: str = "ordinary"


class RuleBasedDetector(BaseDetector):
    SNILS_RE = re.compile(r"\b\d{3}[\s\-]?\d{3}[\s\-]?\d{3}[\s\-]?\d{2}\b")
    INN_RE = re.compile(r"\b\d{10}\b|\b\d{12}\b")
    CARD_RE = re.compile(r"\b(?:\d[\s\-]?){13,19}\b")
    PASSPORT_RE = re.compile(r"\b\d{2}\s?\d{2}\s?\d{6}\b")
    PHONE_RE = re.compile(r"(?:\+7|8)\s*\(?\d{3}\)?[\s\-]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}")
    EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
    DOB_RE = re.compile(r"\b(?:0?[1-9]|[12]\d|3[01])[\.\-/](?:0?[1-9]|1[0-2])[\.\-/](?:19\d{2}|20\d{2})\b")
    FIO_RE = re.compile(r"\b[А-ЯЁ][а-яё]{2,}\s+[А-ЯЁ][а-яё]{2,}(?:\s+[А-ЯЁ][а-яё]{2,})?\b")
    MRZ_RE = re.compile(r"(?m)^[A-Z0-9<]{30,44}$")
    ACCOUNT_RE = re.compile(r"\b\d{20}\b")
    BIK_RE = re.compile(r"\b\d{9}\b")

    PERSON_CONTEXT = ["фио", "сотрудник", "пациент", "контакт", "клиент", "гражданин", "person"]
    DOB_CONTEXT = ["дата рождения", "г.р", "родился", "родилась", "birth", "dob"]
    ADDRESS_CONTEXT = ["адрес проживания", "адрес регистрации", "место жительства", "прописка"]
    GOV_CONTEXT = {
        "snils": ["снилс"],
        "inn": ["инн"],
        "passport": ["паспорт", "серия", "номер", "выдан", "код подразделения"],
    }
    ACCOUNT_CONTEXT = ["счет", "р/с", "расчетный счет", "банк", "бик"]
    NEGATIVE_PLACEHOLDERS = ["example", "sample", "demo", "шаблон", "образец", "<фио>", "заполните"]
    ORG_TOKENS = ["ооо", "ао", "пао", "департамент", "управление", "министерство", "филиал"]
    GENERIC_EMAIL_LOCALPARTS = {"info", "support", "sales", "hr", "contact", "hello"}

    def __init__(self, context_window: int = 80, config: DetectionConfig | None = None):
        self.context_window = context_window
        self.config = config or default_config

    def detect(self, text: str) -> DetectionResult:
        start = time.time()
        normalized = self._normalize(text)
        scopes = self._build_scopes(normalized)

        evidences: list[Evidence] = []
        exclusions: defaultdict[str, int] = defaultdict(int)
        for scope in scopes:
            ev, ex = self._analyze_scope(scope)
            evidences.extend(ev)
            for reason in ex:
                exclusions[reason] += 1

        confirmed = self._classify_file(evidences)
        entities = [self._to_entity(x, normalized) for x in confirmed]

        categories: dict[str, int] = defaultdict(int)
        for entity in entities:
            categories[entity.entity_type] += 1

        assessment = self._build_assessment(confirmed, exclusions)
        result = DetectionResult(
            entities=entities,
            categories=dict(categories),
            processing_time_ms=round((time.time() - start) * 1000, 2),
            warnings=[],
            document_assessment=assessment,
        )
        classify_protection_level(result)
        return result

    def _normalize(self, text: str) -> str:
        text = (text or "").replace("\xa0", " ")
        text = re.sub(r"[ \t]+", " ", text)
        return text

    def _build_scopes(self, text: str) -> list[Scope]:
        scopes: list[Scope] = []
        offset = 0
        for idx, line in enumerate(text.splitlines()):
            raw = line.strip()
            if not raw:
                offset += len(line) + 1
                continue
            scopes.append(Scope(scope_id=f"line:{idx}", text=raw, offset=offset, scope_type="line"))
            offset += len(line) + 1
        if not scopes and text.strip():
            scopes.append(Scope(scope_id="line:0", text=text.strip(), offset=0, scope_type="line"))
        return scopes

    def _analyze_scope(self, scope: Scope) -> tuple[list[Evidence], list[str]]:
        text_low = scope.text.lower()
        evidences: list[Evidence] = []
        exclusions: list[str] = []

        if any(marker in text_low for marker in self.NEGATIVE_PLACEHOLDERS):
            return [], ["placeholder_template"]

        def has_ctx(words: list[str]) -> bool:
            return any(w in text_low for w in words)

        for m in self.SNILS_RE.finditer(scope.text):
            raw = m.group(0)
            digits = re.sub(r"\D", "", raw)
            if not self._valid_snils(digits):
                exclusions.append("snils_checksum_fail")
                continue
            if not has_ctx(self.GOV_CONTEXT["snils"]):
                exclusions.append("snils_without_context")
                continue
            evidences.append(self._ev("snils", "snils", raw, "STRONG", 0.97, m, scope, ["validator:snils_checksum", "context:snils_keyword"]))

        for m in self.INN_RE.finditer(scope.text):
            digits = m.group(0)
            if not self._valid_inn(digits):
                exclusions.append("inn_checksum_fail")
                continue
            if not has_ctx(self.GOV_CONTEXT["inn"]) and not self._looks_structured_field(scope.text):
                exclusions.append("inn_without_context")
                continue
            evidences.append(self._ev("inn", "inn", digits, "STRONG", 0.95, m, scope, ["validator:inn_checksum", "context:inn_or_field"]))

        for m in self.CARD_RE.finditer(scope.text):
            digits = re.sub(r"\D", "", m.group(0))
            if len(digits) < 16 or len(digits) > 19:
                exclusions.append("card_length_fail")
                continue
            if self._is_masked(scope.text[m.start():m.end()]):
                exclusions.append("card_masked")
                continue
            if not self._luhn(digits):
                exclusions.append("card_luhn_fail")
                continue
            evidences.append(self._ev("payment_card_number", "bank_card", digits, "STRONG", 0.96, m, scope, ["validator:luhn"]))

        for m in self.MRZ_RE.finditer(scope.text):
            candidate = m.group(0)
            if candidate.count("<") < 5:
                exclusions.append("mrz_shape_fail")
                continue
            evidences.append(self._ev("mrz", "mrz", candidate, "STRONG", 0.93, m, scope, ["validator:mrz_shape"]))

        for m in self.PASSPORT_RE.finditer(scope.text):
            if not has_ctx(self.GOV_CONTEXT["passport"]):
                exclusions.append("passport_without_context")
                continue
            evidences.append(self._ev("passport", "passport_rf", m.group(0), "STRONG", 0.92, m, scope, ["context:passport_keywords"]))

        account_hits = [m for m in self.ACCOUNT_RE.finditer(scope.text)]
        bik_hits = [m for m in self.BIK_RE.finditer(scope.text)]
        if account_hits:
            if bik_hits and has_ctx(self.ACCOUNT_CONTEXT):
                for m in account_hits:
                    evidences.append(self._ev("bank_account", "account_bik_pair", m.group(0), "STRONG", 0.91, m, scope, ["context:bik_nearby"]))
            else:
                exclusions.append("account_without_bik")

        for m in self.EMAIL_RE.finditer(scope.text):
            email = m.group(0).lower()
            local = email.split("@", 1)[0]
            if local in self.GENERIC_EMAIL_LOCALPARTS and not has_ctx(self.PERSON_CONTEXT):
                exclusions.append("generic_email")
                continue
            if has_ctx(self.PERSON_CONTEXT) or self._looks_structured_field(scope.text):
                evidences.append(self._ev("email", "email", email, "MEDIUM", 0.72, m, scope, ["context:person_or_structured"]))
            else:
                exclusions.append("email_without_person_context")

        for m in self.PHONE_RE.finditer(scope.text):
            normalized_phone = self._normalize_phone(m.group(0))
            if has_ctx(self.PERSON_CONTEXT) or self._looks_structured_field(scope.text):
                evidences.append(self._ev("phone", "phone_ru", normalized_phone, "MEDIUM", 0.7, m, scope, ["context:person_or_structured"]))
            else:
                exclusions.append("phone_without_person_context")

        for m in self.DOB_RE.finditer(scope.text):
            value = m.group(0)
            if not has_ctx(self.DOB_CONTEXT):
                exclusions.append("date_without_dob_context")
                continue
            if not self._plausible_dob(value):
                exclusions.append("dob_age_implausible")
                continue
            evidences.append(self._ev("date_of_birth", "date_of_birth", value, "MEDIUM", 0.68, m, scope, ["context:dob_keyword", "validator:age_range"]))

        for m in self.FIO_RE.finditer(scope.text):
            value = m.group(0)
            if any(tok in value.lower() for tok in self.ORG_TOKENS):
                exclusions.append("organization_like_name")
                continue
            evidences.append(self._ev("person_name", "fio", value, "WEAK", 0.45, m, scope, ["pattern:fio"]))

        if has_ctx(self.ADDRESS_CONTEXT):
            pseudo_match = re.search(r".", scope.text)
            if pseudo_match:
                evidences.append(self._ev("address", "address_personal", scope.text, "MEDIUM", 0.66, pseudo_match, scope, ["context:personal_address"]))

        return evidences, exclusions

    def _classify_file(self, evidences: list[Evidence]) -> list[Evidence]:
        by_scope: dict[str, list[Evidence]] = defaultdict(list)
        for ev in evidences:
            by_scope[ev.scope_id].append(ev)

        strong = [e for e in evidences if e.strength == "STRONG"]
        if strong:
            return self._dedup(strong + self._linked_medium(by_scope, strong))

        confirmed: list[Evidence] = []
        for scope_evidences in by_scope.values():
            mediums = [e for e in scope_evidences if e.strength == "MEDIUM"]
            if len(mediums) >= self.config.MIN_MEDIUM_PER_SCOPE:
                confirmed.extend(mediums)
                confirmed.extend([e for e in scope_evidences if e.entity_type == "person_name"])

        return self._dedup(confirmed)

    def _linked_medium(self, by_scope: dict[str, list[Evidence]], strong: list[Evidence]) -> list[Evidence]:
        strong_scopes = {e.scope_id for e in strong}
        linked: list[Evidence] = []
        for scope_id in strong_scopes:
            for ev in by_scope.get(scope_id, []):
                if ev.strength == "MEDIUM":
                    linked.append(ev)
        return linked

    def _dedup(self, evidences: list[Evidence]) -> list[Evidence]:
        seen: set[tuple[str, str, str]] = set()
        deduped: list[Evidence] = []
        for ev in evidences:
            key = (ev.scope_id, ev.entity_type, ev.masked_value)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(ev)
        return deduped

    def _build_assessment(self, confirmed: list[Evidence], exclusions: dict[str, int]) -> dict:
        detected_categories = sorted({e.entity_type for e in confirmed})
        strong_count = sum(1 for e in confirmed if e.strength == "STRONG")
        medium_count = sum(1 for e in confirmed if e.strength == "MEDIUM")
        has_pd = bool(confirmed)
        if strong_count:
            confidence = "very_high"
            score = min(100, 70 + strong_count * 8 + medium_count * 4)
            reason = "Обнаружены строго валидированные идентификаторы"
        elif medium_count >= 2:
            confidence = "medium"
            score = min(100, 35 + medium_count * 10)
            reason = "Подтверждены минимум 2 средних сигнала в одном локальном scope"
        else:
            confidence = "no_pd_or_weak"
            score = 0
            reason = "Недостаточно подтверждений для precision-first классификации"

        diagnostics = {
            "excluded_candidates": dict(exclusions),
            "top_false_positive_sources": sorted(exclusions.items(), key=lambda x: x[1], reverse=True)[:10],
            "evidence_chain": [
                {
                    "scope": e.scope_id,
                    "type": e.entity_type,
                    "strength": e.strength,
                    "reasons": e.reasons,
                    "masked": e.masked_value,
                }
                for e in confirmed[:50]
            ],
        }

        return {
            "has_personal_data": has_pd,
            "overall_confidence": confidence,
            "overall_risk_score": score,
            "detected_categories": detected_categories,
            "legal_buckets_present": sorted({e.legal_bucket for e in confirmed}),
            "strongest_category": detected_categories[0] if detected_categories else None,
            "short_reason": reason,
            "long_reason": reason,
            "hit_count": len(confirmed),
            "diagnostics": diagnostics,
        }

    def _to_entity(self, ev: Evidence, source_text: str) -> PDEntity:
        ctx_start = max(0, ev.start - self.context_window)
        ctx_end = min(len(source_text), ev.end + self.context_window)
        context = source_text[ctx_start:ctx_end]
        return PDEntity(
            entity_type=ev.entity_type,
            value=ev.masked_value,
            confidence=ev.confidence,
            start_pos=ev.start,
            end_pos=ev.end,
            context=context,
            source="rule",
            metadata={
                "category": ev.entity_type,
                "subtype": ev.subtype,
                "matched_text_redacted": ev.masked_value,
                "normalized_value_if_safe": ev.masked_value,
                "reasons": ev.reasons,
                "strength": ev.strength,
                "legal_bucket": ev.legal_bucket,
                "value_hash": hashlib.sha256(ev.value.encode("utf-8")).hexdigest()[:16],
            },
        )

    def _ev(self, entity_type: str, subtype: str, raw_value: str, strength: str, confidence: float, match: re.Match, scope: Scope, reasons: list[str]) -> Evidence:
        return Evidence(
            entity_type=entity_type,
            subtype=subtype,
            value=raw_value,
            masked_value=self._mask(entity_type, raw_value),
            strength=strength,
            confidence=confidence,
            start=scope.offset + match.start(),
            end=scope.offset + match.end(),
            scope_id=scope.scope_id,
            reasons=reasons,
        )

    def _looks_structured_field(self, text: str) -> bool:
        return ":" in text or "=" in text or "\t" in text

    def _mask(self, entity_type: str, value: str) -> str:
        digits = re.sub(r"\D", "", value)
        if entity_type in {"snils", "inn", "passport", "payment_card_number", "bank_account"} and digits:
            if len(digits) <= 4:
                return "*" * len(digits)
            return f"{digits[:2]}***{digits[-2:]}"
        if entity_type == "email" and "@" in value:
            local, domain = value.split("@", 1)
            return f"{local[:1]}***@{domain}"
        if entity_type == "phone" and digits:
            return f"+7***{digits[-4:]}"
        return value[:2] + "***" if len(value) > 3 else "***"

    def _normalize_phone(self, phone: str) -> str:
        digits = re.sub(r"\D", "", phone)
        if digits.startswith("8"):
            digits = "7" + digits[1:]
        return "+" + digits

    def _is_masked(self, value: str) -> bool:
        return "*" in value or value.count("X") >= 4

    def _luhn(self, digits: str) -> bool:
        total = 0
        reverse_digits = digits[::-1]
        for i, ch in enumerate(reverse_digits):
            n = int(ch)
            if i % 2 == 1:
                n *= 2
                if n > 9:
                    n -= 9
            total += n
        return total % 10 == 0

    def _valid_snils(self, digits: str) -> bool:
        if len(digits) != 11:
            return False
        number = digits[:9]
        control = int(digits[9:])
        if int(number) <= 1001998:
            return control == int(number) % 101
        checksum = sum(int(number[i]) * (9 - i) for i in range(9))
        if checksum < 100:
            expected = checksum
        elif checksum in (100, 101):
            expected = 0
        else:
            expected = checksum % 101
            if expected == 100:
                expected = 0
        return expected == control

    def _valid_inn(self, digits: str) -> bool:
        if len(digits) == 10:
            coeffs = [2, 4, 10, 3, 5, 9, 4, 6, 8]
            n10 = sum(int(digits[i]) * coeffs[i] for i in range(9)) % 11 % 10
            return n10 == int(digits[9])
        if len(digits) == 12:
            c11 = [7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
            c12 = [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
            n11 = sum(int(digits[i]) * c11[i] for i in range(10)) % 11 % 10
            n12 = sum(int(digits[i]) * c12[i] for i in range(11)) % 11 % 10
            return n11 == int(digits[10]) and n12 == int(digits[11])
        return False

    def _plausible_dob(self, dob: str) -> bool:
        parts = re.split(r"[\.\-/]", dob)
        if len(parts) != 3:
            return False
        day, month, year = map(int, parts)
        if not (1900 <= year <= 2012):
            return False
        return 1 <= day <= 31 and 1 <= month <= 12
