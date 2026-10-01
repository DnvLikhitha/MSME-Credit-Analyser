"""
Fallback Bank Statement Parser — Extracts summary metrics from raw text
when LLM extraction returns missing/null values for multi-page statements.
"""
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def parse_bank_statement_summary(text: str) -> dict:
    """
    Parses bank statement summary data from raw text.
    Handles PDF text extraction where spaces between words might be missing (e.g., 'OpeningBalance').
    """
    metrics = {}
    if not text:
        return metrics

    # 1. Flexible regex for HDFC / Standard Statement Summary blocks
    # Handles both 'Opening Balance' and 'OpeningBalance'
    summary_match = re.search(
        r'Opening\s*Bal(?:ance)?.*?\n\s*([\d,]+\.\d{2})\s+(\d+)\s+(\d+)\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})',
        text,
        re.IGNORECASE | re.DOTALL,
    )

    if not summary_match:
        # Alternative pattern with key-value or inline formatting
        summary_match = re.search(
            r'Opening\s*Bal(?:ance)?\s*[:\-]?\s*([\d,]+\.\d{2}).*?Dr\s*Count\s*[:\-]?\s*(\d+).*?Cr\s*Count\s*[:\-]?\s*(\d+).*?Debits\s*[:\-]?\s*([\d,]+\.\d{2}).*?Credits\s*[:\-]?\s*([\d,]+\.\d{2}).*?Closing\s*Bal(?:ance)?\s*[:\-]?\s*([\d,]+\.\d{2})',
            text,
            re.IGNORECASE | re.DOTALL,
        )

    if summary_match:
        try:
            op_bal = float(summary_match.group(1).replace(',', ''))
            dr_cnt = int(summary_match.group(2))
            cr_cnt = int(summary_match.group(3))
            debits = float(summary_match.group(4).replace(',', ''))
            credits = float(summary_match.group(5).replace(',', ''))
            cl_bal = float(summary_match.group(6).replace(',', ''))

            # Estimate number of months from period (e.g. "From : 01/04/2025 To : 30/06/2025")
            months = 1.0
            period_match = re.search(
                r'From\s*:\s*(\d{2}/\d{2}/\d{4}|\d{2}/\d{2}/\d{2})\s+To\s*:\s*(\d{2}/\d{2}/\d{4}|\d{2}/\d{2}/\d{2})',
                text,
                re.IGNORECASE,
            )
            if period_match:
                from datetime import datetime
                d1_str, d2_str = period_match.group(1), period_match.group(2)
                fmt = "%d/%m/%Y" if len(d1_str) == 10 else "%d/%m/%y"
                try:
                    d1 = datetime.strptime(d1_str, fmt)
                    d2 = datetime.strptime(d2_str, fmt)
                    days = (d2 - d1).days + 1
                    months = max(1.0, round(days / 30.0, 1))
                except Exception:
                    months = 1.0

            total_tx = dr_cnt + cr_cnt
            avg_tx = round(total_tx / months, 2)
            avg_bal = round((op_bal + cl_bal) / 2.0, 2)
            min_bal = min(op_bal, cl_bal)

            trend = round((cl_bal - op_bal) / op_bal, 2) if op_bal > 0 else 0.0

            # Annualized revenue from deposit credits
            annualized_rev = round((credits / months) * 12.0, 2)

            # Check cheque bounces
            bounce_matches = len(re.findall(r'chq (?:ret|bounce|dishon| unpaid)|cheque return', text, re.IGNORECASE))

            metrics["avg_monthly_balance"] = avg_bal
            metrics["min_monthly_balance"] = min_bal
            metrics["balance_trend"] = trend
            metrics["num_monthly_transactions"] = avg_tx
            metrics["annual_revenue"] = annualized_rev
            metrics["cheque_bounce_count"] = float(bounce_matches)

            logger.info(
                f"Parsed bank summary: avg_bal={avg_bal}, min_bal={min_bal}, "
                f"trend={trend}, annual_rev={annualized_rev}, tx_pm={avg_tx}"
            )
        except Exception as err:
            logger.warning(f"Error parsing bank statement regex match: {err}")

    return metrics
