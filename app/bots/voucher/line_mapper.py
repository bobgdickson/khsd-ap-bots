from langchain.agents import create_agent
from langchain_core.messages import HumanMessage

from .models import ExtractedInvoice, POLine, LineMapping, InvoiceLine
from .prompts.line_mapper import LINE_MAPPER_PROMPT
from app.services.langfuse import langfuse_handler
from app.bots.tools.extract_pdf import extract_pdf_contents


def generate_line_mapping(invoice: ExtractedInvoice, po_lines: list[POLine], filepath: str, extra_prompt: str | None = None) -> LineMapping:
    system_prompt = LINE_MAPPER_PROMPT
    if extra_prompt:
        system_prompt = system_prompt + "\n\nVendor-specific instructions:\n" + extra_prompt
    agent = create_agent(
        name="Voucher Line Mapper",
        system_prompt=system_prompt,
        tools=[],
        model="gpt-5-mini",
        response_format=LineMapping,
    )

    user_prompt = (
        f"Invoice JSON: {invoice.model_dump()}\n"
        f"PO Lines JSON: {[l.model_dump() for l in po_lines]}"
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

    content_blocks = [{"type": "text", "text": user_prompt}]
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

    result = agent.invoke({"messages": [HumanMessage(content=content_blocks)]}, config={"callbacks": [langfuse_handler]})
    structured = result.get("structured_response", result)
    return (
        structured
        if isinstance(structured, LineMapping)
        else LineMapping.model_validate(structured)
    )


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    # Reuse the sample from po_identifier smoke test
    sample_invoice = ExtractedInvoice(
        invoice_number="9715824737",
        vendor_name="GRAINGER",
        invoice_date="2025-11-18",
        total_amount=155.8,
        purchase_order_raw="KERNH-0000227878",
        fuzzy_po_candidates=["KERNH-0000227878", "1567882102", "661441", "6692567110"],
        lines=[
            InvoiceLine(
                description="LOCKING PLIER SETS, PLAIN GRIP, 4 PCS",
                quantity=1.0,
                unit_price=75.1,
                line_amount=75.1,
            ),
            InvoiceLine(
                description="HEXKEY SET, L, 2 27/32 IN TO 6 3/4 IN",
                quantity=3.0,
                unit_price=22.94,
                line_amount=68.82,
            ),
        ],
    )

    sample_pos = [
        POLine(
            po_id="0000227878",
            po_line=1,
            sched=1,
            distrib=1,
            description="TK133593774T Tongue and Groove Plier Set...",
            amount=93.74,
            account="4301",
            fund="03",
            program="0000",
        ),
        POLine(
            po_id="0000227878",
            po_line=2,
            sched=1,
            distrib=1,
            description="TK133593775T Locking Pliers Set...",
            amount=75.1,
            account="4301",
            fund="03",
            program="0000",
        ),
        POLine(
            po_id="0000227878",
            po_line=3,
            sched=1,
            distrib=1,
            description="TK133593776T Hex Key Set...",
            amount=68.82,
            account="4301",
            fund="03",
            program="0000",
        ),
    ]

    mapping = generate_line_mapping(sample_invoice, sample_pos)
    print("[SMOKE] Line mapping:")
    print(mapping)
