from agents import Agent, Runner, function_tool
from pydantic import ValidationError
import asyncio
from dotenv import load_dotenv
from pathlib import Path
from app.schemas import ExtractedInvoiceData
from app.bots.tools.extract_pdf import extract_pdf_contents

load_dotenv()

# ---------- AGENT ----------

invoice_extract_agent = Agent(
    name="Invoice Extract Agent",
    instructions=(
        "You are an invoice extraction agent. "
        "Use the tool to extract raw data from the document."
        "Extract the following fields from the provided invoice document: "
        "purchase_order, invoice_number, invoice_date, total_amount, sales_tax, "
        "merchandise_amount, miscellaneous_amount, shipping_amount. "
        "Note that merchandise_amount + sales_tax + miscellaneous_amount + shipping_amount should equal total_amount. "
        "merchandise_amount is the subtotal before tax and fees."
        "Return only valid JSON that matches the expected format."
        "Don't include PO prefixes like 'PO#' or 'P.O.', you can include 'KERNH-' if present."
        "Use dashes in PO not underscores, KERNH-LN9721 instead of KERNH_LN9721"
    ),
    tools=[extract_pdf_contents],
    model="gpt-5-mini",
    output_type=ExtractedInvoiceData,
)

# ---------- RUNNER ----------

async def run_invoice_extraction(invoice_path: str | Path, extra_instructions: str | None = None):
    """
    Extracts invoice fields from a given PDF file using the invoice_extract_agent.

    Args:
        invoice_path (str | Path): Full or relative path to the invoice PDF file.

    Returns:
        ExtractedInvoiceData | None: Structured invoice data if successful, else None.
    """
    try:
        # Normalize path
        invoice_path = Path(invoice_path).expanduser().resolve()
        if not invoice_path.exists():
            print(f"❌ File not found: {invoice_path}")
            return None

        print(f"📄 Processing: {invoice_path}")

        # Build an agent, optionally appending extra instructions
        if extra_instructions:
            merged_instructions = (
                invoice_extract_agent.instructions
                + "\n\nAdditional instructions:\n"
                + extra_instructions
            )
            agent = Agent(
                name=invoice_extract_agent.name,
                instructions=merged_instructions,
                tools=invoice_extract_agent.tools,
                model=invoice_extract_agent.model,
                output_type=invoice_extract_agent.output_type,
            )
        else:
            agent = invoice_extract_agent

        #with trace("Extracting invoice fields"):
        result = await Runner.run(agent, str(invoice_path))
        #print("✅ Extraction result:")
        #print(result)
        return result

    except ValidationError as ve:
        print("❌ Validation error in extracted data:")
        print(ve)
        return None

    except Exception as e:
        print("❌ Unexpected error during invoice extraction")
        print(e)
        return None

# ---------- MAIN ----------

if __name__ == "__main__":
    sample_invoice = "./data/cdw.pdf"
    asyncio.run(run_invoice_extraction(sample_invoice))
