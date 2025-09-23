from pathlib import Path
import os, time, asyncio, shutil
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from app.bots.utils.ps import (
    ps_target_frame,
    ps_find_retry,
    ps_find_button,
    handle_peoplesoft_alert,
    handle_alerts,
    ps_wait,
    get_voucher_id,
    handle_modal_sequence,
)
from app.bots.utils.misc import normalize_date, generate_runid, get_invoices_in_data
from app.bots.khedu_scholarship_agent import run_scholarship_extraction
from app.bots.prompts import FIC_PROMPT
from app.schemas import ScholarshipExtractedCheckAuthorization, VoucherEntryResult, VoucherRunLog, VoucherProcessLog
from app import models, database
import sqlalchemy

load_dotenv()

USERNAME = os.getenv("PEOPLESOFT_USERNAME")
PASSWORD = os.getenv("PEOPLESOFT_PASSWORD")

def run_raw_sql() -> str:
    db_url = os.getenv("PS_DB_URL")
    # Subquery to get the highest voucher_id for KHEDU
    query = """
    SELECT CHARTFIELD2
    FROM PS_VCHR_ACCTG_LINE
    WHERE BUSINESS_UNIT = 'KHEDU'
      AND VOUCHER_ID = (
          SELECT MAX(VOUCHER_ID)
          FROM PS_VCHR_ACCTG_LINE
          WHERE BUSINESS_UNIT = 'KHEDU'
      )
      AND DST_ACCT_TYPE = 'DST'
    """
    engine = sqlalchemy.create_engine(db_url)
    with engine.connect() as conn:
        result = conn.execute(sqlalchemy.text(query))
        rows = result.fetchall()
        #print(rows)
        return str(rows[0][0])

def scholarship_playwright_bot(
    scholarship_data: ScholarshipExtractedCheckAuthorization,
    scholarship_resource: str,
    filepath: str = None,
    test_mode: bool = False,
) -> VoucherEntryResult:

    if test_mode:
        PS_BASE_URL = (
            os.getenv("PEOPLESOFT_TEST_ENV", "https://kdfq92.hosted.cherryroad.com/")
            + "psp/KDFQ92"
        )
        print(f"Running in TEST mode against {PS_BASE_URL}")
    else:
        PS_BASE_URL = os.getenv("PEOPLESOFT_ENV") + "psp/KDFP92"
        print(f"Running in PRODUCTION mode against {PS_BASE_URL}")

    if not scholarship_data:
        print("No scholarship data provided, exiting.")
        return

    print(f"Extracted data for: {scholarship_data}")

    with sync_playwright() as p:
        print("Starting PeopleSoft voucher entry bot...")
        try:
            # --- Login ---
            browser = p.chromium.launch_persistent_context("user_data", headless=False)
            page = browser.new_page()
            page.set_viewport_size({"width": 1920, "height": 1080})
            page.goto(PS_BASE_URL)

            page.wait_for_selector("input#i0116")
            page.fill("input#i0116", USERNAME)
            page.click('input[type="submit"]')

            page.wait_for_selector("input#i0118")
            page.fill("input#i0118", PASSWORD)
            page.click('input[type="submit"]')
            page.wait_for_load_state("networkidle")

            # Look for latest Goal code in a voucher and correct history on next one to rename to payee
            page.goto(
                PS_BASE_URL
                + "/EMPLOYEE/ERP/c/DESIGN_CHARTFIELDS.FS_CF_VALUE_HOME.GBL"
            )
            page.wait_for_load_state("networkidle")
            
            ps_target_frame(page).get_by_role("link", name="Goal").click()
            page.wait_for_load_state("networkidle")
            ps_target_frame(page).get_by_role("textbox", name="SetID").fill("KHEDU")
            latest_goal_code = run_raw_sql()
            if latest_goal_code == "999":
                goal_code = "100"
            else:
                try:
                    goal_code = str(int(latest_goal_code) + 1)
                except (TypeError, ValueError):
                    print(f"Invalid latest_goal_code: {latest_goal_code}, defaulting to 100")
                    goal_code = "100"
                print(goal_code)
            ps_target_frame(page).get_by_role("textbox", name="Goal").fill(goal_code)
            ps_target_frame(page).get_by_role("button", name="Search", exact=True).click()
            ps_wait(page, 1)
            ps_target_frame(page).get_by_role("button", name="Correct History").click()
            ps_wait(page, 1)
            page.wait_for_load_state("networkidle")
            ps_target_frame(page).locator("[id=\"CHARTFIELD2_TBL_EFFDT$0\"]").fill("t")
            page.keyboard.press("Tab")
            page.wait_for_load_state("networkidle")
            ps_target_frame(page).locator("[id=\"CHARTFIELD2_TBL_DESCR$0\"]").fill(scholarship_data.name)
            short_descr = scholarship_data.invoice_number.split(" ")[0]
            ps_target_frame(page).locator("[id=\"CHARTFIELD2_TBL_DESCRSHORT$0\"]").fill(short_descr)
            ps_target_frame(page).get_by_role("button", name="Save").click()
            page.pause()
            ps_wait(page, 1)
            page.wait_for_load_state("networkidle")
            page.pause()
            
            # Full Voucher Entry Flow
            # --- Voucher Entry Fields ---
            page.goto(
                PS_BASE_URL
                + "/EMPLOYEE/ERP/c/ENTER_VOUCHER_INFORMATION.VCHR_EXPRESS.GBL"
            )
            
            page.wait_for_load_state("networkidle")
            bu = ps_target_frame(page).get_by_role("textbox", name="Business Unit", exact=True)
            bu.focus()
            bu.fill("KHEDU")
            ps_target_frame(page).get_by_label("Voucher Style").select_option(value="Single Payment Voucher")
            
            #page.keyboard.press("s")
            ps_wait(page, 0.33)
            
            ps_find_retry(page, "Supplier ID").fill("0000000001")
            page.keyboard.press("Tab")
            ps_wait(page, 0.33)
            ps_find_retry(page, "Invoice Number").fill(scholarship_data.invoice_number)
            ps_find_retry(page, "Invoice Date").fill("T")
            ps_find_retry(page, "Gross Invoice Amount").fill(
                str(scholarship_data.amount)
            )
            ps_target_frame(page).get_by_role("checkbox", name="Tax Exempt Flag").check()

            ps_target_frame(page).get_by_role("button", name="Add", exact=True).click()
            page.wait_for_load_state("networkidle")
            ps_wait(page, 1)
            
            # --- Handle Alert ---
            alert_text = handle_peoplesoft_alert(page)
            if alert_text and "Invalid value" in alert_text:
                return VoucherEntryResult(voucher_id="Invalid PO", duplicate=False, out_of_balance=False)
            elif alert_text and "duplicate" in alert_text:
                return VoucherEntryResult(voucher_id="Duplicate", duplicate=True, out_of_balance=False)
      
            # --- Scholarship Entry
            ps_find_retry(page, "Supplier Name").fill(scholarship_data.name)
            ps_target_frame(page).locator("#VCHR_VNDR_INFO_ADDRESS1").fill("5801 Sundale Ave")
            ps_target_frame(page).locator("#VCHR_VNDR_INFO_CITY").fill("Bakersfield")
            ps_target_frame(page).locator("#VCHR_VNDR_INFO_COUNTY").fill("Kern")
            ps_target_frame(page).locator("#VCHR_VNDR_INFO_STATE").fill("CA")
            ps_target_frame(page).locator("#VCHR_VNDR_INFO_POSTAL").fill("93309")
            ps_target_frame(page).get_by_role("tab", name="Invoice Information").click()
            ps_target_frame(page).locator("[id=\"FUND_CODE$0\"]").fill("01")
            ps_target_frame(page).locator("[id=\"PROGRAM_CODE$0\"]").fill(scholarship_resource)
            ps_target_frame(page).locator("[id=\"CHARTFIELD2$0\"]").fill(goal_code)
            ps_target_frame(page).locator("[id=\"CHARTFIELD3$0\"]").fill("100")
            ps_target_frame(page).locator("[id=\"ACCOUNT$0\"]").fill("500")
            
            
            # --- Attachments ---
            #ps_target_frame(page).get_by_role("link", name="Attachments").click()
            #page.wait_for_load_state("networkidle")
            #handle_modal_sequence(
                #page, ["Add Attachment", "Browse", "Upload", "OK"], file=str(Path(filepath).resolve())
            #)

            # --- Save ---
            ps_target_frame(page).locator("#VCHR_PANELS_WRK_VCHR_SAVE_PB").click()
            ps_wait(page, 3)

            alert_text, duplicate, out_of_balance = handle_alerts(page)
            if duplicate:
                return VoucherEntryResult(voucher_id="Duplicate", duplicate=True, out_of_balance=False)
            if out_of_balance:
                return VoucherEntryResult(voucher_id="Out of Balance", duplicate=False, out_of_balance=True)
            ps_wait(page, 1)
            voucher_id = get_voucher_id(page)
            print("Voucher ID:", voucher_id)
            page.pause()
            # --- Voucher Post, Journal Generate
            ps_target_frame(page).get_by_label("Action").select_option(value="Voucher Post")
            ps_target_frame(page).get_by_role("button", name="Run").click()
            ps_wait(page, 1)
            ok_button = page.get_by_role("button", name="Yes")
            ok_button.click()
            ps_wait(page, 10)
            try:
                ps_target_frame(page).get_by_label("Action").select_option(value="Journal Generate")
            except:
                ps_wait(page, 5)
            page.pause()
            ps_target_frame(page).get_by_label("Action").select_option(value="Journal Generate")
            ps_target_frame(page).get_by_role("button", name="Run").click()
            page.pause()
            ok_button = page.get_by_role("button", name="Yes")
            ok_button.click()
            ps_wait(page, 5)


            # Payments 
            ps_target_frame(page).get_by_role("tab", name="Payments").click()
            page.wait_for_load_state("networkidle")
            ps_target_frame(page).get_by_role("link", name="Express Payment").click()
            page.wait_for_load_state("networkidle")
            ps_target_frame(page).get_by_role("button", name="Create Payment").click()
            page.wait_for_load_state("networkidle")
            page.pause()
            ps_target_frame(page).get_by_role("button", name="Refresh").click()
            ps_wait(page, 4)
            ps_target_frame(page).get_by_role("button", name="Process")
            
            page.pause()

            # --- Return entry result
            return VoucherEntryResult(voucher_id=voucher_id, duplicate=False, out_of_balance=False)
        finally:
            if "browser" in locals():
                print("Closing browser...")
                browser.close()


def run_scholarship_entry(scholarship_key: str, test_mode: bool = True, additional_instructions: str = None):
    """
    Process all invoices for one scholarship in a directory.
    Returns (VoucherRunLog, list[VoucherProcessLog]).
    """
    t0 = time.time()
    if test_mode:
        base_dir = r"C:\Users\Bob_Dickson\OneDrive - Kern High School District\Documents\InvoiceProcessing"
        # Directory mapping (folder names → scholarship_key)
        VENDOR_DIRS = {
            "fic": "fic",
        }
    else:
        base_dir = r"C:\Users\Bob_Dickson\OneDrive - Kern High School District\Documents\InvoiceProcessing"
        # Directory mapping (folder names → scholarship_key)
        VENDOR_DIRS = {
            "fic": "fic",
        }
    #TODO: Build resource lookup table for various scholarships
    scholarship_resource = '363'
    vendor_path = Path(base_dir) / VENDOR_DIRS[scholarship_key]
    if not vendor_path.exists():
        raise RuntimeError(f"Vendor directory {vendor_path} not found")

    invoices = list(vendor_path.glob("*.pdf"))
    if not invoices:
        print(f"No invoices found in {vendor_path}")
        return None, []

    runid = generate_runid(scholarship_key, test_mode)
    runlog = VoucherRunLog(runid=runid, vendor=scholarship_key)
    process_logs: list[VoucherProcessLog] = []

    processed_dir = vendor_path / "Processed"
    notprocessed_dir = vendor_path / "NotProcessed"
    processed_dir.mkdir(exist_ok=True)
    notprocessed_dir.mkdir(exist_ok=True)

    print(f"\n🚀 Starting run {runid} with {len(invoices)} scholarships from {vendor_path}")

    for invoice in invoices:
        try:
            # LLM Agent PDF Extraction
            scholarship_data = asyncio.run(run_scholarship_extraction(str(invoice), additional_instructions)).final_output
            if not scholarship_data:
                print(f"❌ Failed extraction: {invoice.name}")
                runlog.failures += 1
                process_logs.append(
                    VoucherProcessLog(
                        runid=runid,
                        filename=invoice.name,
                        voucher_id="Extraction Failed",
                        amount=0.0,
                        invoice="",
                        status="failure",
                    )
                )
                continue

            result = scholarship_playwright_bot(
                scholarship_data,
                scholarship_resource,
                filepath=str(invoice),
                test_mode=test_mode,
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
                amount=scholarship_data.amount,
                invoice=scholarship_data.invoice_number,
                status=status,
            )
            
        except Exception as e:
            print(f"💥 Error processing {invoice.name}: {e}")
            runlog.failures += 1
            VoucherProcessLog(
                runid=runid,
                filename=invoice.name,
                voucher_id="Error",
                amount=0.0,
                invoice="",
                status="failure",
            )


        # Write to DB
        print(process_log)
        db = database.SessionLocal()
        try:
                payload = process_log.model_dump()
                orm_row = models.APBotProcessLog(**payload)
                db.add(orm_row)
                db.commit()
                print("Logged to database.")
        finally:
            db.close()

    t1 = time.time()
    print(f"Average time per invoice: {(t1 - t0) / len(invoices):.2f} seconds.")
    print(f"✅ Completed run {runid}: {runlog.successes} success, {runlog.duplicates} duplicates, {runlog.failures} failures")
    return runlog

def test():
    import random
    scholarship_data = ScholarshipExtractedCheckAuthorization(
        name="KARISSA RODRIGUEZ",
        amount=500.0,
        invoice_number= str(random.randint(1000000, 9999999))
    )
    filepath = "./data/edu_test.pdf"
    fic_result = scholarship_playwright_bot(scholarship_data=scholarship_data,
                                            scholarship_resource='363',
                                            filepath=filepath, 
                                            test_mode=True)
    return fic_result

if __name__ == "__main__":
    # PRD runs
    #runlog = run_vendor_entry("royal", test_mode=False, rent_line="FY26", apo_override="KERNH-APO950043J")
    #runlog = run_vendor_entry("mobile", test_mode=False, rent_line="FY26", additional_instructions=MOBILE_PROMPT)
    #runlog = run_vendor_entry("floyds", test_mode=False, rent_line="FY26", apo_override="KERNH-APO962523J")
    #runlog = run_vendor_entry("cdw", test_mode=False, attach_only=True, additional_instructions=CDW_PROMPT)
    #runlog = run_vendor_entry("class", test_mode=False, rent_line="FY26", additional_instructions=CLASS_PROMPT)
    print(test())
    #runlog = run_scholarship_entry("fic", test_mode=True, additional_instructions=FIC_PROMPT)