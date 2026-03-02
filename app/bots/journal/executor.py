from email import header
from pathlib import Path
from typing import Optional
from datetime import date

from playwright.sync_api import sync_playwright

from app.config import get_settings
from app.bots.utils.ps import (
    ps_login_and_navigate,
    ps_find_retry,
    ps_find_button_retry,
    ps_target_frame,
    ps_wait,
    handle_peoplesoft_alert,
    handle_alerts,
    get_journal_id
)
from .models import JournalEntryPlan, JournalHeader, JournalLine

#page.pause()
settings = get_settings()
USERNAME = settings.peoplesoft_username
PASSWORD = settings.peoplesoft_password



def login_to_journal(page, test_mode: bool = False):
    """Login and navigate to Journal Entry page."""
    if test_mode:
        base_url = settings.peoplesoft_test_env
        dest = base_url + "psp/KDFQ92/EMPLOYEE/ERP/c/PROCESS_JOURNALS.JOURNAL_ENTRY_IE.GBL"
    else:
        base_url = settings.peoplesoft_env
        dest = base_url + "psp/KDFP92/EMPLOYEE/ERP/c/PROCESS_JOURNALS.JOURNAL_ENTRY_IE.GBL"
    ps_login_and_navigate(page, base_url, USERNAME, PASSWORD, dest)
    #page.pause() 

def fill_header(page, header: JournalHeader):
    frame = ps_target_frame(page)
    ps_find_retry(page, "Business Unit").fill(header.business_unit)
    ps_find_retry(page, "Journal Date").fill(header.journal_date.strftime("%m/%d/%Y"))
    #page.pause()  # for testing - remove later
    
    ps_find_button_retry(page, "Add").click()
    page.wait_for_load_state("networkidle")
    alert_text = handle_peoplesoft_alert(page)
    if alert_text:
        print(f"[JOURNAL] Alert after add: {alert_text}")
    ps_find_retry(page, "Long Description").fill(header.description)

def enter_lines(page, lines):
    frame = ps_target_frame(page)
    frame.get_by_role("tab", name="Lines").click()
    page.wait_for_load_state("networkidle")

    def _fill(idx: int, label: str, base_name: str, value: str):
        """Attempt to fill a field on the given line index.

        First try the explicit PeopleSoft naming convention (e.g. ``ACCOUNT$0``).
        If that fails we fall back to the role-based lookup with ``.nth(idx)`` so
        the original behaviour still works when the index is not part of the
        accessible name.
        """
        selector = f'input[name="{base_name}${idx}"], input[id="{base_name}${idx}"]'
        try:
            frame.locator(selector).fill(value)
            page.wait_for_timeout(500)  # small delay to ensure value is registered before next action
            return
        except Exception:
            # drop through to fallback
            pass

        # fallback using the shared label locator and nth() to pick the row
        locator = ps_find_retry(page, label).nth(idx)
        locator.fill(value)
        page.wait_for_timeout(500)  # small delay to ensure value is registered before next action

    # TODO: set fund/resource/goal/function/account/site/department/project/class based on BU rules
    for idx, line in enumerate(lines):
        print(f"[JOURNAL] Filling line {idx}: {line}")
        #page.pause()
        try:
            if line.fund:
                print(f"[JOURNAL]  - fund: {line.fund}")
                _fill(idx, "FUND_CODE", "FUND_CODE", line.fund)
                frame.locator(f'input[name="FUND_CODE${idx}"]').press("Tab")
                page.wait_for_timeout(2000)  # small delay to ensure value is registered before next action
            if line.resource:
                print(f"[JOURNAL]  - resource: {line.resource}")
                _fill(idx, "PROGRAM_CODE", "PROGRAM_CODE", line.resource)
            if line.goal:
                print(f"[JOURNAL]  - goal: {line.goal}")
                _fill(idx, "CHARTFIELD2", "CHARTFIELD2", line.goal)
            if line.function:
                print(f"[JOURNAL]  - function: {line.function}")
                _fill(idx, "CHARTFIELD3", "CHARTFIELD3", line.function)
            if line.account:
                print(f"[JOURNAL]  - account: {line.account}")
                _fill(idx, "ACCOUNT", "ACCOUNT", line.account)
            if line.amount is not None:
                print(f"[JOURNAL]  - amount: {line.amount}")
                _fill(idx, "FOREIGN_AMOUNT", "FOREIGN_AMOUNT", str(line.amount))
            if line.line_description:
                print(f"[JOURNAL]  - description: {line.line_description}")
                # the exact field name may be LINE_DESCRIPTION or LINE_DESCR depending on the form
                _fill(idx, "Line Description", "LINE_DESCR", line.line_description)
        except Exception as e:
            print(f"[JOURNAL] Failed to fill line {idx}: {e}")
            continue
        
        # Only click Insert Lines if this is not the last line
        if idx < len(lines) - 1:
            ps_target_frame(page).get_by_role("link", name="Insert Lines").click()
            print(f"[JOURNAL]  clicked Insert Lines for line {idx}")
        #page.pause()

    ps_find_button_retry(page, "Save").click()
    page.wait_for_load_state("networkidle")
    #page.pause()
    # Handle any save alerts (e.g., validation warnings, confirmation dialogs)
    alert_text, duplicate, out_of_balance = handle_alerts(page)
    if alert_text:
        print(f"[JOURNAL] Alert after save: {alert_text}")
    journal_id = get_journal_id(page)
    if journal_id == "NEXT":
        print(f"[JOURNAL] Journal ID is NEXT, indicating an error.")
        #TO DO: send back failed status to orchestrator with journal_id and alert_text for analyst review
    #page.pause()

    # Processing, Approving and Posting the Voucher
    ps_target_frame(page).get_by_role("button", name="Process").click()
    frame = ps_target_frame(page)
    #page.pause()
    #Pop up to process and click YES
    alert_text, duplicate, out_of_balance = handle_alerts(page)
    if alert_text:
        print(f"[JOURNAL] Alert after save: {alert_text}")
    ps_wait(page, 7)
    frame.get_by_role("tab", name="Approval").click()
    ps_wait(page, 1)
    ps_target_frame(page).get_by_role("button", name="Submit").click()
    ps_wait(page, 1)
    page.pause()
    alert_text, duplicate, out_of_balance = handle_alerts(page)
    if "cannot submit this journal for approval" in alert_text:
        print(f"[JOURNAL] Alert after save: {alert_text}")
        
        print(f"[JOURNAL] Journal ID: {journal_id}")
        #TO DO: send back failed status to orchestrator with journal_id and alert_text for analyst review
    frame.get_by_role("tab", name="Lines").click()
    page.pause()

#Alert Text -  Cannot submit this journal for approval because it is not validated yet. 

def execute_journal_entry(plan: JournalEntryPlan, test_mode: bool = False):
    """Run the journal entry flow in a Playwright browser.

    Uses a persistent context named ``user_data`` so that credentials/cookies
    are stored between runs, similar to the voucher entry bot. This makes
    iterative development easier and avoids repeated login prompts.
    """
    with sync_playwright() as p:
        print("[JOURNAL] Starting PeopleSoft journal entry bot...")
        # launch a persistent context just like ``khedu_voucher_entry`` uses
        browser = p.chromium.launch_persistent_context("user_data", headless=False)
        page = browser.new_page()
        login_to_journal(page, test_mode=test_mode)
        fill_header(page, plan.header)
        enter_lines(page, plan.lines)
        # TODO: save, process, handle popups, submit/approve per analyst steps
        print("[JOURNAL] Entry scaffolding complete; analyst to fill Playwright details.")
        browser.close()


if __name__ == "__main__":
    sample_plan = JournalEntryPlan(
        header=JournalHeader(
            business_unit="KHEDU",
            journal_date=date.today(),
            description="Sample journal entry",
        ),
        lines=[
            JournalLine(fund="01", resource="100", goal="000", function="000", account="100", amount=100.00, line_description="Test debit line"),
            JournalLine(fund="01", resource="100", goal="000", function="000", account="100", amount=-100.00, line_description="Test credit line"),
        ],
    )
    execute_journal_entry(sample_plan, test_mode=True)
