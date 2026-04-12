from abc import ABC, abstractmethod
from typing import Any, Optional
from confluent_kafka import Consumer, Message
import structlog

logger = structlog.get_logger("consumer_base")


class BaseConsumer(ABC):
    
    def __init__(
        self,
        bootstrap_servers: str,
        group_id: str,
        topic: str,
        auto_offset_reset: str = "earliest",
        enable_auto_commit: bool = True,
        auto_commit_interval_ms: int = 5000,
    ):
        self.bootstrap_servers = bootstrap_servers
        self.group_id = group_id
        self.topic = topic
        self.auto_offset_reset = auto_offset_reset
        self.enable_auto_commit = enable_auto_commit
        self.auto_commit_interval_ms = auto_commit_interval_ms
        
        self._consumer: Optional[Consumer] = None
        self._running = False
        
        logger.debug(
            "BaseConsumer initialized",
            bootstrap=bootstrap_servers,
            group_id=group_id,
            topic=topic,
            auto_commit=enable_auto_commit,
        )
    
    @abstractmethod
    async def process_message(self, message: dict) -> bool:
        pass
    
    def _create_consumer_config(self) -> dict:

        return {
            "bootstrap.servers": self.bootstrap_servers,
            "group.id": self.group_id,
            "auto.offset.reset": self.auto_offset_reset,
            "enable.auto.commit": self.enable_auto_commit,
            "auto.commit.interval.ms": self.auto_commit_interval_ms,
            "session.timeout.ms": 30000,
            "heartbeat.interval.ms": 3000,
            "max.poll.interval.ms": 300000,
            "fetch.message.max.bytes": 20_000_000,
        }
    
    def start(self) -> None:

        config = self._create_consumer_config()
        self._consumer = Consumer(config)
        self._consumer.subscribe([self.topic])
        self._running = True
        
        logger.info("Consumer started", topic=self.topic, group_id=self.group_id)
    
    def stop(self) -> None:

        self._running = False
        
        if self._consumer:
            self._consumer.close()
            self._consumer = None
        
        logger.info("Consumer stopped", topic=self.topic)
    
    def run_sync(self, max_messages: Optional[int] = None) -> int:

        if not self._consumer:
            self.start()
        
        processed = 0
        
        try:
            while self._running and (max_messages is None or processed < max_messages):
                msg = self._consumer.poll(timeout=1.0)
                
                if msg is None:
                    continue
                
                if msg.error():
                    logger.error(
                        "Consumer error",
                        error=msg.error().str(),
                        topic=msg.topic(),
                    )
                    continue
                
                try:
                    import json
                    value = msg.value().decode("utf-8")
                    message_data = json.loads(value)
                    
                    success = self.process_message_sync(message_data)
                    
                    if success:
                        processed += 1
                        logger.debug(
                            "Message processed",
                            topic=msg.topic(),
                            partition=msg.partition(),
                            offset=msg.offset(),
                        )
                    
                except Exception as e:
                    logger.error(
                        "Error processing message",
                        error=str(e),
                        error_type=type(e).__name__,
                        offset=msg.offset(),
                    )
                    
        except KeyboardInterrupt:
            logger.info("Consumer interrupted by user")
        finally:
            self.stop()
        
        return processed
    
    def process_message_sync(self, message: dict) -> bool:

        import asyncio
        try:
            return asyncio.run(self.process_message(message))
        except RuntimeError:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self.process_message(message))