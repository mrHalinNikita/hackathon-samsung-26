from pyspark.sql import SparkSession
import structlog

from src.config import settings

logger = structlog.get_logger("spark")


def init_spark_session(
    app_name: str,
    master: str = "local[*]",
    driver_memory: str = "2g",
    executor_memory: str = "2g",
    executor_cores: int = 2,
) -> SparkSession:
    
    logger.debug(
        "Initialization SparkSession",
        app_name=app_name,
        master=master,
        driver_memory=driver_memory,
    )
    
    session = SparkSession.builder \
        .appName(app_name) \
        .master(master) \
        .config("spark.driver.memory", driver_memory) \
        .config("spark.executor.memory", executor_memory) \
        .config("spark.executor.cores", executor_cores) \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
        .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer") \
        .config("spark.sql.execution.arrow.pyspark.enabled", "true") \
        .getOrCreate()
    
    logger.info("SparkSession init", master=master)
    return session


def check_spark_connection(spark: SparkSession) -> bool:

    logger.debug("Checking the connection to Spark")
    
    try:
        result = spark.range(5).count()
        logger.info("Connection to Spark verified", test_result=result)
        return True
    except Exception as e:
        logger.error("Failed to connect to Spark", error=str(e), error_type=type(e).__name__,)
        raise