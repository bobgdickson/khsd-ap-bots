from pathlib import Path
from typing import Optional
import time, asyncio, shutil, sys, os
from playwright.sync_api import sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from app.bots.utils.ps import (
    ps_target_frame,
    ps_find_retry,
    ps_find_button,
    handle_peoplesoft_alert,
    handle_alerts,
    ps_wait,
    find_rent_line,
    get_voucher_id,
    handle_modal_sequence,
    ps_login_and_navigate,
)
from app.bots.utils.misc import (
    generate_runid,
    get_invoices_in_data,
    is_run_cancel_requested,
    normalize_date,
    update_bot_run_status,
)
from app.bots.agents.invoice_extract import run_invoice_extraction
from app.bots.prompts import CDW_PROMPT, CLASS_PROMPT, MOBILE_PROMPT, GRAINGER_PROMPT
from app.schemas import ExtractedInvoiceData, VoucherEntryResult, VoucherRunLog, VoucherProcessLog
from app.config import get_settings
if sys.platform.startswith("win"):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except AttributeError:
        pass
from app import models, database

# TODO: Handle server deployment for file access
def get_vendor_directory(vendor_key: str, test_mode: bool) -> Path:
    if test_mode:
        base_dir = r"C:\Users\Bob_Dickson\OneDrive - Kern High School District\Documents\InvoiceProcessing"
        vendor_dirs = {
            "royal": "Royal Industrial",
            "class": "Class Leasing",
            "mobile": "Mobile Modular",
            "floyds": "Floyds",
            "seq": "Sequoia",
            "cdw": "CDW",
            "grainger": "Grainger",
        }
    else:
        base_dir = r"C:\Users\Bob_Dickson\OneDrive - Kern High School District\Documents - Fiscal\Accounts Payable"
        vendor_dirs = {
            "royal": "Royal Industrial",
            "class": "Class Leasing Invoices",
            "mobile": "Mobile Modular Invoices",
            "floyds": "Floyd's (Standard Plumbing) invoices",
            "seq": "Sequioa Paint",
            "cdw": "CDW",
            "attach": "Invoices scanned, need to be attached",
            "grainger": "Grainger",
        }
    return Path(base_dir) / vendor_dirs[vendor_key]


settings = get_settings()
USERNAME = settings.peoplesoft_username
PASSWORD = settings.peoplesoft_password

# Vendors that require "royal style entry"
ROYAL_STYLE_VENDORS = {"royal", "floyds", "grainger"}


def voucher_playwright_bot(
    invoice_data: ExtractedInvoiceData,
    filepath: str = None,
    royal_style_entry: bool = False,
    attach_only: bool = False,
    rent_line: str = "FY26",
    test_mode: bool = False,
    generic_attach: bool = False,
) -> VoucherEntryResult:

    apo_flag = False

    if test_mode:
        PS_BASE = settings.peoplesoft_test_env
        PS_BASE_URL = (PS_BASE + "psp/KDFQ92")
        print(f"Running in TEST mode against {PS_BASE_URL}")
    else:
        PS_BASE = settings.peoplesoft_env
        PS_BASE_URL = PS_BASE + "psp/KDFP92"
        print(f"Running in PRODUCTION mode against {PS_BASE_URL}")

    if not invoice_data:
        print("No invoice data provided, exiting.")
        return

    print(f"Extracted data for: {invoice_data}")

    with sync_playwright() as p:
        print("Starting PeopleSoft voucher entry bot...")
        try:
            # --- Login ---
            browser = p.chromium.launch(headless=False)
            page = browser.new_page()
            destination = (
                PS_BASE_URL
                + "/EMPLOYEE/ERP/c/ENTER_VOUCHER_INFORMATION.VCHR_EXPRESS.GBL"
            )
            ps_login_and_navigate(page, PS_BASE, USERNAME, PASSWORD, destination)

            # Full Voucher Entry Flow
            if not attach_only:
                # --- Voucher Entry Fields ---
                ps_find_retry(page, "Invoice Number").fill(invoice_data.invoice_number)
                ps_find_retry(page, "Invoice Date").fill(invoice_data.invoice_date)
                ps_find_retry(page, "Gross Invoice Amount").fill(
                    str(invoice_data.total_amount)
                )
                if invoice_data.shipping_amount > 0:
                    ps_find_retry(page, "Freight Amount").fill(
                        str(invoice_data.shipping_amount)
                    )
                if invoice_data.sales_tax > 0:
                    ps_find_retry(page, "Sales Tax Amount").fill(str(invoice_data.sales_tax))
                if invoice_data.miscellaneous_amount > 0:
                    ps_find_retry(page, "Misc Charge Amount").fill(
                        str(invoice_data.miscellaneous_amount)
                    )

                po_input = ps_find_retry(page, "PO Number")

                if invoice_data.purchase_order.startswith("KERNH"):
                    try:
                        bu, po = invoice_data.purchase_order.split("-", 1)
                    except:
                        bu, po = invoice_data.purchase_order.split("_", 1)
                else:
                    bu = "KERNH"
                    po = invoice_data.purchase_order
                
                # Royal Style enters PO directly at Voucher creation screen
                if royal_style_entry and invoice_data.purchase_order:
                    ps_find_retry(page, "PO Business Unit").fill(bu)
                    # This handles APO processing, to override line amount later
                    if "APO" in invoice_data.purchase_order:
                        apo_flag = True
                    po_input.fill(po)

                po_input.focus()
                for key in ["Tab", "Tab", "Tab", "Enter"]:
                    page.keyboard.press(key)
                    ps_wait(page, 1)
                page.wait_for_load_state("networkidle")

                # --- Handle Alert ---
                alert_text = handle_peoplesoft_alert(page)
                if alert_text and "Invalid value" in alert_text:
                    return VoucherEntryResult(voucher_id="Invalid PO", duplicate=False, out_of_balance=False)

                # --- Copy from PO Flow ---
                if apo_flag and royal_style_entry:
                    ps_find_retry(page, "Line Amount").fill(
                        str(invoice_data.merchandise_amount)
                    )
                    ps_find_retry(page, "MERCHANDISE_AMT_DL$0").fill(
                        str(invoice_data.merchandise_amount)
                    )
                    ps_find_retry(page, "VCHR_BAL_WRK_OD_BALANCE_PB").click()
                    page.wait_for_load_state("networkidle")
                else:
                    ps_find_button(page, "Copy From Source Document").click()
                    ps_find_retry(page, "PO Unit").fill("KERNH")
                    ps_find_retry(page, "PO Number").fill(po)
                    ps_find_button(page, "Copy PO").click()
                    page.wait_for_load_state("networkidle")
                    # Potential alert for no matching PO
                    alert_text = handle_peoplesoft_alert(page)
                    if alert_text and "Invalid value" in alert_text:
                        return VoucherEntryResult(voucher_id="Invalid PO", duplicate=False, out_of_balance=False)
                    frame = ps_target_frame(page)
                    frame.get_by_role("button", name="Search", exact=True).click()
                    page.wait_for_load_state("networkidle")

                    # Detect vendor type
                    class_mobile_flag = False
                    try:
                        ps_target_frame(page).get_by_text("CLASS").wait_for(
                            timeout=2000
                        )
                        class_mobile_flag = True
                        print("Class Leasing found in PO")
                    except PlaywrightTimeoutError:
                        try:
                            ps_target_frame(page).get_by_text(
                                "MOBILE"
                            ).wait_for(timeout=2000)
                            class_mobile_flag = True
                            print("Mobile Modular found in PO")
                        except PlaywrightTimeoutError:
                            print("No Class Leasing or Mobile Modular found.")

                    if class_mobile_flag and not find_rent_line(page, rent_line):
                        return VoucherEntryResult(voucher_id=f"No {rent_line} Rent Line on PO", duplicate=False, out_of_balance=False)

                    # Copy PO line
                    ps_target_frame(page).locator(
                        '[id="VCHR_PANELS_WRK_LINE_SELECT_PO$0"]'
                    ).check()
                    ps_wait(page, 3)
                    ps_target_frame(page).locator(
                        '[id="VCHR_MTCH_WS4_MERCHANDISE_AMT$0"]'
                    ).fill(str(invoice_data.merchandise_amount))
                    ps_wait(page, 3)
                    ps_target_frame(page).get_by_role(
                        "button", name="Copy Selected Lines"
                    ).click()
                    page.wait_for_load_state("networkidle")

                    # Handle any alerts
                    alert_text, duplicate, out_of_balance = handle_alerts(page)
                    if duplicate:
                        return VoucherEntryResult(voucher_id="Duplicate", duplicate=True, out_of_balance=False)
                    if out_of_balance:
                        return VoucherEntryResult(voucher_id="Out of Balance", duplicate=False, out_of_balance=True)

                    # Delete auto-added first line
                    ps_target_frame(page).get_by_role("button", name="Delete row").first.click()
                    ps_wait(page, 3)
                    page.get_by_role("button", name="OK").click()
                    ps_wait(page, 3)
                    page.wait_for_load_state("networkidle")
            
            # Attach Only Flow
            else:
                print("Attach-only mode")
                #TODO handle multiple pop ups for generic voucher bot entry per aiko lots of popups on some
                ps_find_button(page, "Find an Existing Value Find").click()
                ps_wait(page, 1)
                if generic_attach:
                    print("Generic attach mode - looking up voucher")
                    # Prefix voucher ID with zeroes to match format
                    while len(invoice_data.invoice_number) < 8:
                        invoice_data.invoice_number = "0" + invoice_data.invoice_number
                    ps_find_retry(page, "Voucher ID").fill(invoice_data.invoice_number)
                else:
                    ps_find_retry(page, "User ID").focus()
                    #TODO change to khedu style drop down box handling
                    for key in ["Tab", "c", "Tab"]:
                        page.keyboard.press(key)
                        ps_wait(page, 1)
                    ps_find_retry(page, "Invoice Number").fill(invoice_data.invoice_number)
                ps_target_frame(page).get_by_role("button", name="Search", exact=True).click()
                invoice_not_found = False
                ps_wait(page, 1)
                try:
                    ps_target_frame(page).get_by_text(
                                    "No matching values were found"
                                ).wait_for(timeout=2000)
                    invoice_not_found = True
                    print("Invoice not entered, skipping attachment.")
                    return VoucherEntryResult(voucher_id="No voucher", duplicate=False, out_of_balance=False)
                except PlaywrightTimeoutError:
                    print("Invoice found, proceeding with attachment.")
                    alert_text = handle_peoplesoft_alert(page)
                    if alert_text:
                        page.get_by_role("button", name="OK").click()
                    ps_target_frame(page).get_by_role("tab", name="Invoice Information").click()
                    ps_wait(page, 1)

            # --- Attachments ---
            ps_target_frame(page).get_by_role("link", name="Attachments").click()
            page.wait_for_load_state("networkidle")
            handle_modal_sequence(
                page, ["Add Attachment", "Browse", "Upload", "OK"], file=str(Path(filepath).resolve())
            )

            # --- Save ---
            ps_target_frame(page).locator("#VCHR_PANELS_WRK_VCHR_SAVE_PB").click()
            ps_wait(page, 3)

            alert_text, duplicate, out_of_balance = handle_alerts(page)
            if duplicate:
                return VoucherEntryResult(voucher_id="Duplicate", duplicate=True, out_of_balance=False)
            if out_of_balance:
                return VoucherEntryResult(voucher_id="Out of Balance", duplicate=False, out_of_balance=True)
            ps_wait(page, 3)
            voucher_id = get_voucher_id(page)
            print("Voucher ID:", voucher_id)
            return VoucherEntryResult(voucher_id=voucher_id, duplicate=False, out_of_balance=False)

        finally:
            if "browser" in locals():
                print("Closing browser...")
                browser.close()


def run_vendor_entry(
    vendor_key: str,
    test_mode: bool = True,
    rent_line: str = "FY26",
    attach_only: bool = False,
    apo_override: str = None,
    additional_instructions: str = None,
    runid: Optional[str] = None,
):
    """
    Process all invoices for one vendor in a directory.
    Returns (VoucherRunLog, list[VoucherProcessLog]).
    """
    t0 = time.time()
    vendor_path = get_vendor_directory(vendor_key, test_mode)
    if not vendor_path.exists():
        raise RuntimeError(f"Vendor directory {vendor_path} not found")

    invoices = list(vendor_path.glob("*.pdf"))
    if not invoices:
        print(f"No invoices found in {vendor_path}")
        return None, []

    runid = runid or generate_runid(
        vendor_key,
        test_mode=test_mode,
        bot_name="voucher_entry",
        context={"vendor_key": vendor_key},
    )
    runlog = VoucherRunLog(runid=runid, vendor=vendor_key)
    process_logs: list[VoucherProcessLog] = []

    if is_run_cancel_requested(runid):
        update_bot_run_status(runid, "cancelled", message="Cancelled before start")
        print(f"Run {runid} was cancelled before it started.")
        return runlog

    if vendor_key == "attach" and not attach_only:
        processed_dir = vendor_path / "Attached"
        notprocessed_dir = vendor_path
    else:
        processed_dir = vendor_path / "Processed"
        notprocessed_dir = vendor_path / "NotProcessed"
    processed_dir.mkdir(exist_ok=True)
    notprocessed_dir.mkdir(exist_ok=True)

    update_bot_run_status(
        runid,
        "running",
        context_updates={"total_invoices": len(invoices)},
    )

    print(f"\n🚀 Starting run {runid} with {len(invoices)} invoices from {vendor_path}")

    cancelled = False
    try:
        for invoice in invoices:
            if is_run_cancel_requested(runid):
                print(f"Cancellation requested for run {runid}. Stopping further processing.")
                cancelled = True
                break

            process_log: Optional[VoucherProcessLog] = None

            try:
                if vendor_key == "attach":
                    # For attach-only, we just need minimal invoice data
                    invoice_data = ExtractedInvoiceData(
                        invoice_number=invoice.stem,
                        invoice_date="",
                        total_amount=0.0,
                        merchandise_amount=0.0,
                        shipping_amount=0.0,
                        sales_tax=0.0,
                        miscellaneous_amount=0.0,
                        purchase_order="",
                    )

                    result = voucher_playwright_bot(
                        invoice_data,
                        filepath=str(invoice),
                        rent_line=rent_line,
                        attach_only=attach_only,
                        test_mode=test_mode,
                        royal_style_entry=False,
                        generic_attach=True,
                    )
                    runlog.successes += 1
                    status = "success"
                    voucher_id = result.voucher_id
                    print(f"Moving entered invoice {invoice.name} to Processed.")
                    shutil.move(str(invoice), processed_dir / invoice.name)
                else:
                    extraction_result = asyncio.run(
                        run_invoice_extraction(str(invoice), additional_instructions)
                    )

                    if not extraction_result:
                        print(f"Failed extraction: {invoice.name}")
                        runlog.failures += 1
                        process_log = VoucherProcessLog(
                            runid=runid,
                            filename=invoice.name,
                            voucher_id="Extraction Failed",
                            amount=0.0,
                            invoice="",
                            status="failure",
                        )
                    else:
                        invoice_data = extraction_result['structured_response']
                        invoice_data.purchase_order = invoice_data.purchase_order.strip()
                        invoice_data.invoice_date = normalize_date(invoice_data.invoice_date)
                        if apo_override:
                            invoice_data.purchase_order = apo_override

                        # Check if vendor_key is in the royal style set which will enter PO at voucher screen
                        royal_style = False
                        if vendor_key in ROYAL_STYLE_VENDORS:
                            royal_style = True

                        result = voucher_playwright_bot(
                            invoice_data,
                            filepath=str(invoice),
                            rent_line=rent_line,
                            attach_only=attach_only,
                            test_mode=test_mode,
                            royal_style_entry=royal_style,
                        )

                    runlog.processed += 1

                    # Move files
                    if result.duplicate:
                        runlog.duplicates += 1
                        status = "duplicate"
                        voucher_id = "Duplicate"
                        print(f"Moving duplicate invoice {invoice.name} to NotProcessed.")
                        shutil.move(str(invoice), notprocessed_dir / invoice.name)
                    elif result.voucher_id.isdigit():
                        runlog.successes += 1
                        status = "success"
                        voucher_id = result.voucher_id
                        print(f"Moving entered invoice {invoice.name} to Processed.")
                        shutil.move(str(invoice), processed_dir / invoice.name)
                    else:
                        runlog.failures += 1
                        status = "failure"
                        voucher_id = result.voucher_id
                        print(f"Not moving failed invoice {invoice.name}.")
                        # leave file in place

                    process_log = VoucherProcessLog(
                        runid=runid,
                        filename=invoice.name,
                        voucher_id=voucher_id,
                        amount=invoice_data.total_amount,
                        invoice=invoice_data.invoice_number,
                        status=status,
                    )

            except Exception as e:
                print(f"Error processing {invoice.name}: {e}")
                runlog.failures += 1
                error_message = str(e).strip() or "Unknown error"
                truncated_error = (
                    error_message if len(error_message) <= 240 else f"{error_message[:237]}..."
                )
                process_log = VoucherProcessLog(
                    runid=runid,
                    filename=invoice.name,
                    voucher_id=f"Error: {truncated_error}",
                    amount=0.0,
                    invoice="",
                    status="failure",
                )

            if process_log is None:
                continue

            process_logs.append(process_log)

            # Write to DB
            print(process_log)
            db = database.SessionLocal()
            try:
                payload = process_log.model_dump()
                orm_row = models.BotProcessLog(**payload)
                db.add(orm_row)
                db.commit()
                print("Logged to database.")
            finally:
                db.close()
    except Exception as exc:
        update_bot_run_status(runid, "failed", message=str(exc))
        raise

    t1 = time.time()
    print(f"Average time per invoice: {(t1 - t0) / len(invoices):.2f} seconds.")

    if cancelled:
        update_bot_run_status(
            runid,
            "cancelled",
            message="Cancelled by request",
            context_updates={
                "processed": runlog.processed,
                "successes": runlog.successes,
                "duplicates": runlog.duplicates,
                "failures": runlog.failures,
            },
        )
        print(f"Run {runid} cancelled after processing {runlog.processed} invoices.")
    else:
        update_bot_run_status(
            runid,
            "completed",
            context_updates={
                "processed": runlog.processed,
                "successes": runlog.successes,
                "duplicates": runlog.duplicates,
                "failures": runlog.failures,
            },
        )
        print(f"Completed run {runid}: {runlog.successes} success, {runlog.duplicates} duplicates, {runlog.failures} failures")

    return runlog



if __name__ == "__main__":
    # PRD runs
    #runlog = run_vendor_entry("royal", test_mode=False, rent_line="FY26", apo_override="KERNH-APO950043J")
    #runlog = run_vendor_entry("mobile", test_mode=False, rent_line="FY26", additional_instructions=MOBILE_PROMPT)
    #runlog = run_vendor_entry("floyds", test_mode=False, rent_line="FY26", apo_override="KERNH-APO962523J")
    #runlog = run_vendor_entry("attach", test_mode=False, attach_only=True)
    #runlog = run_vendor_entry("class", test_mode=False, rent_line="FY26", additional_instructions=CLASS_PROMPT)
    runlog = run_vendor_entry("grainger", test_mode=True, additional_instructions=GRAINGER_PROMPT)
