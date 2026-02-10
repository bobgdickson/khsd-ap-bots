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
)
from .models import JournalEntryPlan, JournalHeader, JournalLine


settings = get_settings()
USERNAME = settings.peoplesoft_username
PASSWORD = settings.peoplesoft_password


def login_to_journal(page, test_mode: bool = False):
    """Login and navigate to Journal Entry page."""
    if test_mode:
        base_url = settings.peoplesoft_test_env
        dest = base_url + "psp/KDFQ92/EMPLOYEE/ERP/c/JOURNAL_JOURNAL_ENTRY.GBL"
    else:
        base_url = settings.peoplesoft_env
        dest = base_url + "psp/KDFP92/EMPLOYEE/ERP/c/JOURNAL_JOURNAL_ENTRY.GBL"
    ps_login_and_navigate(page, base_url, USERNAME, PASSWORD, dest)


def fill_header(page, header: JournalHeader):
    frame = ps_target_frame(page)
    ps_find_retry(page, "Business Unit").fill(header.business_unit)
    ps_find_retry(page, "Journal Date").fill(header.journal_date.strftime("%m/%d/%Y"))
    ps_find_retry(page, "Description").fill(header.description)
    ps_find_button_retry(page, "Add").click()
    page.wait_for_load_state("networkidle")
    alert_text = handle_peoplesoft_alert(page)
    if alert_text:
        print(f"[JOURNAL] Alert after add: {alert_text}")


def enter_lines(page, lines):
    frame = ps_target_frame(page)
    # TODO: navigate to Lines tab if not already active
    for idx, line in enumerate(lines):
        # TODO: set fund/resource/goal/function/account/site/department/project/class based on BU rules
        try:
            if line.account:
                ps_find_retry(page, "Account").fill(line.account)
            if line.amount is not None:
                ps_find_retry(page, "Amount").fill(str(line.amount))
            if line.line_description:
                ps_find_retry(page, "Line Description").fill(line.line_description)
        except Exception as e:
            print(f"[JOURNAL] Failed to fill line {idx}: {e}")
            continue
        # TODO: click Insert Line if more lines remain


def execute_journal_entry(plan: JournalEntryPlan, test_mode: bool = False):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
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
