from pathlib import Path
from typing import Optional
import os, time, asyncio, shutil, sys, datetime
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
    find_rent_line,
    get_voucher_id,
    handle_modal_sequence,
    ps_find_button_retry
)
from app.bots.utils.misc import (
    generate_runid,
    get_invoices_in_data,
    is_run_cancel_requested,
    normalize_date,
    update_bot_run_status,
)
from app.bots.agents.multimodal import extract_to_schema
from app.bots.prompts import CDW_PROMPT, CLASS_PROMPT, MOBILE_PROMPT
from app.schemas import DirectDepositExtractResult, DepositEntryResult, VoucherRunLog, DirectDepositProcessLog
if sys.platform.startswith("win"):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except AttributeError:
        pass
from app import models, database


load_dotenv()

USERNAME = os.getenv("PEOPLESOFT_USERNAME")
PASSWORD = os.getenv("PEOPLESOFT_PASSWORD")

def log_direct_deposit_process(runid, emplid, name, bank_name, routing_number, bank_account, amount_dollars, status, message=None):
    log_entry = DirectDepositProcessLog(
        runid=runid,
        emplid=emplid,
        name=name,
        bank_name=bank_name,
        routing_number=routing_number,
        bank_account=bank_account,
        amount_dollars=amount_dollars,
        status=status,
        message=message,
    )
    print(f"Direct Deposit Log: {log_entry}")

def deposit_playwright_bot(
    deposit_data: DirectDepositExtractResult,
    test_mode: bool = False,
) -> DepositEntryResult:

    apo_flag = False

    if test_mode:
        PS_BASE = os.getenv("PEOPLESOFT_TEST_ENV_HCM")
        PS_BASE_URL = (
            os.getenv("PEOPLESOFT_TEST_ENV_HCM", "https://kdfq92.hosted.cherryroad.com/")
            + "psp/KDHR92"
        )
        print(f"Running in TEST mode against {PS_BASE_URL}")
    else:
        PS_BASE = os.getenv("PEOPLESOFT_ENV_HCM")
        PS_BASE_URL = os.getenv("PEOPLESOFT_ENV_HCM") + "psp/KDHP92"
        print(f"Running in PRODUCTION mode against {PS_BASE_URL}")

    if not deposit_data:
        print("No deposit data provided, exiting.")
        return

    print(f"Extracted data for: {deposit_data}")

    with sync_playwright() as p:
        print("Starting PeopleSoft direct deposit entry bot...")
        try:
            # --- Login ---
            browser = p.chromium.launch(headless=False)
            page = browser.new_page()
            page.set_viewport_size({"width": 1920, "height": 1080})
            page.goto(PS_BASE, timeout=60000)

            page.wait_for_selector("input#i0116")
            page.fill("input#i0116", USERNAME)
            page.click('input[type="submit"]')

            page.wait_for_selector("input#i0118")
            page.fill("input#i0118", PASSWORD)
            page.click('input[type="submit"]')
            page.wait_for_load_state("networkidle")

            page.goto(
                PS_BASE_URL
                + "/EMPLOYEE/HRMS/c/MAINTAIN_PAYROLL_DATA_US.DIRECT_DEPOSIT.USA"
            )
            page.wait_for_load_state("networkidle")
            ps_find_retry(page, "Empl ID").fill(deposit_data.emplid)
            page.locator("iframe[name=\"TargetContent\"]").content_frame.get_by_role("button", name="Search", exact=True).click()
            ps_wait(page, 1)
            #if the status field is not blank, then click the "Add a new row at row" button
            if ps_target_frame(page).get_by_label("Status").input_value() != "":
                page.frame(name="TargetContent")
                add = page.locator("iframe[name=\"TargetContent\"]").content_frame.get_by_role("button", name="Add a new row at row").first
                add.click()
                ps_wait(page, 1)
            ps_find_retry(page,"Effective Date").fill(str(deposit_data.date.strftime("%m/%d/%Y")))
            page.keyboard.press("Tab")
            ps_wait(page, 1)
            ps_target_frame(page).get_by_label("Status").select_option(value="Active")
            ps_find_retry(page, "Bank ID").fill(deposit_data.routing_number)
            page.keyboard.press("Tab")
            ps_wait(page, 1)
            if deposit_data.checking_account:
                ps_target_frame(page).get_by_label("Account Type").select_option(
                value="Checking")
            else:
                ps_target_frame(page).get_by_label("Account Type").select_option(
                value="Savings")
            page.keyboard.press("Tab")
            ps_wait(page, 1)
            if deposit_data.amount_dollars > 0:
                ps_target_frame(page).get_by_label("Deposit Type").select_option(value="Amount")
                ps_find_retry(page, "Net Pay Amount").fill(str(deposit_data.amount_dollars))
                ps_find_retry(page, "Priority").fill("1")
            elif deposit_data.amount_percentage < 100:
                ps_target_frame(page).get_by_label("Deposit Type").select_option(value="Percent")
                ps_find_retry(page, "Net Pay Percent").fill(str(deposit_data.amount_percentage))
                ps_find_retry(page, "Priority").fill("2")
            else:
                ps_target_frame(page).get_by_label("Deposit Type").select_option(value="Balance of Net Pay")
                ps_find_retry(page, "Priority").fill("999")
            ps_find_retry(page, "Account Number").fill(deposit_data.bank_account)
            ps_target_frame(page).get_by_role("button", name="Save", exact=True).click()
            ps_wait(page, 3)

            print(str(deposit_data.emplid), " Success")
            return DepositEntryResult(success=True, message=f"Empl ID: {deposit_data.emplid}")

        finally:
            if "browser" in locals():
                print("Closing browser...")
                browser.close()


def run_direct_deposit_entry(
    test_mode: bool = True,
    additional_instructions: str = None,
    runid: Optional[str] = None,
):
    """
    Process all direct deposits in a directory.
    Returns (VoucherRunLog, list[DirectDepositProcessLog]).
    """
    t0 = time.time()
    file_path = r"C:\Users\Stephen_Nicholas\OneDrive - Kern High School District\PeopleSoft\Direct Deposits"
    vendor_key = "direct_deposit"
    file_path = Path(file_path)

    deposits = list(file_path.glob("*.png")) + list(file_path.glob("*.pdf"))
    if not deposits:
        print(f"No direct deposits found in {file_path}")
        return None, []

    runid = runid or generate_runid(
        vendor_key,
        test_mode=test_mode,
        bot_name="direct_deposit_entry",
        context={"vendor_key": vendor_key},
    )
    runlog = VoucherRunLog(runid=runid, vendor=vendor_key)
    process_logs: list[DirectDepositProcessLog] = []

    if is_run_cancel_requested(runid):
        update_bot_run_status(runid, "cancelled", message="Cancelled before start")
        print(f"Run {runid} was cancelled before it started.")
        return runlog

    processed_dir = file_path / "Attached"
    processed_dir.mkdir(exist_ok=True)

    update_bot_run_status(
        runid,
        "running",
        context_updates={"total_deposits": len(deposits)},
    )

    print(f"\n🚀 Starting run {runid} with {len(deposits)} invoices from {file_path}")

    cancelled = False
    try:
        for deposit in deposits:
            if is_run_cancel_requested(runid):
                print(f"Cancellation requested for run {runid}. Stopping further processing.")
                cancelled = True
                break

            process_log: Optional[DirectDepositProcessLog] = None
            system_prompt="""
            You are a direct deposit extraction agent. 
            Use the tool to extract raw data from the document.
            Extract the following fields from the provided direct_deposit document: 
            emplid, name, date, ssn, bank_name, routing_number, bank_account, checking_account, savings_account, amount_dollars, amount_percentage.
            The ssn field should only contain the last four digits of the social security number.
            The checking_account and savings_account fields should be booleans indicating whether the bank account is a checking or savings account.
            The amount_dollars field is the fixed dollar amount for direct deposit, and amount_percentage is the percentage amount for direct deposit. If one of these is not provided, set it to 0.
            The date field should be converted to MM-DD-YYYY format.
            If you can't find the date, use today's date
            emplid will always be a 6 digit number.
            if checking and savings account are both true, set savings_account to false.
            if checking and saving account are both false, set checking_account to true.
            if amount_dollars and amount_percentage are both blank or 0, then set percentage to 100.
            Return only valid JSON that matches the expected format.
            """
            extraction_result = extract_to_schema(str(deposit), DirectDepositExtractResult, prompt=system_prompt)
            #todo skip if percentage is not 100
            if not extraction_result:
                print(f"Failed extraction: {deposit.name}")
                runlog.failures += 1
                process_log = DirectDepositProcessLog(
                    runid=runid,
                    emplid="",
                    name="",
                    bank_name="",
                    routing_number="",
                    bank_account="",
                    amount_dollars=0.0,
                    status="failure",
                    message="Extraction Failed",
                )
            else:
                deposit_data = extraction_result
                deposit_data.date = normalize_date(deposit_data.date)
                if not deposit_data.date:
                    deposit_data.date = datetime.datetime.now()
                #change date to first of month for direct deposit
                #deposit_data.date = deposit_data.date.replace(day=1)
                result = deposit_playwright_bot(
                    deposit_data,
                    test_mode=test_mode,
                )

                log_direct_deposit_process(
                    runid=generate_runid(),
                    emplid=deposit_data.emplid,
                    name=deposit_data.name,
                    bank_name=deposit_data.bank_name,
                    routing_number=deposit_data.routing_number,
                    bank_account=deposit_data.bank_account,
                    amount_dollars=deposit_data.amount_dollars,
                    status="Success",
                )

            runlog.processed += 1

            if result.success:
                runlog.successes += 1
                status = "success"
                print(f"Moving entered deposits {deposit.name} to Processed.")
                shutil.move(str(deposit), processed_dir / deposit.name)
            else:
                runlog.failures += 1
                status = "failure"
                print(f"Not moving failed deposit {deposit.name}.")

            process_log = DirectDepositProcessLog(
                runid=runid,
                emplid=deposit_data.emplid,
                name=deposit_data.name,
                bank_name=deposit_data.bank_name,
                routing_number=deposit_data.routing_number,
                bank_account=deposit_data.bank_account,
                amount_dollars=deposit_data.amount_dollars,
                status=status,
            )

    except Exception as e:
        log_direct_deposit_process(
            runid=generate_runid(
                vendor_key,
                test_mode=test_mode,
                bot_name="direct_deposit_entry",
                context={"vendor_key": vendor_key},
            ),
            emplid=deposit_data.emplid,
            name=deposit_data.name,
            bank_name=deposit_data.bank_name,
            routing_number=deposit_data.routing_number,
            bank_account=deposit_data.bank_account,
            amount_dollars=deposit_data.amount_dollars,
            status="Failure",
            message=str(e),
        )
        runlog.failures += 1
        process_log = DirectDepositProcessLog(
            runid=runid,
            emplid=deposit_data.emplid,
            name=deposit_data.name,
            bank_name=deposit_data.bank_name,
            routing_number=deposit_data.routing_number,
            bank_account=deposit_data.bank_account,
            amount_dollars=deposit_data.amount_dollars,
            status="failure",
            message=str(e),
        )

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

    # ...existing code...

    t1 = time.time()
    print(f"Average time per invoice: {(t1 - t0) / len(deposits):.2f} seconds.")

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
        print(f"Run {runid} cancelled after processing {runlog.processed} deposits.")
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

def test_with_fake_extraction():
    fake_data = DirectDepositExtractResult(
        emplid="151622",
        name="Test Tester",
        date="2025-12-10",
        ssn="6789",
        bank_name="Bank of Examples",
        routing_number="111000025",
        bank_account="123456789",
        checking_account=True,
        savings_account=False,
        amount_dollars=0.00,
        amount_percentage=100,
    )
    result = deposit_playwright_bot(fake_data, test_mode=True)
    print(f"Test deposit entry result: {result}")

def test_multi_modal_extraction():
    test_file = "dd_ex.png"
    system_prompt="""
            You are a direct deposit extraction agent. 
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
    extraction_result = extract_to_schema(str(test_file), DirectDepositExtractResult, prompt=system_prompt)
    print(f"Extraction result: {extraction_result}")    

if __name__ == "__main__":
    # PRD runs
    #runlog = run_vendor_entry("royal", test_mode=False, rent_line="FY26", apo_override="KERNH-APO950043J")
    #runlog = run_vendor_entry("mobile", test_mode=False, rent_line="FY26", additional_instructions=MOBILE_PROMPT)
    #runlog = run_vendor_entry("floyds", test_mode=False, rent_line="FY26", apo_override="KERNH-APO962523J")
    runlog = run_direct_deposit_entry(test_mode=True)
    #runlog = run_vendor_entry("class", test_mode=False, rent_line="FY26", additional_instructions=CLASS_PROMPT)
    # Test run with fake extraction data
    #test_with_fake_extraction()
    #test_multi_modal_extraction()
