from agents import function_tool
import fitz
from pathlib import Path
from app.schemas import PDFExtractionResult
from app.bots.utils.ocr import (
    page_pixmap,
    pixmap_to_pil,
    safe_preview_b64,
    preprocess_for_ocr,
    ocr_image,
    check_ocr,
)

OCR_AVAILABLE = check_ocr()


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
    max_preview_b64_chars: int = 1_000_000,
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

