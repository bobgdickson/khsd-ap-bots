from pathlib import Path

from app.bots.agents.multimodal import extract_to_schema
from app.bots.voucher.models import ExtractedInvoice, InvoiceLine

EXTRACTION_PROMPT = """
You are an AP invoice extraction agent preparing data for PeopleSoft voucher entry.
Return JSON that matches the provided schema exactly.

Fields to extract:
- invoice_number
- vendor_name
- invoice_date (YYYY-MM-DD)
- total_amount
- purchase_order_raw (raw PO as printed; keep dashes, not underscores)
- fuzzy_po_candidates (include all PO-like strings you see, including your top candidate, that is included in purchase_order_raw)
- lines: description, quantity (if present), unit_price (if present), line_amount (required)
"""

def run_extraction(filepath: str, extra_prompt: str | None = None) -> ExtractedInvoice:
    """
    Use the multimodal extractor to build an ExtractedInvoice.
    Optionally append vendor-specific instructions.
    """
    path = Path(filepath).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    prompt = EXTRACTION_PROMPT
    if extra_prompt:
        prompt = prompt + "\n\nVendor-specific instructions:\n" + extra_prompt

    result = extract_to_schema(
        str(path),
        ExtractedInvoice,
        prompt=prompt,
    )

    # Ensure we have at least one line for downstream logic
    if not result.lines:
        result.lines = [InvoiceLine(description="Invoice total", line_amount=result.total_amount)]

    return result


if __name__ == "__main__":
    SAMPLE = "data/line_test.pdf"
    try:
        invoice = run_extraction(SAMPLE)
        print("[SMOKE] Extraction succeeded:")
        print(invoice)
    except Exception as exc:
        print(f"[SMOKE] Extraction failed: {exc}")
