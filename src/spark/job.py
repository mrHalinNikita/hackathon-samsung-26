import sys
import os
import gc
from pathlib import Path

os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable

sys.path.append(str(Path(__file__).parent.parent.parent))

from pyspark.sql import SparkSession
import structlog

logger = structlog.get_logger("spark_worker")


def process_file_udf(file_path: str) -> dict:

    from src.parsers import ParserFactory
    from src.detectors import detect_personal_data
    import asyncio

    old_stdout, old_stderr = sys.stdout, sys.stderr
    sys.stdout = open(os.devnull, "w")
    sys.stderr = open(os.devnull, "w")

    try:
        path_obj = Path(file_path)
        if not path_obj.exists():
            return {"status": "error", "path": file_path, "message": "File not found"}

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

        pd_result = detect_personal_data(parsed_content.text)

        result = {
            "status": "success",
            "path": file_path,
            "has_pd": pd_result.get("detected", False),
            "pd_categories": pd_result.get("categories", {}),
            "text_length": len(parsed_content.text),
            "snippet": parsed_content.text[:300],
        }

        del parsed_content, pd_result
        gc.collect()

        return result

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

        logger.info(
            f"Processing batch {batch_idx + 1}/{total_batches}",
            batch_size=len(batch),
            files=[Path(f).name for f in batch[:3]] + (["..."] if len(batch) > 3 else []),
        )

        rdd = spark.sparkContext.parallelize(batch, numSlices=min(MAX_PARALLEL, len(batch)))
        batch_results = rdd.map(process_file_udf).collect()

        rdd.unpersist(blocking=True)

        all_results.extend(batch_results)

        gc.collect()

        import time
        time.sleep(0.5)

    stats = {"success": 0, "parse_error": 0, "pd_found": 0, "critical_error": 0, "empty": 0, "error": 0}
    for res in all_results:
        status = res.get("status", "unknown")
        stats[status] = stats.get(status, 0) + 1
        if res.get("has_pd"):
            stats["pd_found"] += 1
            logger.warning("PD Detected!", path=res["path"], categories=res["pd_categories"])

    logger.info("Spark Job Finished", stats=stats)
    return all_results