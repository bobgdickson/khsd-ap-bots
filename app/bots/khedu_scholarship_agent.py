from agents import Agent, Runner
from pydantic import ValidationError
import asyncio
from dotenv import load_dotenv
from pathlib import Path
from app.schemas import ScholarshipExtractedCheckAuthorization
from app.bots.tools.extract_pdf import extract_pdf_contents

load_dotenv()

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
