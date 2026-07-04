import json
import typing
from pydantic import BaseModel, Field
import google.generativeai as genai

from backend.config import settings

# Configure Gemini
if settings.GOOGLE_API_KEY:
    genai.configure(api_key=settings.GOOGLE_API_KEY)


class ExtractedData(BaseModel):
    """Pydantic schema for structured output from Gemini."""
    annual_revenue: typing.Optional[float] = Field(None, description="Total annual revenue or turnover in INR")
    revenue_growth_yoy: typing.Optional[float] = Field(None, description="Year over year revenue growth percentage (e.g., 15.5 for 15.5%)")
    net_profit_margin: typing.Optional[float] = Field(None, description="Net profit margin percentage")
    gross_profit_margin: typing.Optional[float] = Field(None, description="Gross profit margin percentage")
    
    total_liabilities: typing.Optional[float] = Field(None, description="Total liabilities in INR")
    total_assets: typing.Optional[float] = Field(None, description="Total assets in INR")
    debt_to_income_ratio: typing.Optional[float] = Field(None, description="Debt to income ratio (ratio, not percentage)")
    
    current_ratio: typing.Optional[float] = Field(None, description="Current assets divided by current liabilities")
    quick_ratio: typing.Optional[float] = Field(None, description="Quick assets divided by current liabilities")
    
    gst_filing_consistency: typing.Optional[float] = Field(None, description="Score from 0 to 1 indicating consistency of GST filings (1 = perfect)")
    total_gst_paid: typing.Optional[float] = Field(None, description="Total GST paid in INR")
    gst_turnover: typing.Optional[float] = Field(None, description="Turnover reported in GST filings in INR")
    
    avg_monthly_balance: typing.Optional[float] = Field(None, description="Average monthly bank balance in INR")
    min_monthly_balance: typing.Optional[float] = Field(None, description="Minimum monthly bank balance in INR")
    balance_trend: typing.Optional[float] = Field(None, description="Score from -1 to 1 indicating balance trend (-1 = declining, 1 = growing)")
    num_monthly_transactions: typing.Optional[float] = Field(None, description="Average number of transactions per month")
    cheque_bounce_count: typing.Optional[float] = Field(None, description="Number of cheque bounces observed")


async def extract_financial_metrics_from_text(text: str) -> dict:
    """
    Calls Gemini API with structured output to extract financial metrics from raw text.
    Returns a dictionary matching the ExtractedMetrics SQLAlchemy model schema.
    """
    if not settings.GOOGLE_API_KEY:
        raise ValueError("GOOGLE_API_KEY is not configured.")

    # We use Gemini 1.5 Flash as it supports Structured Outputs via response_schema
    model = genai.GenerativeModel(
        model_name=settings.GEMINI_MODEL,
        system_instruction=(
            "You are an expert financial analyst. Your job is to extract specific financial metrics "
            "from the provided raw text (which comes from OCR on bank statements, GST filings, or financials). "
            "Extract the data accurately. If a metric is not present in the text or cannot be reasonably derived, "
            "return null for that field. Do not make up numbers. Convert all monetary values to standard float representations."
        )
    )

    try:
        response = await model.generate_content_async(
            text,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=ExtractedData,
                temperature=0.1,  # Low temperature for factual extraction
            )
        )
        
        # The response text will be a JSON string matching the ExtractedData schema
        data = json.loads(response.text)
        return data
        
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        raise
