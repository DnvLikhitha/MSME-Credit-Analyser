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
from backend.services.recommendation import generate_and_save_recommendations
from backend.services.report import generate_and_save_report
from backend.services.scoring import save_risk_score
from backend.utils.bank_parser import parse_bank_statement_summary
from backend.utils.cache import cache_document_status, connect_redis
from backend.utils.encryption import decrypt_password
from backend.utils.gemini import extract_financial_metrics_from_text
from backend.utils.rabbitmq import DOCUMENT_PROCESSING_QUEUE
from backend.utils.websocket_manager import ws_manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def extract_text_from_file(file_path: str, mime_type: str, password: str | None = None) -> str:
    """Extracts text from a PDF or image file. Supports password-protected PDFs."""
    text = ""
    try:
        if mime_type == "application/pdf":
            open_kwargs = {"password": password} if password else {}
            try:
                with pdfplumber.open(file_path, **open_kwargs) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
            except Exception as pdf_err:
                err_type = type(pdf_err).__name__.lower()
                err_msg = str(pdf_err).lower()
                if (
                    "password" in err_msg
                    or "encrypted" in err_msg
                    or "incorrect" in err_msg
                    or "password" in err_type
                    or "encrypt" in err_type
                ):
                    raise ValueError(
                        "This PDF is password-protected. Please provide the correct PDF password when uploading."
                    ) from pdf_err
                raise

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
                doc_id_str = str(doc.id)
                await cache_document_status(doc_id_str, "EXTRACTING")
                await ws_manager.broadcast_status(doc_id_str, "EXTRACTING", "Extracting text and financial metrics...")
                
                try:
                    # 1. Decrypt password (if present) and extract text
                    raw_password = decrypt_password(doc.pdf_password) if doc.pdf_password else None

                    loop = asyncio.get_running_loop()
                    text = await loop.run_in_executor(
                        None, extract_text_from_file, doc.file_path, doc.mime_type, raw_password
                    )
                    
                    if not text.strip():
                        raise ValueError("No text could be extracted from the file.")

                    # Clear the password from DB immediately after extraction
                    if doc.pdf_password:
                        doc.pdf_password = None
                        db.commit()

                    # 2. Send to Gemini for structured extraction
                    logger.info(f"Extracted {len(text)} characters. Sending to Gemini...")
                    extracted_data_dict = await extract_financial_metrics_from_text(text)
                    
                    # Merge fallback metrics for any null fields if text contains bank statement summaries
                    fallback_metrics = parse_bank_statement_summary(text)
                    for key, val in fallback_metrics.items():
                        if extracted_data_dict.get(key) is None and val is not None:
                            extracted_data_dict[key] = val
                            logger.info(f"Filled missing metric '{key}' with parsed fallback value: {val}")

                    # 3. Save extracted metrics to database
                    metrics = ExtractedMetrics(
                        document_id=doc.id,
                        raw_extraction_json=extracted_data_dict,
                        **extracted_data_dict
                    )
                    db.add(metrics)
                    doc.status = "SCORING"
                    db.commit()
                    db.refresh(metrics)
                    await cache_document_status(doc_id_str, "SCORING")
                    await ws_manager.broadcast_status(doc_id_str, "SCORING", "Computing MSME credit risk score...")

                    logger.info(f"Extraction complete for {document_id}. Running risk scoring...")

                    # 4. Phase 3 — Run risk scoring immediately
                    risk_score = save_risk_score(db, doc.id, metrics)
                    logger.info(
                        f"Scoring complete for {document_id}: "
                        f"{risk_score.overall_score}/100 [{risk_score.risk_band}]"
                    )

                    doc.status = "RECOMMENDING"
                    db.commit()
                    await cache_document_status(doc_id_str, "RECOMMENDING")
                    await ws_manager.broadcast_status(doc_id_str, "RECOMMENDING", "Retrieving matching government schemes via RAG...")

                    # 5. Phase 4 — Run loan scheme matching via Embedding RAG
                    logger.info(f"Running loan scheme recommendations for {document_id}...")
                    recs = await generate_and_save_recommendations(db, doc.id, metrics, risk_score)

                    doc.status = "REPORTING"
                    db.commit()
                    await cache_document_status(doc_id_str, "REPORTING")
                    await ws_manager.broadcast_status(doc_id_str, "REPORTING", "Generating comprehensive credit report PDF...")

                    # 6. Phase 5 — Generate PDF credit report
                    logger.info(f"Generating PDF report for {document_id}...")
                    generate_and_save_report(db, doc, metrics, risk_score, recs)

                    doc.status = "COMPLETE"
                    db.commit()
                    await cache_document_status(doc_id_str, "COMPLETE")
                    await ws_manager.broadcast_status(
                        doc_id_str,
                        "COMPLETE",
                        "Credit assessment completed successfully!",
                        extra={"risk_score": risk_score.overall_score, "risk_band": risk_score.risk_band},
                    )
                    logger.info(f"Pipeline complete for {document_id}. Upload -> Extract -> Score -> Recommend -> Report. Done!")
                    
                except Exception as e:
                    logger.error(f"Failed processing document {document_id}: {e}")
                    # Ensure password is wiped even if processing fails
                    if doc.pdf_password:
                        doc.pdf_password = None
                    doc.status = "FAILED"
                    doc.error_message = str(e) or f"Processing failed: {type(e).__name__}"
                    db.commit()
                    await cache_document_status(doc_id_str, "FAILED", error=doc.error_message)
                    await ws_manager.broadcast_status(doc_id_str, "FAILED", f"Processing failed: {doc.error_message}")

        except Exception as e:
            logger.error(f"Message processing failed: {e}")


async def main():
    """Main worker loop to consume RabbitMQ messages."""
    logger.info("Starting MSME Extraction Worker...")
    
    # Initialize Redis connection pool
    await connect_redis()

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
