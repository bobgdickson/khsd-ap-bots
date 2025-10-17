from pathlib import Path
import os, time, asyncio, shutil
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from app.bots.utils.ps import (
    ps_target_frame,
    ps_find_retry,
    handle_peoplesoft_alert,
    handle_alerts,
    ps_wait,
    get_voucher_id,
)
from app.bots.utils.misc import generate_runid
from app.bots.agents.payline_extract import run_payline_extraction
from app.bots.prompts import FIC_PROMPT
from app.schemas import PaylineExcelExtractedData, PaylineExcelItem, PaylineExcelError, PaylineEntryResult, PaylineRunLog
from app import models, database
import sqlalchemy

load_dotenv()

USERNAME = os.getenv("PEOPLESOFT_USERNAME")
PASSWORD = os.getenv("PEOPLESOFT_PASSWORD")

def run_raw_sql(emplid, empl_rcd, begin_dt, end_dt, erncd, amt) -> str:
    db_url = os.getenv("PS_DB_URL_HCM")
    # TODO: Stephen SQL for checking status of payline
    query = """
    SELECT COUNT(*)
    FROM PS_PAY_EARNINGS E
    JOIN PS_PAY_OTH_EARNS O
        ON O.PAYGROUP = E.PAYGROUP
        AND O.PAGE_NUM = E.PAGE_NUM
        AND O.LINE_NUM = E.LINE_NUM
        AND O.OFF_CYCLE = E.OFF_CYCLE
        AND O.SEPCHK = E.SEPCHK
        AND O.PAY_END_DT = E.PAY_END_DT
        AND O.ADDL_NBR = E.ADDL_NBR
    WHERE
        E.EMPLID = :emplid
        AND E.EMPL_RCD = :empl_rcd
        AND E.EARNS_BEGIN_DT = :begin_dt
        AND E.EARNS_END_DT = :end_dt
        AND O.ERNCD = :erncd
        AND (O.OTH_EARNS = :amt OR E.REG_EARNS = :amt)
    """
    params = {
        "emplid": emplid,
        "empl_rcd": empl_rcd,
        "begin_dt": begin_dt,
        "end_dt": end_dt,
        "erncd": erncd,
        "amt": amt,
    }
    engine = sqlalchemy.create_engine(db_url)
    with engine.connect() as conn:
        result = conn.execute(sqlalchemy.text(query), params)
        rows = result.fetchall()
        print(rows)
        return str(rows[0][0])

def payline_playwright_bot(
    payline_data: PaylineExcelItem,
    test_mode: bool = False,
) -> PaylineEntryResult:

    if test_mode:
        PS_BASE_URL = (
            os.getenv("PEOPLESOFT_TEST_ENV_HCM", "https://kdhq92.hosted.cherryroad.com/") #TODO: Update for HCM
            + "psp/KDFQ92"
        )
        print(f"Running in TEST mode against {PS_BASE_URL}")
    else:
        PS_BASE_URL = os.getenv("PEOPLESOFT_ENV_HCM") + "psp/KDHP92"
        print(f"Running in PRODUCTION mode against {PS_BASE_URL}")

    if not payline_data:
        print("No payline data provided, exiting.")
        return

    print(f"Extracted data for: {payline_data}")

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
            ps_target_frame(page).locator("[id=\"CHARTFIELD2_TBL_DESCR$0\"]").fill(payline_data.name.upper())
            short_descr = payline_data.invoice_number.split(" ")[0]
            ps_target_frame(page).locator("[id=\"CHARTFIELD2_TBL_DESCRSHORT$0\"]").fill(short_descr)
            ps_target_frame(page).get_by_role("button", name="Save").click()
            #page.pause()
            ps_wait(page, 1)
            page.wait_for_load_state("networkidle")
            #page.pause()
            
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
            ps_wait(page, 1)
            ps_find_retry(page, "Invoice Number").fill(payline_data.invoice_number)
            ps_find_retry(page, "Invoice Date").fill("T")
            ps_find_retry(page, "Gross Invoice Amount").fill(
                str(payline_data.amount)
            )
            ps_target_frame(page).get_by_role("checkbox", name="Tax Exempt Flag").check()

            ps_target_frame(page).get_by_role("button", name="Add", exact=True).click()
            page.wait_for_load_state("networkidle")
            ps_wait(page, 1)
            
            # --- Handle Alert ---
            alert_text = handle_peoplesoft_alert(page)
            if alert_text and "Invalid value" in alert_text:
                #TODO: Update log for payline error
                return PaylineEntryResult(voucher_id="Invalid PO", duplicate=False, out_of_balance=False)
            elif alert_text and "duplicate" in alert_text:
                return PaylineEntryResult(voucher_id="Duplicate", duplicate=True, out_of_balance=False)
      
            # --- Payline Entry
            ps_find_retry(page, "Supplier Name").fill(payline_data.name.upper())
            ps_target_frame(page).locator("#VCHR_VNDR_INFO_ADDRESS1").fill("5801 SUNDALE AVE")
            ps_target_frame(page).locator("#VCHR_VNDR_INFO_CITY").fill("BAKERSFIELD")
            ps_target_frame(page).locator("#VCHR_VNDR_INFO_COUNTY").fill("KERN")
            ps_target_frame(page).locator("#VCHR_VNDR_INFO_STATE").fill("CA")
            ps_target_frame(page).locator("#VCHR_VNDR_INFO_POSTAL").fill("93309")
            ps_target_frame(page).get_by_role("tab", name="Invoice Information").click()
            ps_target_frame(page).locator("[id=\"FUND_CODE$0\"]").fill("01")
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
                #TODO: Update log for payline error
                return PaylineEntryResult(voucher_id="Duplicate", duplicate=True, out_of_balance=False)
            if out_of_balance:
                return PaylineEntryResult(voucher_id="Out of Balance", duplicate=False, out_of_balance=True)
            ps_wait(page, 1)
            voucher_id = get_voucher_id(page)
            print("Voucher ID:", voucher_id)
            #page.pause()
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
            #page.pause()
            ps_target_frame(page).get_by_label("Action").select_option(value="Journal Generate")
            ps_target_frame(page).get_by_role("button", name="Run").click()
            
            ok_button = page.get_by_role("button", name="Yes")
            ok_button.click()
            ps_wait(page, 5)

            #page.pause()

            # Payments 
            ps_target_frame(page).get_by_role("tab", name="Payments").click()
            page.wait_for_load_state("networkidle")
            ps_target_frame(page).get_by_role("link", name="Express Payment").click()
            ps_wait(page, 2)
            ps_target_frame(page).get_by_role("button", name="Create Payment").click()
            ps_wait(page, 10)
            ps_target_frame(page).get_by_role("button", name="Refresh").click()
            try:
                ps_target_frame(page).get_by_role("button", name="Process").click()
            except PlaywrightTimeoutError:
                ps_wait(page, 5)
                ps_target_frame(page).get_by_role("button", name="Refresh").click()
                ps_wait(page, 1)
                ps_target_frame(page).get_by_role("button", name="Process").click()
            
            #page.pause()

            # --- Return entry result
            #TODO: Update log for payline error
            return PaylineEntryResult(voucher_id=voucher_id, duplicate=False, out_of_balance=False)
        finally:
            if "browser" in locals():
                print("Closing browser...")
                browser.close()


def run_payline_entry(test_mode: bool = True, additional_instructions: str = None):
    """
    Process all paylines for one excel file in a directory.
    Returns (VoucherRunLog, list[VoucherProcessLog]).
    """
    t0 = time.time()
    if test_mode:
        base_dir = './data'
    else:
        #TODO: Replace with shared folder path for PRD runs
        base_dir = r"C:\somewhere"
    # Get file Certificated_Adjustments.xlsx from base_dir
    excel_path = Path(base_dir) / "Certificated_Adjustments.xlsx"
    if not excel_path.exists():
        raise RuntimeError(f"Adjustment file {excel_path} not found")

    runid = generate_runid(
        identifier="payline",
        test_mode=test_mode,
        bot_name="payline_entry",
    )
    runlog = PaylineRunLog(runid=runid)

    print(f"\n🚀 Starting run {runid} for payline adjustments")

    # Extract payline worklist from excel file
    paylines: list[PaylineExcelItem] = []
    errors: list[PaylineExcelError] = []
    try:
        extraction_result = asyncio.run(
            run_payline_extraction(excel_path, additional_instructions)
        )
        if not extraction_result or not extraction_result.final_output:
            print(f"Failed extraction: {excel_path}")
        else:
            payline_output = extraction_result.final_output
            paylines = list(payline_output.items or [])
            errors = list(payline_output.errors or [])
    except Exception as e:
        print(f"Extraction error: {e}")

    # payline entry results to DB
    db = database.SessionLocal()
    for payline in paylines:
        try:
            payload = payline.model_dump()
            orm_row = models.PaylineExcelItem(**payload)
            # check if exists by unique fields (tab_name, emplid, empl_rcd, ern_ded_code, amount)
            existing = db.query(models.PaylineExcelItem).filter_by(
                tab_name=payline.tab_name,
                emplid=payline.emplid,
                empl_rcd=payline.empl_rcd,
                ern_ded_code=payline.ern_ded_code,
                amount=payline.amount
            ).first()
            if existing:
                continue  # Skip duplicates
            else:
                db.add(orm_row)
                db.commit()
        except Exception as e:
            print(f"DB error for {payline}: {e}")

    # Get all paylines with status of new
    paylines_to_process = db.query(models.PaylineExcelItem).filter_by(status="new").all()

    # Run SQL to check if they have been entered in PS already and update status to processed if so
    for payline in paylines_to_process:
        try:
            count = int(run_raw_sql(
                payline.emplid,
                payline.empl_rcd,
                payline.earnings_begin_dt,
                payline.earnings_end_dt,
                payline.ern_ded_code,
                payline.amount
            ))
            if count > 0:
                payline.status = "processed"
                db.commit()
        except Exception as e:
            print(f"SQL check error for {payline}: {e}")

    paylines_to_process = db.query(models.PaylineExcelItem).filter_by(status="new").all()
    print(f"Found {len(paylines_to_process)} paylines to process.")

    for payline in paylines_to_process:
        try:
            #result = payline_playwright_bot(
            #    payline_data,
            #    test_mode=test_mode,
            #)
            #TODO: Remove when actual call is uncommented
            result = PaylineEntryResult(success=True, pay_group="RSA", pay_end_dt="2025-08-31", off_cycle="N", page_num=1, line_num=1, addl_nbr=1, emplid=payline.emplid, amount=payline.amount)
            print(f"Processed {payline.emplid}: {result}")

            if result.success:
                runlog.processed += 1
                payline.status = "tested" if test_mode else "processed"
            else:
                payline.status = "error"    
            
        except Exception as e:
            print(f" Error processing {payline.emplid}: {e}")
            runlog.failures += 1
            payline.status = "error"
            payline.notes = str(e)
        db.commit()

        db.close()

    t1 = time.time()
    print(f"Average time per payline: {(t1 - t0) / len(paylines_to_process):.2f} seconds.")
    print(f"Completed run {runid}: {runlog.processed} success, {runlog.failures} failures")
    return runlog

def test():
    import random
    payline_data = PaylineExcelItem(
        tab_name="Test",
        hr_requestor="Test User",
        month_requested="August",
        site="Kern High",
        emplid=str(random.randint(100000, 999999)),
        empl_rcd=0,
        ern_ded_code="RSA",
        amount=813.18,
        earnings_begin_dt="2025-08-01",
        earnings_end_dt="2025-08-31",
        notes="Test entry"
    )
    payline_result = payline_playwright_bot(payline_data=payline_data, test_mode=True)
    return payline_result

if __name__ == "__main__":
    #run_raw_sql('127518', 0, '2025-08-01', '2025-08-31', 'RSA', 813.18)
    run_payline_entry(test_mode=True)
