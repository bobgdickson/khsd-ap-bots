from pathlib import Path
from typing import Type, List
import base64
import fitz  # PyMuPDF
from pydantic import BaseModel
from PIL import Image
import io

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

# Load dotenv if needed and get openAI API key from env
from dotenv import load_dotenv
load_dotenv()
import os


def _pdf_to_images(pdf_path: str, dpi: int = 180) -> List[Image.Image]:
    """Render all pages of a PDF to PIL images."""
    doc = fitz.open(pdf_path)
    images = []
    for page in doc:
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        images.append(img)
    doc.close()
    return images


def _image_to_base64(image: Image.Image) -> str:
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def extract_to_schema(
    file_path: str,
    schema: Type[BaseModel],
    *,
    prompt: str = "Extract structured data according to the schema."
) -> BaseModel:
    """
    Universal extractor:
    - Accepts PDF or image
    - Calls multimodal LLM
    - Validates output to provided Pydantic schema
    """
    path = Path(file_path)
    ext = path.suffix.lower()

    # 1️⃣ Convert file → list of PIL images
    if ext == ".pdf":
        images = _pdf_to_images(str(path))
    elif ext in {".png", ".jpg", ".jpeg", ".tiff", ".bmp"}:
        images = [Image.open(path)]
    else:
        raise ValueError(f"Unsupported file: {file_path}")

    # 2️⃣ Convert 1st page (or best page later) to base64
    b64 = _image_to_base64(images[0])

    # 3️⃣ Construct multimodal message with explicit schema contract
    model = ChatOpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        model="gpt-5-mini",  # or gpt-5-mini if enabled
        temperature=0
    ).with_structured_output(schema)

    message = HumanMessage(
        content=[
            {"type": "text", "text": prompt},
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{b64}"
                }
            }
        ]
    )

    # 4️⃣ Invoke model → returns validated Pydantic object
    return model.invoke([message])

# Example usage:
if __name__ == "__main__":
    from app.schemas import ExtractedInvoiceData

    result = extract_to_schema(
        "./data/cdw.pdf",
        ExtractedInvoiceData,
        prompt="Extract the invoice details as per the schema."
    )
    print(result.model_dump_json(indent=2))