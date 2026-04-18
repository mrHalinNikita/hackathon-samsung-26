import sys
import os
import gc
import time
from collections import defaultdict
from pathlib import Path

os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable

sys.path.append(str(Path(__file__).parent.parent.parent))

from pyspark.sql import SparkSession
import structlog

from src.config import settings
from src.detectors.base import DetectionResult, classify_protection_level

logger = structlog.get_logger("spark_worker")

_worker_detector = None


def _get_worker_detector():
    global _worker_detector

    if _worker_detector is None:
        from src.detectors import EnsembleDetector, default_config

        _worker_detector = EnsembleDetector(default_config)
        logger.debug("EnsembleDetector (Regex + NLP) initialized for worker")
    return _worker_detector


def _status_rank(status: str) -> int:
    ranks = {
        "success": 0,
        "empty": 1,
        "parse_error": 2,
        "critical_error": 3,
    }
    return ranks.get(status, 1)


def _make_partial(file_path: str) -> dict:
    return {
        "file_hash": None,
        "status": "success",
        "chunk_count": 0,
        "text_length": 0,
        "pd_processing_ms": 0.0,
        "entity_keys": set(),
        "legal_buckets": set(),
        "detected_categories": set(),
        "overall_risk_score": 0,
        "overall_confidence": "no_pd_or_weak",
        "strongest_category": None,
        "short_reason": "",
        "long_reason": "",
        "snippet": "",
        "warnings": [],
        "errors": [],
        "path": file_path,
    }


def _message_limit() -> int:
    configured = getattr(settings, "CHUNK_MAX_MESSAGES_PER_FILE", 100)
    return max(10, int(configured))


def _normalize_entity_value(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _build_entity_key(entity_type: str, raw_value: str, global_start: int | None) -> tuple:
    """
    Формирует ключ дедупликации сущностей между overlap-чанками.
    """

    window = getattr(settings, "CHUNK_ENTITY_DEDUP_WINDOW_CHARS", 25)
    if window <= 0:
        window = 25

    position_bucket = None if global_start is None else int(global_start) // window
    normalized_value = _normalize_entity_value(raw_value)
    return entity_type, normalized_value, position_bucket


def _merge_partials(left: dict, right: dict) -> dict:
    merged = _make_partial(left.get("path") or right.get("path"))

    merged["file_hash"] = left.get("file_hash") or right.get("file_hash")
    merged["status"] = (
        left["status"]
        if _status_rank(left.get("status", "empty")) >= _status_rank(right.get("status", "empty"))
        else right["status"]
    )
    merged["chunk_count"] = left.get("chunk_count", 0) + right.get("chunk_count", 0)
    merged["text_length"] = left.get("text_length", 0) + right.get("text_length", 0)
    merged["pd_processing_ms"] = left.get("pd_processing_ms", 0.0) + right.get("pd_processing_ms", 0.0)
    merged["entity_keys"] = set(left.get("entity_keys", set())) | set(right.get("entity_keys", set()))
    merged["legal_buckets"] = set(left.get("legal_buckets", set())) | set(right.get("legal_buckets", set()))
    merged["detected_categories"] = set(left.get("detected_categories", set())) | set(right.get("detected_categories", set()))
    if right.get("overall_risk_score", 0) > left.get("overall_risk_score", 0):
        merged["overall_risk_score"] = right.get("overall_risk_score", 0)
        merged["overall_confidence"] = right.get("overall_confidence", "no_pd_or_weak")
        merged["strongest_category"] = right.get("strongest_category")
        merged["short_reason"] = right.get("short_reason", "")
        merged["long_reason"] = right.get("long_reason", "")
    else:
        merged["overall_risk_score"] = left.get("overall_risk_score", 0)
        merged["overall_confidence"] = left.get("overall_confidence", "no_pd_or_weak")
        merged["strongest_category"] = left.get("strongest_category")
        merged["short_reason"] = left.get("short_reason", "")
        merged["long_reason"] = left.get("long_reason", "")
    merged["snippet"] = left.get("snippet") or right.get("snippet") or ""

    left_warnings = left.get("warnings", [])
    right_warnings = right.get("warnings", [])
    merged["warnings"] = (left_warnings + right_warnings)[:_message_limit()]

    left_errors = left.get("errors", [])
    right_errors = right.get("errors", [])
    merged["errors"] = (left_errors + right_errors)[:_message_limit()]

    return merged


def _finalize_result(file_path: str, partial: dict) -> dict:
    categories = defaultdict(int)
    for entity_type, _value, _bucket in partial.get("entity_keys", set()):
        categories[entity_type] += 1

    detection = DetectionResult(categories=dict(categories))
    classify_protection_level(detection)

    entity_count = sum(categories.values())
    result = {
        "status": partial.get("status", "empty"),
        "path": file_path,
        "file_hash": partial.get("file_hash"),
        "has_pd": detection.has_sensitive_data or partial.get("overall_risk_score", 0) >= 20,
        "protection_level": detection.protection_level,
        "protection_level_reason": detection.protection_level_reason,
        "pd_categories": dict(categories),
        "pd_entity_count": entity_count,
        "pd_processing_ms": round(partial.get("pd_processing_ms", 0.0), 2),
        "text_length": partial.get("text_length", 0),
        "snippet": partial.get("snippet", ""),
        "chunk_count": partial.get("chunk_count", 0),
        "warnings": partial.get("warnings", []),
        "errors": partial.get("errors", []),
        "document_assessment": {
            "has_personal_data": detection.has_sensitive_data or partial.get("overall_risk_score", 0) >= 20,
            "overall_confidence": partial.get("overall_confidence", "no_pd_or_weak"),
            "overall_risk_score": partial.get("overall_risk_score", 0),
            "legal_buckets_present": sorted(partial.get("legal_buckets", set())),
            "detected_categories": sorted(partial.get("detected_categories", set())),
            "short_reason": partial.get("short_reason", ""),
            "long_reason": partial.get("long_reason", ""),
            "hit_count": entity_count,
            "strongest_category": partial.get("strongest_category"),
        },
    }

    # Если chunk-ов не было совсем, считаем файл пустым.
    if partial.get("chunk_count", 0) == 0 and result["status"] == "success":
        result["status"] = "empty"

    return result


def process_file_chunks_udf(file_path: str) -> list[tuple[str, dict]]:
    """
    Обрабатывает файл в режиме chunk-стрима и возвращает partial-данные
    для последующей reduceByKey-агрегации по file_path.
    """

    from src.parsers import ParserFactory
    import asyncio

    try:
        path_obj = Path(file_path)
        if not path_obj.exists():
            partial = _make_partial(file_path)
            partial["status"] = "parse_error"
            partial["errors"].append("File not found")
            return [(file_path, partial)]

        # Грубая отсечка на экстремально большие файлы.
        if path_obj.stat().st_size > 500_000_000:
            partial = _make_partial(file_path)
            partial["status"] = "parse_error"
            partial["errors"].append("File too large for current worker limits")
            return [(file_path, partial)]

        detector = _get_worker_detector()
        partial = _make_partial(file_path)
        emitted_any = False

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            async def _consume_chunks():
                nonlocal emitted_any, partial

                async for chunk in ParserFactory.parse_file_chunks(path_obj):
                    emitted_any = True
                    partial["chunk_count"] += 1
                    partial["file_hash"] = partial.get("file_hash") or chunk.file_hash
                    partial["text_length"] += chunk.char_count

                    if chunk.errors:
                        partial["warnings"].extend(chunk.errors[:3])

                    if not chunk.text.strip():
                        continue

                    if not partial["snippet"]:
                        partial["snippet"] = chunk.text[:300]

                    pd_result = detector.detect(chunk.text)
                    partial["pd_processing_ms"] += pd_result.processing_time_ms
                    partial["warnings"].extend(pd_result.warnings[:3])
                    assessment = pd_result.document_assessment or {}
                    partial["overall_risk_score"] = max(
                        partial.get("overall_risk_score", 0),
                        assessment.get("overall_risk_score", 0),
                    )
                    if partial["overall_risk_score"] == assessment.get("overall_risk_score", 0):
                        partial["overall_confidence"] = assessment.get("overall_confidence", "no_pd_or_weak")
                        partial["strongest_category"] = assessment.get("strongest_category")
                        partial["short_reason"] = assessment.get("short_reason", "")
                        partial["long_reason"] = assessment.get("long_reason", "")
                    partial["legal_buckets"].update(assessment.get("legal_buckets_present", []))
                    partial["detected_categories"].update(assessment.get("detected_categories", []))

                    for entity in pd_result.entities:
                        local_start = entity.start_pos or 0
                        global_start = chunk.offset_start + local_start
                        partial["entity_keys"].add(
                            _build_entity_key(
                                entity.entity_type,
                                entity.value,
                                global_start,
                            )
                        )

            loop.run_until_complete(_consume_chunks())
        finally:
            loop.close()

        if not emitted_any:
            partial["status"] = "empty"

        return [(file_path, partial)]
    
    except Exception as e:
        partial = _make_partial(file_path)
        partial["status"] = "critical_error"
        partial["errors"].append(str(e)[:200])
        return [(file_path, partial)]


def run_spark_processing(spark: SparkSession, file_paths: list[str]):
    spark.sparkContext.setLogLevel("WARN")
    logger.info("Starting Spark Processing Job", files_count=len(file_paths))

    BATCH_SIZE = 8
    MAX_PARALLEL = 4

    all_results = []
    total_batches = (len(file_paths) + BATCH_SIZE - 1) // BATCH_SIZE

    for batch_idx in range(total_batches):
        start_idx = batch_idx * BATCH_SIZE
        end_idx = min(start_idx + BATCH_SIZE, len(file_paths))
        batch = file_paths[start_idx:end_idx]

        logger.info(f"Processing batch {batch_idx + 1}/{total_batches}", batch_size=len(batch))

        rdd = spark.sparkContext.parallelize(batch, numSlices=min(MAX_PARALLEL, len(batch)))
        partials_rdd = rdd.flatMap(process_file_chunks_udf)
        aggregated_rdd = partials_rdd.reduceByKey(_merge_partials)
        batch_results = aggregated_rdd.map(lambda kv: _finalize_result(kv[0], kv[1])).collect()

        all_results.extend(batch_results)

        rdd.unpersist(blocking=True)
        gc.collect()
        time.sleep(0.2)

    stats = {
        "success": 0,
        "parse_error": 0,
        "pd_found": 0,
        "critical_error": 0,
        "empty": 0,
        "error": 0,
        "skipped": 0,
    }
    total_entities = 0
    total_pd_time_ms = 0.0

    for res in all_results:
        status = res.get("status", "unknown")
        if status.startswith("skipped"):
            stats["skipped"] += 1
        else:
            stats[status] = stats.get(status, 0) + 1

        if res.get("has_pd"):
            stats["pd_found"] += 1
            total_entities += res.get("pd_entity_count", 0)
            total_pd_time_ms += res.get("pd_processing_ms", 0)

            logger.warning(
                "PD Detected!",
                path=Path(res["path"]).name,
                protection_level=res.get("protection_level"),
                protection_reason=res.get("protection_level_reason"),
                categories=res["pd_categories"],
                entities=res.get("pd_entity_count", 0),
                pd_time_ms=res.get("pd_processing_ms", 0),
                chunks=res.get("chunk_count", 0),
            )

    stats["total_entities_found"] = total_entities
    stats["avg_pd_processing_ms"] = round(total_pd_time_ms / max(1, stats["pd_found"]), 2)

    logger.info("Spark Job Finished", stats=stats)
    return all_results


def _finalize_kv(item: tuple[str, dict]) -> dict:
    path, partial = item
    return _finalize_result(path, partial)