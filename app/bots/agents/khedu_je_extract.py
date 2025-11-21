from agents import Agent, Runner
from pydantic import ValidationError
import asyncio
from dotenv import load_dotenv
from pathlib import Path
from app.schemas import KheduJournalExtractedData
from app.bots.tools.extract_pdf import extract_pdf_contents

load_dotenv()

# ---------- AGENT ----------

journal_extract_agent = Agent(
    name="Journal Extract Agent",
    instructions=(
        "You are a Journal form extraction agent. "
        "You are going to extract the name of the Journal recipient from the attached form."
        "Extract the amount as well and include those two pieces of information in your response."
        "The name response is a student the scholarship is targeted, generally designatated Student: name."
        "If it isn't listed student it is usually the name the follows 'Pay to the order of'. or a University name."
        "It is never Lovkarn Riar, Sarinna Anchondo or Elisa Machado."
        "The journal amount will usually be indicated with a dollar sign $X and follow the word transfer."
        "Use one of the following journal types: PBEST, YWEL, PODER, Bidart"
        "Description will be a format similar to this: 'TRANSFER FROM (TYPE) TO CHECKING (AMOUNT) - (NAME)'"
        "as an example: 'TRANSFER FROM PBEST TO CHECKING 500 - JOHN DOE'"
        "Source account will be the name that usually follows the word From after the amount as in transfer $500 from Project BEST Market Account"
        "Destination account will be the name that usually follows the word To after the amount as in 'to the KHSD Checking Account'"
    ),
    tools=[extract_pdf_contents],
    model="gpt-5-mini",
    output_type=KheduJournalExtractedData,
)

# ---------- RUNNER ----------

async def run_journal_extraction(invoice_path: str | Path, extra_instructions: str | None = None):
    """
    Extracts Journal fields from a given PDF file using the invoice_journal_agent.

    Args:
        invoice_path (str | Path): Full or relative path to the Journal PDF file.

    Returns:
        KheduJournalExtractedData | None: Structured Journal data if successful, else None.
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
                journal_extract_agent.instructions
                + "\n\nAdditional instructions:\n"
                + extra_instructions
            )
            agent = Agent(
                name=journal_extract_agent.name,
                instructions=merged_instructions,
                tools=journal_extract_agent.tools,
                model=journal_extract_agent.model,
                output_type=journal_extract_agent.output_type,
            )
        else:
            agent = journal_extract_agent

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
    sample_invoice = "./edu_je.pdf"
    asyncio.run(run_journal_extraction(sample_invoice))
