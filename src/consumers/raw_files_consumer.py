import structlog
from confluent_kafka import Message

from src.consumers.base import BaseConsumer
from src.consumers.processor import FileProcessor
from src.config import settings

logger = structlog.get_logger("raw_files_consumer")


class RawFilesConsumer(BaseConsumer):
    
    def __init__(
        self,
        kafka_bootstrap: str,
        group_id: str = "pd-scanner-parser-group",
        input_topic: str = None,
        output_topic: str = None,
    ):
        super().__init__(
            bootstrap_servers=kafka_bootstrap,
            group_id=group_id,
            topic=input_topic or settings.KAFKA_TOPIC_RAW_FILES,
            enable_auto_commit=True,
        )
        
        self.processor = FileProcessor(
            kafka_bootstrap=kafka_bootstrap,
            output_topic=output_topic or settings.KAFKA_TOPIC_EXTRACTED_TEXT,
        )
        
        logger.info(
            "RawFilesConsumer initialized",
            input_topic=self.topic,
            output_topic=self.processor.output_topic,
            group_id=self.group_id,
            auto_commit=True,
        )
    
    async def process_message(self, message: dict) -> bool:

        try:
            required_fields = ["path", "extension"]
            for field in required_fields:
                if field not in message:
                    logger.error("Missing required field in message", field=field, message=message)
                    return True
            
            result = await self.processor.process(message)
            
            logger.info(
                "Message processed",
                path=message.get("path"),
                status=result.get("status"),
                pd_categories=list(result.get("personal_data", {}).get("categories", {}).keys()),
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Unexpected error in process_message",
                error=str(e),
                error_type=type(e).__name__,
                message_path=message.get("path"),
            )

            return True