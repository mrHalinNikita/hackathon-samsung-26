import sys
import os
import gc
import time
from pathlib import Path

os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable

sys.path.append(str(Path(__file__).parent.parent.parent))

from pyspark.sql import SparkSession
import structlog

logger = structlog.get_logger("spark_worker")

_worker_detector = None

def _get_worker_detector():
    global _worker_detector

    if _worker_detector is None:
        from src.detectors import EnsembleDetector, default_config

        _worker_detector = EnsembleDetector(default_config)
        logger.debug("EnsembleDetector (Regex + NLP) initialized for worker")
    return _worker_detector

def process_file_udf(file_path: str) -> dict:

    from src.parsers import ParserFactory
    import asyncio

    old_stdout, old_stderr = sys.stdout, sys.stderr
    sys.stdout = open(os.devnull, "w")
    sys.stderr = open(os.devnull, "w")

    try:
        path_obj = Path(file_path)
        if not path_obj.exists():
            return {"status": "error", "path": file_path, "message": "File not found"}

        if path_obj.stat().st_size > 100_000_000:
            return {"status": "skipped_large", "path": file_path, "message": "File too large"}

        parsed_content = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                parsed_content = loop.run_until_complete(ParserFactory.parse_file(path_obj))
            finally:
                loop.close()
        except Exception as parse_err:
            return {"status": "parse_error", "path": file_path, "message": str(parse_err)[:200]}

        if not parsed_content or not parsed_content.text:
            return {"status": "empty", "path": file_path}

        detector = _get_worker_detector()
        pd_result = detector.detect(parsed_content.text)

        result = {
            "status": "success",
            "path": file_path,
            "has_pd": pd_result.has_sensitive_data,
            "pd_categories": pd_result.categories,
            "pd_entity_count": pd_result.entity_count,
            "pd_processing_ms": pd_result.processing_time_ms,
            "text_length": len(parsed_content.text),
            "snippet": parsed_content.text[:300],
        }

        del parsed_content, pd_result, detector
        gc.collect()
        return result

    except TimeoutError as e:
        return {"status": "timeout", "path": file_path, "error": str(e)}
    except Exception as e:
        return {"status": "critical_error", "path": file_path, "error": str(e)[:200]}
    finally:
        sys.stdout, sys.stderr = old_stdout, old_stderr


def run_spark_processing(spark: SparkSession, file_paths: list[str]):

    spark.sparkContext.setLogLevel("WARN")
    logger.info("Starting Spark Processing Job", files_count=len(file_paths))

    BATCH_SIZE = 3
    MAX_PARALLEL = 2

    all_results = []
    total_batches = (len(file_paths) + BATCH_SIZE - 1) // BATCH_SIZE

    for batch_idx in range(total_batches):
        start_idx = batch_idx * BATCH_SIZE
        end_idx = min(start_idx + BATCH_SIZE, len(file_paths))
        batch = file_paths[start_idx:end_idx]

        heavy = [f for f in batch if Path(f).stat().st_size > 50_000_000]
        if heavy:
            for hf in heavy:
                all_results.append({"status": "skipped_heavy", "path": hf})
            batch = [f for f in batch if f not in heavy]
            if not batch:
                continue

        logger.info(f"Processing batch {batch_idx + 1}/{total_batches}", batch_size=len(batch))

        rdd = spark.sparkContext.parallelize(batch, numSlices=min(MAX_PARALLEL, len(batch)))
        batch_results = rdd.map(process_file_udf).collect()
        rdd.unpersist(blocking=True)

        all_results.extend(batch_results)

        gc.collect()
        time.sleep(0.5)

    stats = {
        "success": 0, "parse_error": 0, "pd_found": 0, "critical_error": 0, "empty": 0, "error": 0, "skipped": 0
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
                categories=res["pd_categories"],
                entities=res.get("pd_entity_count", 0),
                pd_time_ms=res.get("pd_processing_ms", 0)
            )

    stats["total_entities_found"] = total_entities
    stats["avg_pd_processing_ms"] = round(total_pd_time_ms / max(1, stats["pd_found"]), 2)

    logger.info("Spark Job Finished", stats=stats)
    return all_results