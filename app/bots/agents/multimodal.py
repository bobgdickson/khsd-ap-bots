from pathlib import Path
from typing import Type, List
import base64
import fitz  # PyMuPDF
from pydantic import BaseModel
from PIL import Image
import io

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langfuse import observe


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
    # Convert PNG RGBA → JPEG compatible RGB
    if image.mode in ("RGBA", "LA"):
        image = image.convert("RGB")

    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode("utf-8")

@observe(name="document_vision_extract")
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
    from pydantic import BaseModel
    from datetime import datetime
    class DirectDepositExtractResult(BaseModel):
        emplid: str
        name: str
        date: datetime
        ssn: str
        bank_name: str
        routing_number: str
        bank_account: str
        checking_account: bool
        savings_account: bool
        amount_dollars: float
        amount_percentage: float
    result = extract_to_schema(
        "./data/dd.png",
        DirectDepositExtractResult,
        prompt="""
            You are an direct deposit extraction agent.
            Use the tool to extract raw data from the document.
            Extract the following fields from the provided direct_deposit document:
            emplid, name, date, ssn, bank_name, routing_number, bank_account, checking_account, savings_account, amount_dollars, amount_percentage.
            The ssn field should only contain the last four digits of the social security number.
            The checking_account and savings_account fields should be booleans indicating whether the bank account is a checking or savings account.
            The amount_dollars field is the fixed dollar amount for direct deposit, and amount_percentage is the percentage amount for direct deposit. If one of these is not provided, set it to 0.
            The date field should be converted to YYYY-MM-DD format.
            emplid will always be a 6 digit number.
            if checking and savings account are both true, set savings_account to false.
            if checking and saving account are both false, set checking_account to true.
            if amount_dollars and amount_percentage are both blank or 0, then set percentage to 100.
            Return only valid JSON that matches the expected format.
        """
    )
    print(result.model_dump_json(indent=2))