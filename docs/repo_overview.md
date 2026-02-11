# KHSD AP Bots: Overview for Non‑Engineers

This repo hosts automation “bots” that read documents, extract data with AI, and enter that data into PeopleSoft via Playwright (browser automation). Below is a quick tour of the pieces you’ll touch when adding or adjusting agents.

## Core Pieces
- **Agents (app/bots/agents/…)**: Small wrappers that call an LLM (OpenAI) with a prompt and, when needed, tools (e.g., PDF parsing). Example: `invoice_extract.py`, `multimodal.py`.
- **Tools (app/bots/tools/…)**: Helpers the agents can call, such as `extract_pdf.py` to pull text/images from PDFs or images.
- **Schemas (app/schemas.py)**: Pydantic models that define the structured data shape the LLM must return (e.g., invoice fields, direct deposit fields).
- **Playwright Bots (app/bots/*.py)**: Browser automations that log into PeopleSoft and enter data. They consume the structured output from agents (e.g., `voucher_entry.py`, `direct_deposit_entry.py`).
- **Voucher v2 Pipeline (app/bots/voucher/…)**: A staged flow that extracts an invoice, identifies a PO, loads PO lines from the database, maps invoice lines to PO lines, and then executes entry. Components:
  - `extraction_stage.py`: Runs the multimodal extractor to get invoice data.
  - `po_identifier.py`: Uses an LLM + DB-backed search tool to pick the correct PO.
  - `po_sql.py`: SQL helpers to pull PO lines from PeopleSoft DB (`PS_DB_URL`).
  - `line_mapper.py`: LLM to map invoice lines to PO lines.
  - `executor.py`: Playwright actions to enter and attach documents.
  - `pipeline.py`: Orchestrates all steps.
- **Database Models (app/models.py)**: SQLAlchemy models for logging runs/processes (voucher logs, direct deposit logs, agent registry).
- **Migrations (alembic/…​)**: Alembic scripts to create/update tables (run via Alembic CLI).

## Key Libraries and What They Do
- **LangChain / LangChain OpenAI**: Sends prompts and structured schemas to OpenAI models; `create_agent` builds an agent that can call tools. `ChatOpenAI.with_structured_output` enforces schema returns.
- **Pydantic**: Defines and validates structured outputs (schemas). The LLM output is validated into these models.
- **Playwright**: Automates the PeopleSoft UI for data entry (fill fields, click buttons, upload attachments).
- **SQLAlchemy**: Database access and models for logging runs and reading PeopleSoft POs.
- **PyMuPDF / PIL / Tesseract (OCR)**: Used inside `extract_pdf.py` to get text and a base64 preview image from PDFs/images.
- **Langfuse**: Callback/observability for LLM calls (optional).

## Typical Flow to Add/Modify an Agent
1) **Define the schema**: Add or reuse a Pydantic model in `app/schemas.py` that represents the data you need.
2) **Write a prompt**: In an agent (or pipeline stage), craft clear instructions that tell the model exactly what fields to return and any domain rules.
3) **Build the agent**: Use `create_agent` (or `extract_to_schema` in `multimodal.py`) with your prompt and target schema; attach tools if needed (e.g., `extract_pdf_contents`).
4) **Consume the result**: Pass the structured output into the Playwright bot (fill fields, attach files) or downstream logic.
5) **Log the run**: Persist run/process logs via the SQLAlchemy models where appropriate.

## Environment and Config
- **.env**: Holds API keys and URLs. Important keys: `OPENAI_API_KEY`, PeopleSoft URLs (`PEOPLESOFT_ENV`, `PEOPLESOFT_TEST_ENV`, etc.), DB URLs (`DATABASE_URL`, `PS_DB_URL`), Langfuse keys.
- **PS_DB_URL vs DATABASE_URL**: `PS_DB_URL` is for the PeopleSoft DB (used by `po_sql.py`); `DATABASE_URL` is for the internal scratch/data warehouse.

## Running and Testing
- **Smoke scripts**: Some modules have `if __name__ == "__main__":` blocks for quick manual checks.
- **Pytest**: Unit tests live in `tests/`. Run `pytest` to execute; many tests monkeypatch network/DB calls to avoid external dependencies.
- **Alembic**: Use Alembic CLI to apply migrations when models change (new logging tables, etc.).

## Adding a New Agent (Example)
1) Create a schema in `app/schemas.py` for the fields you need.
2) Write a prompt and agent in `app/bots/agents/…` (or use `multimodal.extract_to_schema` if vision is needed).
3) If the agent must parse PDFs/images, rely on `extract_pdf.py` as a tool.
4) Wire the output into a Playwright bot for data entry if required.
5) Add tests in `tests/` to validate the agent’s parsing and any downstream logic.
