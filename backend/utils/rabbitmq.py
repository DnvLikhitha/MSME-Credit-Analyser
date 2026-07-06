import json
from typing import Optional

import aio_pika

from backend.config import settings

# Global connection and channel objects for the FastAPI lifecycle
_connection: Optional[aio_pika.RobustConnection] = None
_channel: Optional[aio_pika.RobustChannel] = None

DOCUMENT_PROCESSING_QUEUE = "document_processing_queue"


async def connect_rabbitmq():
    """Establish connection to RabbitMQ (called during app startup)."""
    global _connection, _channel
    try:
        _connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
        _channel = await _connection.channel()
        # Declare the queue so it exists before we publish
        await _channel.declare_queue(DOCUMENT_PROCESSING_QUEUE, durable=True)
        print(f"[*] Connected to RabbitMQ at {settings.RABBITMQ_URL}")
    except Exception as e:
        print(f"[!] Failed to connect to RabbitMQ: {e}")


async def close_rabbitmq():
    """Close RabbitMQ connection (called during app shutdown)."""
    global _connection
    if _connection:
        await _connection.close()
        print("[*] Closed RabbitMQ connection")


async def publish_document_processing_task(document_id: str):
    """Publish a document ID to the processing queue."""
    global _channel
    if not _channel:
        print("[!] RabbitMQ channel not initialized. Cannot publish message.")
        return False

    message_body = json.dumps({"document_id": str(document_id)}).encode()
    message = aio_pika.Message(
        body=message_body,
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
    )

    try:
        await _channel.default_exchange.publish(
            message,
            routing_key=DOCUMENT_PROCESSING_QUEUE,
        )
        return True
    except Exception as e:
        print(f"[!] Failed to publish task to RabbitMQ: {e}")
        return False
