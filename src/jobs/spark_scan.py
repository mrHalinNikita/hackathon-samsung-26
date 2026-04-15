import os
import sys
from pathlib import Path
from pyspark.sql import SparkSession
import structlog

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.spark.job import run_spark_processing
from src.scanner.file_walker import walk_directory

logger = structlog.get_logger("spark_scan_job")


def main():
    logger.info("Starting Spark Scan Job...", project_root=str(PROJECT_ROOT))

    spark = SparkSession.builder \
        .appName("pd-scanner-k8s-job-local") \
        .master("local[1]") \
        .config("spark.driver.memory", os.getenv("SPARK_DRIVER_MEMORY", "1g")) \
        .config("spark.executor.memory", os.getenv("SPARK_EXECUTOR_MEMORY", "1g")) \
        .config("spark.python.worker.memory", os.getenv("SPARK_PYTHON_WORKER_MEMORY", "512m")) \
        .config("spark.python.worker.memory.overhead", "0.2") \
        .config("spark.default.parallelism", os.getenv("SPARK_DEFAULT_PARALLELISM", "2")) \
        .config("spark.sql.shuffle.partitions", "2") \
        .config("spark.python.worker.reuse", "true") \
        .config("spark.python.worker.faulthandler.enabled", "true") \
        .config("spark.ui.port", "4040") \
        .getOrCreate()

    try:
        scan_root = os.getenv("SCAN_ROOT_PATH", "/data/test_dataset")
        logger.info("Scanning directory", path=scan_root)

        if not Path(scan_root).exists():
            logger.error("Scan root path does not exist!", path=scan_root)
            sys.exit(1)

        files = []
        for f_info in walk_directory(scan_root, calculate_hash=False):
            files.append(str(f_info.path))

        if not files:
            logger.warning("No files found in scan root.")
            sys.exit(0)

        logger.info(f"Found {len(files)} files. Dispatching to Spark...")

        results = run_spark_processing(spark, files)

        success = sum(1 for r in results if r.get("status") == "success")
        pd_found = sum(1 for r in results if r.get("has_pd"))
        
        logger.info("Job completed successfully.",
                    total_files=len(files),
                    successfully_processed=success,
                    personal_data_found=pd_found)

    except Exception as e:
        logger.error("Job failed!", error=str(e), error_type=type(e).__name__)
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)
    finally:
        spark.stop()
        logger.info("Spark session stopped.")


if __name__ == "__main__":
    main()