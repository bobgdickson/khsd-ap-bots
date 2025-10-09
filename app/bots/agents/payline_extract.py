from agents import Agent, Runner
from pydantic import ValidationError
import asyncio
from dotenv import load_dotenv
from pathlib import Path
from app.schemas import PaylineExcelExtractedData
from app.bots.tools.extract_payline_excel import extract_payline_excel

load_dotenv()

# ---------- AGENT ----------

payline_extract_agent = Agent(
    name="Payline Extract Agent",
    instructions=(
        "You are a Payline extract agent helping out the payroll department. "
        "Use the tool to extract raw data from the excel file."
        "Extract the following fields from the provided excel document, these will typically be in separate columns with headers indicating their contents: "
        "- tab_name: The name of the tab in the excel file where the data was found.\n"
        "- hr_requestor: The name of the HR requestor, usually found in the name of the tab (eg VERONICA_OCTOBER 2025 would be Veronica).\n"
        "- month_requested: The month the payroll is requested for, usually found in the name of the tab (eg VERONICA_OCTOBER 2025 would be October 2025).\n"
        "- emplid: Employee ID number, usually a 6 digit number.\n"
        "- empl_rcd: Employee record number, usually a small integer like 0 or 1.  If there are two in that cell (1, 2 for instance) add it to the errors list for human review.\n"
        "- ern_ded_code: Earnings or Deduction code, usually a 3 or 4 character code like 'RSA' or 'SAL'.\n"
        "- amount: The amount to be processed, usually a decimal number like 1500.00.\n"
        "- earnings_begin_dt: The start date for the earnings, usually in MM/DD/YYYY format.\n"
        "- earnings_end_dt: The end date for the earnings, usually in MM/DD/YYYY format.\n"
        "- notes: Any additional notes or comments, if available.\n"
        "If the row is incomplete and you cannot infer the data, add that row to the errors list with a brief description of the issue.\n"
        "Note that there are many tabs in the excel file, process them in order but when the month_requested changes (eg from OCTOBER to SEPTEMBER) stop processing further tabs as they are likely for a different payroll period.\n"
    ),
    tools=[extract_payline_excel],
    model="gpt-5-mini",
    output_type=PaylineExcelExtractedData,
)

# ---------- RUNNER ----------

async def run_payline_extraction(excel_path: str | Path, extra_instructions: str | None = None):
    """
    Extracts payline fields from a given excel file using the payline_extract_agent.

    Args:
        excel_path (str | Path): Full or relative path to the payline excel file.

    Returns:
        PaylineExcelExtractedData | None: Structured payline data if successful, else None.
    """
    try:
        # Normalize path
        excel_path = Path(excel_path).expanduser().resolve()
        if not excel_path.exists():
            print(f"❌ File not found: {excel_path}")
            return None

        print(f"📄 Processing: {excel_path}")

        # Build an agent, optionally appending extra instructions
        if extra_instructions:
            merged_instructions = (
                payline_extract_agent.instructions
                + "\n\nAdditional instructions:\n"
                + extra_instructions
            )
            agent = Agent(
                name=payline_extract_agent.name,
                instructions=merged_instructions,
                tools=payline_extract_agent.tools,
                model=payline_extract_agent.model,
                output_type=payline_extract_agent.output_type,
            )
        else:
            agent = payline_extract_agent

        #with trace("Extracting invoice fields"):
        result = await Runner.run(agent, str(excel_path))
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
    sample_paylines = "./data/Certificated_adjustments.xlsx"
    asyncio.run(run_payline_extraction(sample_paylines))
