import asyncio
import json
import logging
import os
import sys

# Ensure backend modules can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import aio_pika
import pdfplumber
import pytesseract
from PIL import Image

from backend.config import settings
from backend.database import SessionLocal
from backend.models.document import Document
from backend.models.extracted_metrics import ExtractedMetrics
from backend.utils.gemini import extract_financial_metrics_from_text
from backend.utils.rabbitmq import DOCUMENT_PROCESSING_QUEUE

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def extract_text_from_file(file_path: str, mime_type: str) -> str:
    """Extracts text from a PDF or image file."""
    text = ""
    try:
        if mime_type == "application/pdf":
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            
            # Fallback to OCR if PDF has no text (e.g., scanned PDF)
            # Not fully implemented here for brevity, but this is where it would go.
            
        elif mime_type in ["image/jpeg", "image/png", "image/jpg"]:
            image = Image.open(file_path)
            text = pytesseract.image_to_string(image)
        else:
            logger.warning(f"Unsupported mime_type for extraction: {mime_type}")
            
    except Exception as e:
        logger.error(f"Error extracting text from {file_path}: {e}")
        raise
        
    return text


async def process_document(message: aio_pika.IncomingMessage):
    """Callback function for RabbitMQ consumer."""
    async with message.process():
        try:
            body = json.loads(message.body.decode())
            document_id = body.get("document_id")
            
            if not document_id:
                logger.error("Message missing document_id")
                return

            logger.info(f"Processing document {document_id}")
            
            with SessionLocal() as db:
                doc = db.query(Document).filter(Document.id == document_id).first()
                if not doc:
                    logger.error(f"Document {document_id} not found in DB")
                    return
                
                # Update status to EXTRACTING
                doc.status = "EXTRACTING"
                db.commit()
                
                try:
                    # 1. Extract text (Blocking I/O, ideally run in executor)
                    loop = asyncio.get_running_loop()
                    text = await loop.run_in_executor(None, extract_text_from_file, doc.file_path, doc.mime_type)
                    
                    if not text.strip():
                        raise ValueError("No text could be extracted from the file.")
                    
                    # 2. Send to Gemini for structured extraction
                    logger.info(f"Extracted {len(text)} characters. Sending to Gemini...")
                    extracted_data_dict = await extract_financial_metrics_from_text(text)
                    
                    # 3. Save to database
                    metrics = ExtractedMetrics(
                        document_id=doc.id,
                        raw_extraction_json=extracted_data_dict,
                        **extracted_data_dict
                    )
                    db.add(metrics)
                    
                    # 4. Update status to SCORING (triggers Phase 3 next)
                    doc.status = "SCORING"
                    db.commit()
                    
                    logger.info(f"Successfully processed document {document_id}")
                    
                except Exception as e:
                    logger.error(f"Failed processing document {document_id}: {e}")
                    doc.status = "FAILED"
                    doc.error_message = str(e)
                    db.commit()

        except Exception as e:
            logger.error(f"Message processing failed: {e}")


async def main():
    """Main worker loop to consume RabbitMQ messages."""
    logger.info("Starting MSME Extraction Worker...")
    
    # Wait for RabbitMQ to be ready in Docker
    await asyncio.sleep(5)
    
    try:
        connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
        channel = await connection.channel()
        
        # Pre-fetch 1 message at a time
        await channel.set_qos(prefetch_count=1)
        
        queue = await channel.declare_queue(DOCUMENT_PROCESSING_QUEUE, durable=True)
        
        logger.info(f"Worker connected to {settings.RABBITMQ_URL}, waiting for messages...")
        
        # Consume messages indefinitely
        await queue.consume(process_document)
        
        # Keep the loop running
        await asyncio.Future()
        
    except Exception as e:
        logger.error(f"Worker failed to start: {e}")
    finally:
        if 'connection' in locals() and connection:
            await connection.close()

if __name__ == "__main__":
    asyncio.run(main())
