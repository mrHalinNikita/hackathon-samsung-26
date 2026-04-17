import os
import unittest


def _set_required_env():
    required = {
        "APP_NAME": "pd-scanner",
        "APP_ENV": "test",
        "LOG_LEVEL": "INFO",
        "POSTGRES_HOST": "localhost",
        "POSTGRES_PORT": "5432",
        "POSTGRES_DB": "pd",
        "POSTGRES_USER": "user",
        "POSTGRES_PASSWORD": "pass",
        "POSTGRES_SSLMODE": "disable",
        "REDIS_HOST": "localhost",
        "REDIS_PORT": "6379",
        "REDIS_PASSWORD": "pass",
        "REDIS_DB": "0",
        "KAFKA_BROKER": "localhost",
        "KAFKA_PORT": "9092",
        "KAFKA_TOPIC_RAW_FILES": "raw",
        "KAFKA_TOPIC_EXTRACTED_TEXT": "extracted",
        "KAFKA_TOPIC_RESULTS": "results",
        "SCAN_ROOT_PATH": ".",
        "SCAN_MAX_FILE_SIZE_MB": "100",
        "OCR_HOST": "localhost",
        "OCR_PORT": "8001",
        "OCR_TESSERACT_LANGS": "rus",
        "OCR_MAX_IMAGE_SIZE_MB": "10",
        "REPORT_OUTPUT_PATH": "./reports/scan_report.csv",
    }
    for key, value in required.items():
        os.environ.setdefault(key, value)


_set_required_env()

from src.spark.job import _build_entity_key, _finalize_result, _make_partial, _merge_partials


class SparkDedupTests(unittest.TestCase):
    def test_build_entity_key_normalizes_value_and_bucket(self):
        key_a = _build_entity_key("email", " User@Test.com ", 101)
        key_b = _build_entity_key("email", "user@test.com", 119)
        self.assertEqual(key_a, key_b)

    def test_merge_partials_deduplicates_entity_keys(self):
        left = _make_partial("/tmp/demo.txt")
        right = _make_partial("/tmp/demo.txt")

        left["entity_keys"].add(("email", "user@test.com", 4))
        right["entity_keys"].add(("email", "user@test.com", 4))

        merged = _merge_partials(left, right)
        self.assertEqual(len(merged["entity_keys"]), 1)

    def test_finalize_result_counts_unique_categories(self):
        partial = _make_partial("/tmp/demo.txt")
        partial["entity_keys"].add(("email", "user1@test.com", 1))
        partial["entity_keys"].add(("email", "user2@test.com", 2))
        partial["entity_keys"].add(("phone", "+79990000000", 3))
        partial["chunk_count"] = 3

        result = _finalize_result("/tmp/demo.txt", partial)
        self.assertEqual(result["pd_categories"]["email"], 2)
        self.assertEqual(result["pd_categories"]["phone"], 1)
        self.assertEqual(result["pd_entity_count"], 3)


if __name__ == "__main__":
    unittest.main()