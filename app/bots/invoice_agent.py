from agents import Agent, Runner, trace, function_tool
from pydantic import BaseModel, ValidationError
import base64
import fitz
import io
import asyncio
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

# ---------- OUTPUT MODELS ----------

class PDFExtractionResult(BaseModel):
    """
    Output model for PDF extraction tool.
    - extracted_text: Full text extracted from the PDF
    - image_base64: Base64-encoded PNG image of the first page
    - success: Whether the extraction was successful
    - description: A short status message
    """
    extracted_text: str
    image_base64: str
    success: bool
    description: str

class ExtractedInvoiceData(BaseModel):
    purchase_order: str
    invoice_number: str
    invoice_date: str
    total_amount: float
    sales_tax: float
    merchandise_amount: float
    miscellaneous_amount: float
    shipping_amount: float

# ---------- TOOLS ----------

@function_tool
def extract_pdf_contents(input: str) -> PDFExtractionResult:
    """
    Extracts text and a base64-encoded PNG image of the first page from a PDF.
    Uses PyMuPDF (fitz) instead of Poppler-based tools.
    """
    try:
        doc = fitz.open(input)
        if len(doc) == 0:
            return PDFExtractionResult(
                extracted_text="",
                image_base64="",
                success=False,
                description="Empty or invalid PDF"
            )

        # Extract text from all pages
        extracted_text = "\n".join(page.get_text() for page in doc)

        # Render first page as image
        first_page = doc[0]
        pix = first_page.get_pixmap(dpi=150)
        img_bytes = pix.tobytes("png")
        image_base64 = base64.b64encode(img_bytes).decode("utf-8")

        return PDFExtractionResult(
            extracted_text=extracted_text.strip(),
            image_base64=image_base64,
            success=True,
            description="PDF processed using PyMuPDF"
        )

    except Exception as e:
        return PDFExtractionResult(
            extracted_text="",
            image_base64="",
            success=False,
            description=f"Error: {str(e)}"
        )
    
# ---------- AGENT ----------

invoice_extract_agent = Agent(
    name="Invoice Extract Agent",
    instructions=(
        "You are an invoice extraction agent. "
        "Extract the following fields from the provided invoice document: "
        "purchase_order, invoice_number, invoice_date, total_amount, sales_tax, "
        "merchandise_amount, miscellaneous_amount, shipping_amount. "
        "Return only valid JSON that matches the expected format."
    ),
    tools=[extract_pdf_contents],
    model="gpt-4.1-mini",
    output_type=ExtractedInvoiceData,
)

# ---------- RUNNER ----------

async def run_invoice_extraction(invoice_path: str | Path):
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

        with trace("Extracting invoice fields"):
            result = await Runner.run(invoice_extract_agent, str(invoice_path))
            print("✅ Extraction result:")
            print(result)
            return result

    except ValidationError as ve:
        print("❌ Validation error in extracted data:")
        print(ve)
        return None

    except Exception as e:
        print("❌ Unexpected error during invoice extraction")
        return None

# ---------- MAIN ----------

if __name__ == "__main__":
    sample_invoice = "./data/sample.pdf"
    asyncio.run(run_invoice_extraction(sample_invoice))
