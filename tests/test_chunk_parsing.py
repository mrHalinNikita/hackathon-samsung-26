import unittest
import os
from pathlib import Path


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

from src.parsers.base import BaseParser, ParsedContent


class DummyParser(BaseParser):
    @property
    def supported_extensions(self) -> list[str]:
        return [".txt"]

    async def parse(self, filepath: Path) -> ParsedContent:
        return ParsedContent(
            text="abcdefghij",
            metadata={"path": str(filepath)},
            errors=[],
            word_count=1,
            char_count=10,
        )


class ChunkParsingTests(unittest.IsolatedAsyncioTestCase):
    async def test_parse_chunks_fallback_returns_single_chunk(self):
        parser = DummyParser()
        chunks = [chunk async for chunk in parser.parse_chunks(Path("/tmp/file.txt"))]

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].text, "abcdefghij")
        self.assertTrue(chunks[0].is_last)
        self.assertEqual(chunks[0].offset_start, 0)
        self.assertEqual(chunks[0].offset_end, 10)

    async def test_iter_text_chunks_with_overlap(self):
        parser = DummyParser()
        chunks = list(parser._iter_text_chunks("abcdefghij", chunk_size=4, overlap=1))

        self.assertEqual(
            chunks,
            [
                ("abcd", 0, 4),
                ("defg", 3, 7),
                ("ghij", 6, 10),
            ],
        )


if __name__ == "__main__":
    unittest.main()