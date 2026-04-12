from confluent_kafka import Producer, KafkaError
from confluent_kafka.admin import AdminClient, NewTopic
import structlog

from src.config import settings

logger = structlog.get_logger("kafka")


def init_kafka_producer(
    bootstrap_servers: str,
    client_id: str = "pd-scanner",
    acks: str = "all",
    retries: int = 5,
    compression_type: str = "snappy",
    max_message_bytes: int = 20_000_000,
) -> Producer:

    config = {
        "bootstrap.servers": bootstrap_servers,
        "client.id": client_id,
        "acks": acks,
        "retries": retries,
        "retry.backoff.ms": 100,
        "linger.ms": 5,
        "compression.type": compression_type,
        "enable.idempotence": True,
    }
    
    logger.debug("Initializing Kafka producer", bootstrap=bootstrap_servers, client_id=client_id)
    
    producer = Producer(config)
    
    try:
        metadata = producer.list_topics(timeout=10)
        logger.info("Connection to Kafka verified", topics=list(metadata.topics.keys()))
    except Exception as e:
        logger.warning("Failed to retrieve Kafka metadata", error=str(e))
    
    return producer


def ensure_topics_exist(
    bootstrap_servers: str,
    topics: list[str],
    num_partitions: int = 3,
    replication_factor: int = 1,
) -> None:
    
    admin = AdminClient({"bootstrap.servers": bootstrap_servers})
    
    topic_list = [
        NewTopic(
            topic,
            num_partitions=num_partitions,
            replication_factor=replication_factor,
            config={"retention.ms": "604800000"},  # 7 days
        )
        for topic in topics
    ]
    
    fs = admin.create_topics(topic_list)
    
    for topic, f in fs.items():
        try:
            f.result()
            logger.info("The topic has been created or already exists", topic=topic)
        except Exception as e:
            if "TOPIC_ALREADY_EXISTS" not in str(e):
                logger.error("Error creating topic", topic=topic, error=str(e))


def delivery_report(err, msg):

    if err:
        logger.error("Message NOT delivered", error=err, topic=msg.topic())
    else:
        logger.debug("Message delivered", topic=msg.topic(), partition=msg.partition(), offset=msg.offset())