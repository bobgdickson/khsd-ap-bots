from langchain.agents import create_agent
from pydantic import ValidationError
import asyncio
from dotenv import load_dotenv
from pathlib import Path
from app.schemas import DirectDepositExtractResult
from app.bots.tools.extract_pdf import extract_pdf_contents
from app.services.langfuse import langfuse_handler

load_dotenv()

# ---------- AGENT PARAMS ----------


name="Direct Deposit Extract Agent"
system_prompt="""
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
tools=[extract_pdf_contents]
model="gpt-5-mini"
response_format=DirectDepositExtractResult


# ---------- RUNNER ----------

async def run_direct_deposit_extraction(direct_deposit_path: str | Path, extra_instructions: str | None = None):
    """
    Extracts direct_deposit fields from a given PDF file using the direct_deposit_extract_agent.

    Args:
        direct_deposit_path (str | Path): Full or relative path to the direct_deposit PDF file.

    Returns:
        Extracteddirect_depositData | None: Structured direct_deposit data if successful, else None.
    """
    try:
        # Normalize path
        direct_deposit_path = Path(direct_deposit_path).expanduser().resolve()
        if not direct_deposit_path.exists():
            print(f"❌ File not found: {direct_deposit_path}")
            return None

        print(f"📄 Processing: {direct_deposit_path}")
        input = {"messages": [{"role": "user", "content": str(direct_deposit_path)}]}
        # Build an agent, optionally appending extra instructions
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

        result = agent.invoke(input, config={"callbacks": [langfuse_handler]})
        print("✅ Extraction result:")
        print(result['structured_response'])
        return result

    except ValidationError as ve:
        print("❌ Validation error in extracted data:")
        print(ve)
        return None

    except Exception as e:
        print("❌ Unexpected error during direct_deposit extraction")
        print(e)
        return None

# ---------- MAIN ----------

if __name__ == "__main__":
    sample_direct_deposit = "dd_ex.png"
    asyncio.run(run_direct_deposit_extraction(sample_direct_deposit, extra_instructions="test."))
