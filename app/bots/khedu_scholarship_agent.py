from agents import Agent, Runner, function_tool
from pydantic import ValidationError
import fitz
import asyncio
from dotenv import load_dotenv
from pathlib import Path
from app.schemas import ScholarshipExtractedCheckAuthorization, PDFExtractionResult
from app.bots.utils.ocr import page_pixmap, pixmap_to_pil, safe_preview_b64, preprocess_for_ocr, ocr_image, check_ocr

load_dotenv()

OCR_AVAILABLE = check_ocr()

# ---------- tool ----------

@function_tool
def extract_pdf_contents(
    input: str,
    *,
    ocr_if_empty: bool = True,
    ocr_lang: str = "eng",
    ocr_dpi: int = 300,
    preview_dpi: int = 140,
    max_ocr_pages: int = 5,
    include_preview_on_ocr: bool = False,
    max_preview_b64_chars: int = 1_000_000
) -> PDFExtractionResult:
    """
    Extract text from a PDF. If no text layer, optionally OCR (Tesseract).
    Returns a size-capped JPEG preview for native-text PDFs; omits the preview
    on OCR (by default) to avoid large base64 payloads.
    """
    try:
        path = Path(input).expanduser().resolve()
        if not path.exists():
            return PDFExtractionResult(
                extracted_text="",
                image_base64="",
                success=False,
                description=f"File not found: {path}",
            )

        doc = fitz.open(str(path))
        if len(doc) == 0:
            return PDFExtractionResult(
                extracted_text="",
                image_base64="",
                success=False,
                description="Empty or invalid PDF",
            )

        # 1) Native text layer
        native_text_parts = [p.get_text() for p in doc]
        native_text = "\n".join(t for t in native_text_parts if t).strip()

        first_page = doc[0]
        native_preview_b64 = safe_preview_b64(
            first_page, dpi=preview_dpi, max_chars=max_preview_b64_chars
        )

        if native_text:
            return PDFExtractionResult(
                extracted_text=native_text,
                image_base64=native_preview_b64,
                success=True,
                description="PyMuPDF text layer",
            )

        # 2) OCR fallback
        if not (ocr_if_empty and OCR_AVAILABLE):
            return PDFExtractionResult(
                extracted_text="",
                image_base64=native_preview_b64,
                success=False,
                description="No text layer; OCR disabled/unavailable",
            )

        ocr_text_parts = []
        pages_to_ocr = min(len(doc), max_ocr_pages)
        for i in range(pages_to_ocr):
            pix = page_pixmap(doc[i], dpi=ocr_dpi)
            pil_img = pixmap_to_pil(pix)
            pil_img = preprocess_for_ocr(pil_img)
            page_text = ocr_image(pil_img, lang=ocr_lang, psm=6)
            if page_text:
                ocr_text_parts.append(page_text)

        ocr_text = "\n".join(ocr_text_parts).strip()

        ocr_preview_b64 = ""
        if include_preview_on_ocr:
            ocr_preview_b64 = safe_preview_b64(
                first_page, dpi=preview_dpi, max_chars=max_preview_b64_chars
            )

        if ocr_text:
            return PDFExtractionResult(
                extracted_text=ocr_text,
                image_base64=ocr_preview_b64,
                success=True,
                description=f"OCR successful (dpi={ocr_dpi}, pages={pages_to_ocr})",
            )
        else:
            return PDFExtractionResult(
                extracted_text="",
                image_base64=ocr_preview_b64,
                success=False,
                description="No text layer and OCR found no text",
            )

    except Exception as e:
        return PDFExtractionResult(
            extracted_text="",
            image_base64="",
            success=False,
            description=f"Error: {type(e).__name__}: {e}",
        )
    
# ---------- AGENT ----------

scholarship_extract_agent = Agent(
    name="Scholarship Extract Agent",
    instructions=(
        "You are a scholarship form extraction agent. "
        "You are going to extract the name of the scholarship recipient from the attached form."
        "Extract the amount as well and include those two pieces of information in your response."
        "The scholarship recipient is generally the name of the Payable to: person."
        "It is never Lovkarn Riar or Elisa Machado."
        "The request should always have the amount in the request, typically a Please issue a check in the amount of $X."
        "For the invoice number, use first initial, last name and append the scholarship type e.g. 'BDICKSON FIC' for first in class"
    ),
    tools=[extract_pdf_contents],
    model="gpt-5-mini",
    output_type=ScholarshipExtractedCheckAuthorization,
)

# ---------- RUNNER ----------

async def run_scholarship_extraction(invoice_path: str | Path, extra_instructions: str | None = None):
    """
    Extracts scholarship fields from a given PDF file using the invoice_scholarship_agent.

    Args:
        invoice_path (str | Path): Full or relative path to the scholarship PDF file.

    Returns:
        ScholarshipExtractedCheckAuthorization | None: Structured scholarship data if successful, else None.
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
                scholarship_extract_agent.instructions
                + "\n\nAdditional instructions:\n"
                + extra_instructions
            )
            agent = Agent(
                name=scholarship_extract_agent.name,
                instructions=merged_instructions,
                tools=scholarship_extract_agent.tools,
                model=scholarship_extract_agent.model,
                output_type=scholarship_extract_agent.output_type,
            )
        else:
            agent = scholarship_extract_agent

        #with trace("Extracting invoice fields"):
        result = await Runner.run(agent, str(invoice_path))
        print("✅ Extraction result:")
        print(result)
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
    sample_invoice = "./data/edu_test.pdf"
    asyncio.run(run_scholarship_extraction(sample_invoice))
