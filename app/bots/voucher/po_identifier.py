from langchain.agents import create_agent
from langchain.tools import tool
from langchain_core.messages import HumanMessage
from .po_sql import search_po_candidates
from .models import ExtractedInvoice, ValidatedPO, InvoiceLine
from .prompts.po_identifier import PO_IDENTIFIER_PROMPT
from app.services.langfuse import langfuse_handler
from app.bots.tools.extract_pdf import extract_pdf_contents

def identify_po(invoice: ExtractedInvoice, filepath: str, extra_prompt: str | None = None) -> ValidatedPO:

    @tool
    def po_search(pattern: str) -> list[dict]:
        """Search for PO candidates in PeopleSoft matching the given pattern."""
        return search_po_candidates(pattern)

    system_prompt = PO_IDENTIFIER_PROMPT
    if extra_prompt:
        system_prompt = system_prompt + "\n\nVendor-specific instructions:\n" + extra_prompt

    agent = create_agent(
        name="Voucher PO Identifier",
        system_prompt=system_prompt,
        tools=[po_search],
        model="gpt-5-mini",
        response_format=ValidatedPO,
    )

    base_text = (
        f"Vendor name: {invoice.vendor_name}\n"
        f"Raw PO text: {invoice.purchase_order_raw}\n"
        f"Fuzzy PO candidates: {invoice.fuzzy_po_candidates}"
    )

    pdf_contents = extract_pdf_contents.invoke(
        {"input": filepath, "include_preview_on_ocr": True}
    )
    if isinstance(pdf_contents, dict):
        extracted_text = pdf_contents.get("extracted_text", "") or ""
        image_b64 = pdf_contents.get("image_base64", "") or ""
    else:
        extracted_text = getattr(pdf_contents, "extracted_text", "") or ""
        image_b64 = getattr(pdf_contents, "image_base64", "") or ""

    content_blocks = [{"type": "text", "text": base_text}]
    if extracted_text:
        content_blocks.append({"type": "text", "text": extracted_text})
    if image_b64:
        content_blocks.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": image_b64
                    if image_b64.startswith("data:image")
                    else f"data:image/jpeg;base64,{image_b64}"
                },
            }
        )
    human_msg = HumanMessage(content=content_blocks)

    result = agent.invoke({"messages": [human_msg]}, config={"callbacks": [langfuse_handler]})
    structured = result.get("structured_response", result)
    if not isinstance(structured, ValidatedPO):
        structured = ValidatedPO.model_validate(structured)
    if structured.confidence is None:
        structured.confidence = 0.0
    return structured


if __name__ == "__main__":
    
    extract_test = ExtractedInvoice(
        invoice_number='9715824737', 
        vendor_name='GRAINGER',
        invoice_date='2025-11-18', 
        total_amount=155.8, 
        purchase_order_raw='KERNH-0000227878',
        fuzzy_po_candidates=['KERNH-0000227878', '1567882102', '661441', '6692567110'], 
        lines=[InvoiceLine(description='LOCKING PLIER SETS, PLAIN GRIP, 4 PCS MANUFACTURER # 428GS', quantity=1.0, unit_price=75.1, line_amount=75.1), 
                InvoiceLine(description='HEXKEY SET, L, 2 27/32 IN TO 6 3/4 IN MANUFACTURER # 13213', quantity=3.0, unit_price=22.94, line_amount=68.82)]
    )
    po = identify_po(extract_test)
    print("[SMOKE] Identified PO:")
    print(po)
