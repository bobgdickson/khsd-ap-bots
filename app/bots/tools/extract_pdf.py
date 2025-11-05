import base64
import io

from langchain.tools import tool
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
IMAGE_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".tif",
    ".tiff",
    ".bmp",
    ".gif",
    ".webp",
}
MIN_NATIVE_TEXT_LENGTH = 30


def _pil_preview_b64(img, *, max_chars: int) -> str:
    """
    Build an image preview guaranteed to be <= max_chars in base64 length.
    Mirrors safe_preview_b64 but works with a PIL Image instance.
    """
    from PIL import Image

    try:
        working = img.convert("RGB")
        quality = 60
        width, height = working.size

        while True:
            buf = io.BytesIO()
            working.save(buf, format="JPEG", quality=quality, optimize=True)
            b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            if len(b64) <= max_chars:
                return b64

            new_w = max(int(width * 0.8), 400)
            new_h = max(int(height * 0.8), 400)
            if (new_w, new_h) == (width, height) and quality <= 45:
                return ""
            working = working.resize((new_w, new_h), Image.LANCZOS)
            width, height = new_w, new_h
            if quality > 45:
                quality -= 5
    except Exception:
        return ""


def _ocr_pil_image(img, *, lang: str, psm: int = 6) -> str:
    processed = preprocess_for_ocr(img)
    return ocr_image(processed, lang=lang, psm=psm).strip()


def _extract_image_file(
    path: Path,
    *,
    ocr_if_empty: bool,
    ocr_lang: str,
    include_preview_on_ocr: bool,
    max_preview_b64_chars: int,
) -> PDFExtractionResult:
    from PIL import Image

    with Image.open(path) as img:
        preview_b64 = ""
        if include_preview_on_ocr:
            preview_b64 = _pil_preview_b64(img, max_chars=max_preview_b64_chars)

        if not OCR_AVAILABLE:
            return PDFExtractionResult(
                extracted_text="",
                image_base64=preview_b64,
                success=False,
                description="Image OCR unavailable (pytesseract not configured)",
            )

        if not ocr_if_empty:
            return PDFExtractionResult(
                extracted_text="",
                image_base64=preview_b64,
                success=False,
                description="Image provided; OCR disabled by parameter",
            )

        ocr_text = _ocr_pil_image(img, lang=ocr_lang)
        if ocr_text:
            return PDFExtractionResult(
                extracted_text=ocr_text,
                image_base64=preview_b64,
                success=True,
                description="Image OCR successful",
            )
        else:
            return PDFExtractionResult(
                extracted_text="",
                image_base64=preview_b64,
                success=False,
                description="Image OCR found no text",
            )


@tool
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
    Extract text from a PDF or image file. If no text layer / image input, optionally OCR.
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

        suffix = path.suffix.lower()

        if suffix in IMAGE_SUFFIXES:
            return _extract_image_file(
                path,
                ocr_if_empty=ocr_if_empty,
                ocr_lang=ocr_lang,
                include_preview_on_ocr=include_preview_on_ocr,
                max_preview_b64_chars=max_preview_b64_chars,
            )

        if suffix != ".pdf":
            return PDFExtractionResult(
                extracted_text="",
                image_base64="",
                success=False,
                description=f"Unsupported file type: {suffix}",
            )

        with fitz.open(str(path)) as doc:
            if len(doc) == 0:
                return PDFExtractionResult(
                    extracted_text="",
                    image_base64="",
                    success=False,
                    description="Empty or invalid PDF",
                )

            native_text_parts = [p.get_text() for p in doc]
            native_text = "\n".join(t for t in native_text_parts if t).strip()
            native_text_length = len(native_text)

            first_page = doc[0]
            native_preview_b64 = safe_preview_b64(
                first_page, dpi=preview_dpi, max_chars=max_preview_b64_chars
            )

            sufficient_native_text = native_text_length >= MIN_NATIVE_TEXT_LENGTH
            short_native_text = native_text if not sufficient_native_text else ""

            if sufficient_native_text:
                return PDFExtractionResult(
                    extracted_text=native_text,
                    image_base64=native_preview_b64,
                    success=True,
                    description="PyMuPDF text layer",
                )

            if not (ocr_if_empty and OCR_AVAILABLE):
                description = (
                    f"Short text layer (<{MIN_NATIVE_TEXT_LENGTH} chars); OCR disabled/unavailable"
                    if short_native_text
                    else "No text layer; OCR disabled/unavailable"
                )
                return PDFExtractionResult(
                    extracted_text=short_native_text,
                    image_base64=native_preview_b64,
                    success=bool(short_native_text),
                    description=description,
                )

            ocr_text_parts = []
            pages_to_ocr = min(len(doc), max_ocr_pages)
            for i in range(pages_to_ocr):
                pix = page_pixmap(doc[i], dpi=ocr_dpi)
                pil_img = pixmap_to_pil(pix)
                page_text = _ocr_pil_image(pil_img, lang=ocr_lang, psm=6)
                if page_text:
                    ocr_text_parts.append(page_text)

            ocr_text = "\n".join(ocr_text_parts).strip()

            ocr_preview_b64 = ""
            if include_preview_on_ocr:
                ocr_preview_b64 = safe_preview_b64(
                    first_page, dpi=preview_dpi, max_chars=max_preview_b64_chars
                )

            if ocr_text:
                combined_text = "\n".join(
                    filter(None, [short_native_text, ocr_text])
                ).strip()
                return PDFExtractionResult(
                    extracted_text=combined_text,
                    image_base64=ocr_preview_b64,
                    success=True,
                    description=f"OCR successful (dpi={ocr_dpi}, pages={pages_to_ocr})",
                )
            else:
                return PDFExtractionResult(
                    extracted_text=short_native_text,
                    image_base64=ocr_preview_b64,
                    success=bool(short_native_text),
                    description="No text layer and OCR found no text",
                )

    except Exception as e:
        return PDFExtractionResult(
            extracted_text="",
            image_base64="",
            success=False,
            description=f"Error: {type(e).__name__}: {e}",
        )

