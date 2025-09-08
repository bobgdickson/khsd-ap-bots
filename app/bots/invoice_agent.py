from agents import Agent, Runner, trace, function_tool
from pydantic import BaseModel, ValidationError
import base64
import fitz
import io
import asyncio
import os
from dotenv import load_dotenv
from pathlib import Path
from app.schemas import ExtractedInvoiceData

load_dotenv()

# OCR deps
try:
    import pytesseract
    cmd = os.getenv("TESSERACT_CMD")
    if cmd:
        cmd = os.path.expandvars(cmd)  # lets you use %LOCALAPPDATA% if you prefer
        pytesseract.pytesseract.tesseract_cmd = cmd
    from PIL import Image, ImageOps, ImageFilter
    _OCR_AVAILABLE = True
except Exception:
    _OCR_AVAILABLE = False

class PDFExtractionResult(BaseModel):
    extracted_text: str
    image_base64: str
    success: bool
    description: str

# ---------- helpers ----------

def _page_pixmap(page, dpi: int) -> fitz.Pixmap:
    scale = dpi / 72.0
    return page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)

def _pixmap_to_pil(pix: fitz.Pixmap):
    buf = io.BytesIO(pix.tobytes("png"))
    from PIL import Image  # local import to avoid hard dep if not needed
    return Image.open(buf)

def _safe_preview_b64(page, dpi=140, *, max_chars=1_000_000) -> str:
    """
    Build an image preview guaranteed to be <= max_chars in base64 length.
    Uses JPEG + iterative downscale if needed; returns '' if it can't fit.
    """
    try:
        from PIL import Image
        pix = _page_pixmap(page, dpi=dpi)
        img = _pixmap_to_pil(pix).convert("RGB")

        quality = 60
        width, height = img.size

        while True:
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality, optimize=True)
            b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            if len(b64) <= max_chars:
                return b64
            # shrink & (lightly) drop quality
            new_w = max(int(width * 0.8), 400)
            new_h = max(int(height * 0.8), 400)
            if (new_w, new_h) == (width, height) and quality <= 45:
                return ""  # give up, safer to omit
            img = img.resize((new_w, new_h), Image.LANCZOS)
            width, height = new_w, new_h
            if quality > 45:
                quality -= 5
    except Exception:
        return ""

def _preprocess_for_ocr(img):
    from PIL import ImageOps, ImageFilter
    g = ImageOps.grayscale(img)
    g = ImageOps.autocontrast(g)
    return g.filter(ImageFilter.MedianFilter(3))

def _ocr_image(img, lang="eng", psm=6) -> str:
    config = f"--oem 3 --psm {psm}"
    return pytesseract.image_to_string(img, lang=lang, config=config)

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
        native_preview_b64 = _safe_preview_b64(
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
        if not (ocr_if_empty and _OCR_AVAILABLE):
            return PDFExtractionResult(
                extracted_text="",
                image_base64=native_preview_b64,
                success=False,
                description="No text layer; OCR disabled/unavailable",
            )

        ocr_text_parts = []
        pages_to_ocr = min(len(doc), max_ocr_pages)
        for i in range(pages_to_ocr):
            pix = _page_pixmap(doc[i], dpi=ocr_dpi)
            pil_img = _pixmap_to_pil(pix)
            pil_img = _preprocess_for_ocr(pil_img)
            page_text = _ocr_image(pil_img, lang=ocr_lang, psm=6)
            if page_text:
                ocr_text_parts.append(page_text)

        ocr_text = "\n".join(ocr_text_parts).strip()

        ocr_preview_b64 = ""
        if include_preview_on_ocr:
            ocr_preview_b64 = _safe_preview_b64(
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

invoice_extract_agent = Agent(
    name="Invoice Extract Agent",
    instructions=(
        "You are an invoice extraction agent. "
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
