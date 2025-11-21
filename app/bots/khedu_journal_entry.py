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
from app.bots.agents.khedu_je_extract import run_scholarship_extraction
from app.bots.prompts import FIC_PROMPT
from app.schemas import KheduJournalExtractedData
from app import models, database
import sqlalchemy

load_dotenv()

USERNAME = os.getenv("PEOPLESOFT_USERNAME")
PASSWORD = os.getenv("PEOPLESOFT_PASSWORD")

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
        return None

    print(f"Extracted data for: {scholarship_data}")

    browser = None
    with sync_playwright() as p:
        print("Starting PeopleSoft journal entry bot...")
        try:
            # --- Login ---
            browser = p.chromium.launch_persistent_context("user_data", headless=False)
            page = browser.new_page()
            page.set_viewport_size({"width": 1920, "height": 1080})
            page.goto(PS_BASE_URL)

            page.wait_for_selector("input#i0116")
            page.fill("input#i0116", USERNAME)
            page.click('input[type=\"submit\"]')

            page.wait_for_selector("input#i0118")
            page.fill("input#i0118", PASSWORD)
            page.click('input[type=\"submit\"]')
            page.wait_for_load_state("networkidle")
            # continue implementation...
        except PlaywrightTimeoutError as e:
            print(f"Playwright timeout: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")
        finally:
            if browser is not None:
                try:
                    browser.close()
                except Exception:
                    pass
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
            ps_find_retry(page, "Invoice Number").fill(scholarship_data.invoice_number)
            ps_find_retry(page, "Invoice Date").fill("T")
            ps_find_retry(page, "Gross Invoice Amount").fill(
                str(scholarship_data.amount)
            )
            ps_target_frame(page).get_by_role("checkbox", name="Tax Exempt Flag").check()
            
            page.pause()