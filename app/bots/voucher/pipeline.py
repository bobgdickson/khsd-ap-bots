from pathlib import Path
from typing import Iterable

from pydantic import BaseModel

from .extraction_stage import run_extraction
from .po_identifier import identify_po
from .po_sql import load_po_lines
from .line_mapper import generate_line_mapping
from .executor import execute_voucher_entry
from .models import VoucherEntryPlan
from .vendor_detection import detect_vendor, load_special_vendor_prompts
from .review_agent import review_plan
from app.bots.voucher.utils import (
    is_numeric_voucher,
    move_invoice_file,
    log_process_to_db,
    generate_runid,
)

def run_v2_voucher(
    filepath: str,
    page,
    special_vendor_prompts: dict[str, dict[str, str]] | None = None,
    test_mode: bool = True,
    runid: str | None = None,
    processed_dir: Path | None = None,
    duplicates_dir: Path | None = None,
    playwright=None,
):
    print(f"[PIPELINE] Starting voucher v2 for file: {filepath}")
    special_prompts = special_vendor_prompts or load_special_vendor_prompts()
    print(f"[PIPELINE] Loaded special vendor prompts for vendors: {list(special_prompts.keys())}")

    # Stage 0 - Detect vendor for special handling prompt
    detected_vendor, vendor_prompts = detect_vendor(filepath, special_prompts)
    print(f"[PIPELINE] Detected vendor: {detected_vendor}, has special prompts: {bool(vendor_prompts)}")
    if detected_vendor and not vendor_prompts:
        vendor_prompts = special_prompts.get(detected_vendor.lower())
    extraction_prompt = vendor_prompts.get("extraction") if vendor_prompts else None
    po_prompt = vendor_prompts.get("po_identifier") if vendor_prompts else None

    # Stage 1 - Extract
    print("[PIPELINE] Running extraction...")
    invoice = run_extraction(filepath, extra_prompt=extraction_prompt)
    print(f"[PIPELINE] Extracted invoice: {invoice.invoice_number}, vendor: {invoice.vendor_name}")

    # Stage 2 - Validate PO
    print("[PIPELINE] Identifying PO...")
    validated_po = identify_po(invoice, filepath, extra_prompt=po_prompt)
    print(f"[PIPELINE] Validated PO: {validated_po.po_id} (confidence={validated_po.confidence})")

    # Stage 3 - Load PO Lines
    print("[PIPELINE] Loading PO lines...")
    po_lines = load_po_lines(validated_po.po_id)
    print(f"[PIPELINE] Loaded {len(po_lines)} PO lines")

    # Stage 4 - Line Mapping
    print("[PIPELINE] Generating line mapping...")
    mapping = generate_line_mapping(invoice, po_lines, filepath, extra_prompt=po_prompt)
    print(f"[PIPELINE] Mapping strategy: {mapping.strategy}, mapped lines: {len(mapping.lines)}")

    # Consolidate mapping lines by PO line (sum amounts)
    consolidated: dict[int, float] = {}
    for entry in mapping.lines:
        consolidated[entry.po_line] = consolidated.get(entry.po_line, 0.0) + entry.amount
    if len(consolidated) != len(mapping.lines):
        print(f"[PIPELINE] Consolidated mapping lines from {len(mapping.lines)} to {len(consolidated)}")
    mapping.lines = [
        type(mapping.lines[0])(po_line=po_line, amount=round(amount, 2)) for po_line, amount in consolidated.items()
    ]

    # Build the plan
    plan = VoucherEntryPlan(
        po=validated_po,
        invoice=invoice,
        mapping=mapping,
        attachment_path=filepath,
        po_lines=po_lines,
    )

    # Stage 5 - Execute
    print("[PIPELINE] Reviewing plan before execution...")
    decision = review_plan(plan, extra_prompt=po_prompt)
    print(f"[PIPELINE] Review decision: execute={decision.execute}, reason={decision.reason}")

    if not decision.execute:
        result = {
            "voucher_id": "ReviewBlocked",
            "duplicate": False,
            "out_of_balance": False,
            "alert": decision.reason,
        }
    else:
        print("[PIPELINE] Executing voucher entry...")
        result = execute_voucher_entry(plan, test_mode=test_mode, page=page, playwright=playwright)
        print("[PIPELINE] Execution result:", result)
    try:
        if not test_mode:
            move_invoice_file(filepath, result, processed_dir, duplicates_dir)
        status = (
            "duplicate"
            if result.get("duplicate")
            else "success"
            if is_numeric_voucher(result.get("voucher_id"))
            else "failure"
        )
        review_reason = ""
        if result.get("voucher_id") == "ReviewBlocked":
            reason_text = decision.short_reason or decision.reason or result.get("alert", "")
            review_reason = f" Review reason: {reason_text}"
        log_process_to_db(
            runid=runid,
            filename=Path(filepath).name,
            voucher_id=result.get("voucher_id", ""),
            amount=invoice.total_amount,
            invoice_number=invoice.invoice_number,
            status=status + review_reason,
        )
    except Exception as e:
        print(f"[PIPELINE] Post-processing error: {e}")
    return result


def run_v2_voucher_dir(
    directory: str | Path,
    page,
    test_mode: bool = True,
    special_vendor_prompts: dict[str, dict[str, str]] | None = None,
    runid: str | None = None,
    processed_dir: Path | None = None,
    duplicates_dir: Path | None = None,
):
    """
    Process all PDFs in a directory with the v2 pipeline.
    """
    directory = Path(directory).expanduser().resolve()
    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")

    special_prompts = special_vendor_prompts or load_special_vendor_prompts()
    runid = runid or generate_runid(
        f"{directory.name}_v2",
        test_mode=test_mode,
        bot_name="voucher_v2_pipeline",
        context={"directory": str(directory)},
    )

    processed_dir = processed_dir or (directory / "Processed")
    duplicates_dir = duplicates_dir or (directory / "Duplicates")

    files: Iterable[Path] = directory.glob("*.pdf")
    results = []
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        for f in files:
            print(f"[PIPELINE] Processing file: {f.name}")
            try:
                result = run_v2_voucher(
                    str(f),
                    page,
                    special_vendor_prompts=special_prompts,
                    test_mode=test_mode,
                    runid=runid,
                    processed_dir=processed_dir,
                    duplicates_dir=duplicates_dir,
                    playwright=p,
                )
                results.append((f.name, result))
            except Exception as e:
                print(f"[PIPELINE] Error processing {f.name}: {e}")
                results.append((f.name, {"error": str(e)}))
    return results

if __name__ == "__main__":
    directory = r"C:\Users\Bob_Dickson\OneDrive - Kern High School District\Documents - Fiscal\Accounts Payable\Vestis"
    results = run_v2_voucher_dir(directory, page=None, test_mode=False)
    from pprint import pprint
    pprint(results)
