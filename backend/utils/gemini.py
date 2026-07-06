"""Gemini API integration for structured financial metric extraction."""
import json
import typing
import google.generativeai as genai
import google.ai.generativelanguage as glm

from backend.config import settings

# Configure Gemini
if settings.GOOGLE_API_KEY:
    genai.configure(api_key=settings.GOOGLE_API_KEY)


def _build_response_schema() -> glm.Schema:
    """
    Build a Gemini-compatible JSON schema for financial metric extraction.
    We manually build the glm.Schema because the Gemini SDK rejects Pydantic
    schemas that include 'default' or 'anyOf' fields (Pydantic v1/v2 quirk).
    """
    def nullable_number(description: str) -> glm.Schema:
        return glm.Schema(
            type=glm.Type.NUMBER,
            description=description,
            nullable=True,
        )

    return glm.Schema(
        type=glm.Type.OBJECT,
        properties={
            "annual_revenue": nullable_number("Total annual revenue or turnover in INR"),
            "revenue_growth_yoy": nullable_number("Year-over-year revenue growth percentage (e.g., 15.5 for 15.5%)"),
            "net_profit_margin": nullable_number("Net profit margin percentage"),
            "gross_profit_margin": nullable_number("Gross profit margin percentage"),
            "total_liabilities": nullable_number("Total liabilities in INR"),
            "total_assets": nullable_number("Total assets in INR"),
            "debt_to_income_ratio": nullable_number("Debt to income ratio (ratio, not percentage)"),
            "current_ratio": nullable_number("Current assets divided by current liabilities"),
            "quick_ratio": nullable_number("Quick assets divided by current liabilities"),
            "gst_filing_consistency": nullable_number("Score from 0 to 1 indicating consistency of GST filings"),
            "total_gst_paid": nullable_number("Total GST paid in INR"),
            "gst_turnover": nullable_number("Turnover reported in GST filings in INR"),
            "avg_monthly_balance": nullable_number("Average monthly bank balance in INR"),
            "min_monthly_balance": nullable_number("Minimum monthly bank balance in INR"),
            "balance_trend": nullable_number("Score from -1 to 1 indicating balance trend (-1=declining, 1=growing)"),
            "num_monthly_transactions": nullable_number("Average number of transactions per month"),
            "cheque_bounce_count": nullable_number("Number of cheque bounces observed"),
        }
    )


async def extract_financial_metrics_from_text(text: str) -> dict:
    """
    Calls Gemini API with structured output to extract financial metrics from raw text.
    Returns a dictionary matching the ExtractedMetrics SQLAlchemy model schema.
    """
    if not settings.GOOGLE_API_KEY:
        raise ValueError("GOOGLE_API_KEY is not configured.")

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
                response_schema=_build_response_schema(),
                temperature=0.1,
            )
        )

        data = json.loads(response.text)
        return data

    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        raise


def _build_recommendation_schema() -> glm.Schema:
    """Build a Gemini-compatible JSON schema for an array of loan recommendations."""
    recommendation_item = glm.Schema(
        type=glm.Type.OBJECT,
        properties={
            "scheme_name": glm.Schema(type=glm.Type.STRING, description="Exact name of the scheme from the knowledge base"),
            "scheme_type": glm.Schema(type=glm.Type.STRING, description="MUDRA | PMEGP | CGTMSE | SIDBI | OTHER"),
            "issuing_body": glm.Schema(type=glm.Type.STRING, description="Issuing body from the knowledge base"),
            "eligibility_score": glm.Schema(type=glm.Type.NUMBER, description="Score from 0.0 to 1.0 indicating how well this business matches the scheme criteria"),
            "reasoning": glm.Schema(type=glm.Type.STRING, description="A 2-3 sentence explanation of why this scheme is recommended based on the user's specific metrics and risk band"),
            "scheme_details": glm.Schema(
                type=glm.Type.OBJECT,
                properties={
                    "max_loan_amount_inr": glm.Schema(type=glm.Type.NUMBER, nullable=True),
                    "interest_rate_range": glm.Schema(type=glm.Type.STRING, nullable=True),
                    "tenure": glm.Schema(type=glm.Type.STRING, nullable=True),
                    "collateral_required": glm.Schema(type=glm.Type.BOOLEAN, nullable=True)
                }
            )
        }
    )

    return glm.Schema(
        type=glm.Type.ARRAY,
        items=recommendation_item,
        description="Top 3 recommended loan schemes based on the provided business profile"
    )


async def match_loan_schemes(metrics_dict: dict, risk_score_dict: dict, knowledge_base_str: str) -> list[dict]:
    """
    Calls Gemini API with the business profile and knowledge base to generate ranked loan recommendations.
    Returns a list of dictionaries matching the LoanRecommendation SQLAlchemy model schema.
    """
    if not settings.GOOGLE_API_KEY:
        raise ValueError("GOOGLE_API_KEY is not configured.")

    model = genai.GenerativeModel(
        model_name=settings.GEMINI_MODEL,
        system_instruction=(
            "You are an expert MSME financial advisor. You will be provided with the financial metrics "
            "and credit risk score of a business, along with a knowledge base of Indian Government Loan Schemes. "
            "Your task is to analyze the business profile against the schemes' eligibility criteria and output "
            "the top 3 most suitable loan schemes as a structured JSON array. Sort them from best match (highest eligibility) "
            "to worst match. Be realistic about eligibility: if a business has HIGH risk and poor financials, do not "
            "recommend schemes that require strong financial track records."
        )
    )

    prompt = f"""
    ### KNOWLEDGE BASE (Available Loan Schemes)
    {knowledge_base_str}

    ### BUSINESS PROFILE
    Metrics: {json.dumps(metrics_dict, indent=2)}
    Risk Assessment: {json.dumps(risk_score_dict, indent=2)}

    Output the top 3 recommended schemes as a JSON array.
    """

    try:
        response = await model.generate_content_async(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=_build_recommendation_schema(),
                temperature=0.2, # slight creativity for reasoning
            )
        )

        data = json.loads(response.text)
        return data

    except Exception as e:
        print(f"Error calling Gemini API for recommendations: {e}")
        raise
