
import fitz
import io, os
import base64
import pytesseract
from dotenv import load_dotenv

load_dotenv()

# ---------- helpers ----------

def check_ocr():
    # OCR deps
    try:
        import pytesseract
        cmd = os.getenv("TESSERACT_CMD")
        if cmd:
            cmd = os.path.expandvars(cmd)  # lets you use %LOCALAPPDATA% if you prefer
            pytesseract.pytesseract.tesseract_cmd = cmd
        from PIL import Image, ImageOps, ImageFilter
        OCR_AVAILABLE = True
    except Exception:
        OCR_AVAILABLE = False
    return OCR_AVAILABLE

def page_pixmap(page, dpi: int) -> fitz.Pixmap:
    scale = dpi / 72.0
    return page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)

def pixmap_to_pil(pix: fitz.Pixmap):
    buf = io.BytesIO(pix.tobytes("png"))
    from PIL import Image  # local import to avoid hard dep if not needed
    return Image.open(buf)

def safe_preview_b64(page, dpi=140, *, max_chars=1_000_000) -> str:
    """
    Build an image preview guaranteed to be <= max_chars in base64 length.
    Uses JPEG + iterative downscale if needed; returns '' if it can't fit.
    """
    try:
        from PIL import Image
        pix = page_pixmap(page, dpi=dpi)
        img = pixmap_to_pil(pix).convert("RGB")

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

def preprocess_for_ocr(img):
    from PIL import ImageOps, ImageFilter
    g = ImageOps.grayscale(img)
    g = ImageOps.autocontrast(g)
    return g.filter(ImageFilter.MedianFilter(3))

def ocr_image(img, lang="eng", psm=6) -> str:
    config = f"--oem 3 --psm {psm}"
    return pytesseract.image_to_string(img, lang=lang, config=config)
