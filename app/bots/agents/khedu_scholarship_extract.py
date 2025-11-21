from langchain.agents import create_agent
from pydantic import ValidationError
import asyncio
from dotenv import load_dotenv
from pathlib import Path
from app.schemas import ScholarshipExtractedCheckAuthorization
from app.bots.tools.extract_pdf import extract_pdf_contents
from app.services.langfuse import langfuse_handler

load_dotenv()

# ---------- AGENT PARAMS ----------

name="Scholarship Extract Agent"
system_prompt="""
    You are a scholarship form extraction agent.
    Use the tool to extract raw data from the document.
    Extract the name of the scholarship recipient and the scholarship amount from the document.
    The scholarship recipient is generally the name of the Payable to: person.
    It is never Lovkarn Riar or Elisa Machado.
    The request should always have the amount in the request, typically phrased as: Please issue a check in the amount of $X.
    For the invoice number, use first initial, last name and append the scholarship type e.g. 'BDICKSON FIC' for first in class.
    Return only valid JSON that matches the expected format.
"""
tools=[extract_pdf_contents]
model="gpt-5-mini"
response_format=ScholarshipExtractedCheckAuthorization


# ---------- RUNNER ----------

async def run_scholarship_extraction(invoice_path: str | Path, extra_instructions: str | None = None):
    """
    Extracts scholarship fields from a given PDF file using the scholarship extract agent.

    Args:
        invoice_path (str | Path): Full or relative path to the scholarship PDF file.

    Returns:
        ScholarshipExtractedCheckAuthorization | None: Structured scholarship data if successful, else None.
    """
    try:
        invoice_path = Path(invoice_path).expanduser().resolve()
        if not invoice_path.exists():
            print(f"[ERROR] File not found: {invoice_path}")
            return None

        print(f"[INFO] Processing: {invoice_path}")
        input_payload = {"messages": [{"role": "user", "content": str(invoice_path)}]}

        if extra_instructions:
            merged_instructions = system_prompt + "\n\nAdditional instructions:\n" + extra_instructions
            agent = create_agent(
                name=name,
                system_prompt=merged_instructions,
                tools=tools,
                model=model,
                response_format=response_format,
            )
        else:
            agent = create_agent(
                name=name,
                system_prompt=system_prompt,
                tools=tools,
                model=model,
                response_format=response_format,
            )

        result = agent.invoke(input_payload, config={"callbacks": [langfuse_handler]})
        print("[INFO] Extraction result:")
        structured_response = result.get("structured_response", result)
        print(structured_response)
        return result

    except ValidationError as ve:
        print("[ERROR] Validation error in extracted data:")
        print(ve)
        return None

    except Exception as e:
        print("[ERROR] Unexpected error during scholarship extraction")
        print(e)
        return None

# ---------- MAIN ----------

if __name__ == "__main__":
    sample_invoice = "./data/edu_test.pdf"
    asyncio.run(run_scholarship_extraction(sample_invoice))
