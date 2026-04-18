from pathlib import Path
import json
import structlog
from typing import Optional

from src.parsers import ParserFactory, ParsedContent
from src.infrastructure import init_kafka_producer
from src.detectors import detect_personal_data

logger = structlog.get_logger("processor")


class FileProcessor:
    
    def __init__(self, kafka_bootstrap: str, output_topic: str):
        self.kafka_bootstrap = kafka_bootstrap
        self.output_topic = output_topic
        self._producer = None
    
    def _get_producer(self):
        if self._producer is None:
            self._producer = init_kafka_producer(self.kafka_bootstrap)
        return self._producer
    
    async def process(self, file_info: dict) -> dict:

        filepath = Path(file_info["path"])
        file_hash = file_info.get("file_hash")
        
        logger.info(
            "Starting file processing",
            path=str(filepath),
            hash=file_hash,
            extension=file_info.get("extension"),
        )
        
        parsed = await ParserFactory.parse_file(filepath)
        
        if parsed is None or parsed.is_empty:
            logger.warning(
                "No content extracted from file",
                path=str(filepath),
                errors=parsed.errors if parsed else ["No parser found"],
            )
            return {
                "file_hash": file_hash,
                "path": str(filepath),
                "status": "failed",
                "error": "No content extracted",
                "errors": parsed.errors if parsed else ["No parser found"],
            }
        
        logger.debug(
            "Content extracted",
            path=str(filepath),
            char_count=parsed.char_count,
            word_count=parsed.word_count,
        )
        
        pd_detection = await self._detect_pd(parsed.text)
        
        result = {
            "file_hash": file_hash,
            "path": str(filepath),
            "status": "success",
            "extracted_text": parsed.text[:10000],
            "text_truncated": len(parsed.text) > 10000,
            "metadata": {
                **parsed.metadata,
                "word_count": parsed.word_count,
                "char_count": parsed.char_count,
            },
            "personal_data": pd_detection,
            "processing_errors": parsed.errors,
        }
        
        await self._send_result(result)
        
        logger.info(
            "File processing completed",
            path=str(filepath),
            status=result["status"],
            pd_categories=list(pd_detection.get("categories", {}).keys()),
        )
        
        return result
    
    async def _detect_pd(self, text: str) -> dict:
        return detect_personal_data(text)
    
    async def _send_result(self, result: dict) -> None:

        producer = self._get_producer()
        
        try:
            key = result["file_hash"] or result["path"]
            value = json.dumps(result, ensure_ascii=False).encode("utf-8")
            
            producer.produce(
                self.output_topic,
                key=key,
                value=value,
                callback=self._delivery_callback,
            )
            producer.poll(0)
            
        except Exception as e:
            logger.error(
                "Failed to send result to Kafka",
                error=str(e),
                result_path=result.get("path"),
            )
            raise
    
    def _delivery_callback(self, err, msg):

        if err:
            logger.error("Result delivery failed", error=err)
        else:
            logger.debug(
                "Result delivered",
                topic=msg.topic(),
                partition=msg.partition(),
                offset=msg.offset(),
            )
    
    def close(self) -> None:

        if self._producer:
            self._producer.flush(timeout=10)
            self._producer.close()
            self._producer = None