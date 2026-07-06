"""
Curated knowledge base of Indian Government MSME Loan Schemes.
This is used as context for the Gemini-based recommendation engine.
"""

GOVERNMENT_SCHEMES = [
    {
        "scheme_name": "PMMY - MUDRA (Shishu)",
        "scheme_type": "MUDRA",
        "issuing_body": "Micro Units Development and Refinance Agency",
        "description": "Loans for micro-enterprises at the starting stage.",
        "max_loan_amount_inr": 50000,
        "collateral_required": False,
        "eligibility_criteria": "Micro enterprises, non-corporate, non-farm sector income generating activities.",
        "interest_rate_range": "10% - 12%",
        "tenure": "Up to 5 years"
    },
    {
        "scheme_name": "PMMY - MUDRA (Kishore)",
        "scheme_type": "MUDRA",
        "issuing_body": "Micro Units Development and Refinance Agency",
        "description": "Loans for enterprises that have started but need funds to expand.",
        "max_loan_amount_inr": 500000,
        "collateral_required": False,
        "eligibility_criteria": "Existing micro enterprises looking for expansion.",
        "interest_rate_range": "11% - 14%",
        "tenure": "Up to 5 years"
    },
    {
        "scheme_name": "PMMY - MUDRA (Tarun)",
        "scheme_type": "MUDRA",
        "issuing_body": "Micro Units Development and Refinance Agency",
        "description": "Loans for established enterprises needing larger funds for growth.",
        "max_loan_amount_inr": 1000000,
        "collateral_required": False,
        "eligibility_criteria": "Established micro/small enterprises with steady revenue.",
        "interest_rate_range": "11% - 14%",
        "tenure": "Up to 5 years"
    },
    {
        "scheme_name": "PMEGP (Prime Minister's Employment Generation Programme)",
        "scheme_type": "PMEGP",
        "issuing_body": "KVIC / Ministry of MSME",
        "description": "Credit-linked subsidy program to generate employment through micro-enterprises.",
        "max_loan_amount_inr": 5000000,  # 50 Lakh for manufacturing, 20 for service
        "collateral_required": False, # Up to 10 Lakhs no collateral
        "eligibility_criteria": "Any individual, above 18 years. New manufacturing or service sector projects. High priority for rural/unemployed.",
        "interest_rate_range": "Standard bank rates (subsidized margin money)",
        "tenure": "3 to 7 years"
    },
    {
        "scheme_name": "CGTMSE (Credit Guarantee Fund Trust for Micro and Small Enterprises)",
        "scheme_type": "CGTMSE",
        "issuing_body": "Ministry of MSME and SIDBI",
        "description": "Provides guarantee cover for collateral-free credit facilities to MSEs.",
        "max_loan_amount_inr": 50000000,  # 5 Crore limit
        "collateral_required": False,
        "eligibility_criteria": "New and existing Micro and Small Enterprises engaged in manufacturing or service activity (excluding agriculture, retail trade, educational institutions, self help groups). Minimum LOW/MEDIUM risk band required by most member banks.",
        "interest_rate_range": "Subject to RBI guidelines, typically 9% - 14%",
        "tenure": "Varies by lender"
    },
    {
        "scheme_name": "SIDBI Make in India Soft Loan Fund for Micro Small and Medium Enterprises (SMILE)",
        "scheme_type": "SIDBI",
        "issuing_body": "SIDBI",
        "description": "Soft loans in the nature of quasi-equity and term loans on relatively soft terms to meet debt-equity ratio required for establishing new MSMEs or expanding existing ones.",
        "max_loan_amount_inr": 25000000, # Varies, usually minimum 10 Lakh
        "collateral_required": True, # Usually requires some collateral or CGTMSE cover
        "eligibility_criteria": "New enterprises in manufacturing/services. Existing enterprises undertaking expansion/modernization. Requires good financial track record (LOW risk).",
        "interest_rate_range": "Attractive lower interest rates",
        "tenure": "Up to 10 years including moratorium"
    },
    {
        "scheme_name": "Stand-Up India Scheme",
        "scheme_type": "OTHER",
        "issuing_body": "SIDBI / Ministry of Finance",
        "description": "Bank loans between 10 lakh and 1 Crore to at least one SC/ST borrower and at least one woman borrower per bank branch for setting up a greenfield enterprise.",
        "max_loan_amount_inr": 10000000,
        "collateral_required": False, # Covered under CGSSI
        "eligibility_criteria": "SC/ST and/or women entrepreneurs. Greenfield projects only in manufacturing, services, or trading sector.",
        "interest_rate_range": "Lowest applicable rate of the bank for that category",
        "tenure": "Up to 7 years"
    }
]

def get_schemes_context() -> str:
    """Returns the knowledge base formatted as a readable string for LLM injection."""
    import json
    return json.dumps(GOVERNMENT_SCHEMES, indent=2)
