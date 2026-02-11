from pathlib import Path
import re
from playwright.sync_api import sync_playwright

from app.bots.utils.ps import (
    handle_alerts,
    handle_modal_sequence,
    get_voucher_id,
    handle_peoplesoft_alert,
    ps_find_button,
    ps_find_button_retry,
    ps_find_retry,
    ps_target_frame,
    ps_wait,
    ps_login_and_navigate,
    find_rent_line,
    ps_find,
    ps_find_div,
)
from .models import VoucherEntryPlan
from app.config import get_settings

settings = get_settings()
USERNAME = settings.peoplesoft_username
PASSWORD = settings.peoplesoft_password
PS_BASE = settings.peoplesoft_env
PS_BASE_URL = PS_BASE + "psp/KDFP92"

def date_to_ps_format(date_str: str) -> str:
    """Convert any date to 'MM/DD/YYYY' format for PeopleSoft."""
    from datetime import datetime

    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%Y/%m/%d"):
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%m/%d/%Y")
        except ValueError:
            continue
    raise ValueError(f"Unrecognized date format: {date_str}")

def login(p, test_mode: bool = False):
    """Login to PeopleSoft and navigate to voucher entry page."""
    if test_mode:
        base_url = settings.peoplesoft_test_env
        PS_BASE_URL = base_url + "psp/KDFQ92"
    else:
        base_url = settings.peoplesoft_env
        PS_BASE_URL = base_url + "psp/KDFP92"
    
    # --- Login ---
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    destination = (
        PS_BASE_URL
        + "/EMPLOYEE/ERP/c/ENTER_VOUCHER_INFORMATION.VCHR_EXPRESS.GBL"
    )
    ps_login_and_navigate(page, base_url, USERNAME, PASSWORD, destination)
    return page


def enter_header_fields(page, invoice):
    """Fill basic invoice header fields."""
    ps_find_retry(page, "Invoice Number").fill(invoice.invoice_number)
    ps_find_retry(page, "Invoice Date").fill(date_to_ps_format(invoice.invoice_date))
    ps_find_retry(page, "Gross Invoice Amount").fill(str(invoice.total_amount))


def enter_po_header(page, po_id: str):
    """Populate PO unit/number before copy-from-PO."""
    po_unit = "KERNH"
    po_number = po_id
    if "-" in po_id:
        maybe_unit, maybe_number = po_id.split("-", 1)
        if maybe_unit and maybe_number:
            po_unit, po_number = maybe_unit, maybe_number

    ps_find_retry(page, "PO Business Unit").fill(po_unit)
    ps_find_retry(page, "PO Number").fill(po_number)

def create_voucher(page):
    ps_target_frame(page).get_by_role("button", name="Add", exact=True).click()
    page.wait_for_load_state("networkidle")
    # --- Handle Alert ---
    alert_text = handle_peoplesoft_alert(page)
    if alert_text and "Invalid value" in alert_text:
        #TODO: Handle invalid value alert
        print("[ERROR] Invalid value alert encountered during voucher creation.")
        ps_wait(page, 1)

def copy_po_lines(page, plan: VoucherEntryPlan):
    """Copy PO lines into the voucher prior to overriding amounts."""
    print("[EXECUTOR] Copy PO flow starting")
    ps_find_button_retry(page, "Copy From Source Document").click()
    ps_wait(page, 1)
    ps_find_retry(page, "PO Unit").fill("KERNH")
    ps_find_retry(page, "PO Number").fill(plan.po.po_id)
    print(f"[EXECUTOR] Copying PO {plan.po.po_id}")
    ps_find_button(page, "Copy PO").click()
    page.wait_for_load_state("networkidle")

    frame = ps_target_frame(page)
    
    try:
        frame.get_by_role("button", name="Search", exact=True).click()
        page.wait_for_load_state("networkidle")
    except Exception:
        pass
    alert_text = handle_peoplesoft_alert(page)
    if alert_text and "Invalid value" in alert_text:
        print("[EXECUTOR] Invalid PO alert after search")
        return {"error": "Invalid PO"}
    selected = set()
    if len(plan.mapping.lines) == 1:
        # fast search when only one line
        entry = plan.mapping.lines[0]
        try:
            ps_find_retry(page, "PO Line Number From").fill(str(entry.po_line))
            try:
                frame.get_by_role("button", name="Search", exact=True).click()
                page.wait_for_load_state("networkidle")
            except Exception:
                pass
            alert_text = handle_peoplesoft_alert(page)
            if alert_text and "Invalid value" in alert_text:
                print(f"[EXECUTOR] Invalid PO line {entry.po_line} during search")
            else:
                line_text = frame.locator('[id="win0divVCHR_MTCH_WS4_LINE_NBR$0"]').inner_text().strip()
                print(f"[EXECUTOR] Search for PO line {entry.po_line} returned '{line_text}'")
                amt_locator = frame.locator('[id="VCHR_MTCH_WS4_MERCHANDISE_AMT$0"]').first
                amt_locator.fill(str(entry.amount))
                frame.locator('[id="VCHR_PANELS_WRK_LINE_SELECT_PO$0"]').check()
                selected.add(entry.po_line)
                print(f"[EXECUTOR] Selected PO line {entry.po_line} amount {entry.amount}")
        except Exception as e:
            print(f"[WARN] Failed selecting PO line {entry.po_line}: {e}")
    else:
        # multiple lines: iterate sequentially
        mapping_by_line = {entry.po_line: entry.amount for entry in plan.mapping.lines}
        row_idx = 0
        while len(selected) < len(mapping_by_line):
            try:
                line_locator = frame.locator(f'[id="win0divVCHR_MTCH_WS4_LINE_NBR${row_idx}"]')
                line_text = line_locator.inner_text().strip()
            except Exception:
                try:
                    frame.get_by_role("button", name="Show next row").click()
                    ps_wait(page, 1)
                    row_idx += 1
                    print(f"[EXECUTOR] Advancing to next row {row_idx}")
                    continue
                except Exception:
                    print("[EXECUTOR] No further rows available")
                    break
            print(f"[EXECUTOR] Inspecting row {row_idx}: text='{line_text}'")
            m = re.search(r"(\\d+)", line_text)
            po_line_num = int(m.group(1)) if m else None
            if po_line_num in mapping_by_line:
                try:
                    amt_locator = frame.locator(f'[id="VCHR_MTCH_WS4_MERCHANDISE_AMT${row_idx}"]').first
                    amt_locator.fill(str(mapping_by_line[po_line_num]))
                    frame.locator(f'[id="VCHR_PANELS_WRK_LINE_SELECT_PO${row_idx}"]').check()
                    selected.add(po_line_num)
                    print(f"[EXECUTOR] Selected PO line {po_line_num} at row {row_idx} amount {mapping_by_line[po_line_num]}")
                except Exception:
                    print(f"[WARN] Could not select/fill PO line {po_line_num} at row {row_idx}")
            row_idx += 1

    #page.pause()
    ps_wait(page, 1)
    try:
        frame.get_by_role("button", name="Copy Selected Lines").click()
        page.wait_for_load_state("networkidle")
        print("[EXECUTOR] Copy Selected Lines clicked")
    except Exception:
        print("[WARN] Failed to click Copy Selected Lines")
        pass

    # handle possible alerts (use tax, etc.)
    try:
        alert_text, dup, oob = handle_alerts(page)
        if alert_text:
            print(f"[EXECUTOR] Alert after copy: {alert_text}")
    except Exception:
        print("[WARN] Exception handling alerts after copy")

    # delete auto-created blank line after copy
    try:
        frame = ps_target_frame(page)
        frame.get_by_role("button", name="Delete row").first.click()
        ps_wait(page, 1)
        page.get_by_role("button", name="OK").click()
        ps_wait(page, 1)
        print("[EXECUTOR] Deleted auto-created line")
    except Exception:
        print("[WARN] Unable to delete auto-created line")


def enter_po_line_amounts(page, plan: VoucherEntryPlan):
    """Fill line amounts according to the mapping output."""
    frame = ps_target_frame(page)
    for idx, entry in enumerate(plan.mapping.lines):
        try:
            amt_locator = frame.locator(f'#VCHR_MTCH_WS4_MERCHANDISE_AMT${idx}')
            amt_locator.fill(str(entry.amount))
        except Exception:
            print(f"[WARN] Could not set amount for PO line {entry.po_line}")


def attach_file(page, filepath: str | Path):
    ps_target_frame(page).get_by_role("link", name="Attachments").click()
    page.wait_for_load_state("networkidle") 
    handle_modal_sequence(
        page, ["Add Attachment", "Browse", "Upload", "OK"], file=str(Path(filepath).resolve())
    )


def save_voucher(page):
    ps_target_frame(page).locator("#VCHR_PANELS_WRK_VCHR_SAVE_PB").click()
    ps_wait(page, 1)
    alert_text, duplicate, out_of_balance = handle_alerts(page)
    #page.pause()
    voucher_id = get_voucher_id(page)
    return {
        "voucher_id": voucher_id,
        "duplicate": duplicate,
        "out_of_balance": out_of_balance,
        "alert": alert_text,
    }


def execute_voucher_entry(plan: VoucherEntryPlan, test_mode: bool = True, page=None):
    """
    Execute voucher entry. If a page is provided, reuse it; otherwise create a new Playwright session.
    """
    owns_browser = False
    if page is None:
        owns_browser = True
        p = sync_playwright().start()
        page = login(p, test_mode)
    try:
        enter_header_fields(page, plan.invoice)
        create_voucher(page)
        copy_result = copy_po_lines(page, plan)
        if isinstance(copy_result, dict) and copy_result.get("error"):
            return {
                "voucher_id": copy_result.get("error"),
                "duplicate": False,
                "out_of_balance": False,
                "alert": copy_result.get("error"),
            }
        #enter_po_line_amounts(page, plan) # Currently amounts are set during copy_po_lines to minimize time spent in the UI with incorrect amounts
        attach_file(page, plan.attachment_path)
        return save_voucher(page)
    finally:
        if owns_browser:
            try:
                page.context.browser.close()
            except Exception:
                pass


if __name__ == "__main__":
    from .models import VoucherEntryPlan, LineMappingEntry, LineMapping, ExtractedInvoice, InvoiceLine, ValidatedPO
    test_plan = VoucherEntryPlan(
        po=ValidatedPO(
            po_id='CPO54496-A',
            vendor_id='33452',
            vendor_name='VESTIS',
            confidence=0.95
        ),
        invoice=ExtractedInvoice(
            invoice_number='2601783326-test',
            vendor_name='VESTIS',
            invoice_date='2025-11-18',
            total_amount=100,
            purchase_order_raw='KERNH-CPO54496-A',
            fuzzy_po_candidates=['KERNH-CPO54496-A', '1567882102', '661441'],
            lines=[
                InvoiceLine(description='LOCKING PLIER SETS,PLAIN GRIP,4 PCS MANUFACTURER # 428GS', quantity=1.0, unit_price=75.1, line_amount=75.1),
                InvoiceLine(description='HEXKEYS, L 2 27/32 IN TO 6 3/4 IN MANUFACTURER # 13213', quantity=3.0, unit_price=22.94, line_amount=68.82)
            ]
        ),
        mapping=LineMapping(
            strategy="Test Strategy",
            lines=[
                LineMappingEntry(po_line=26, amount=100), 
                #LineMappingEntry(po_line=12, amount=20)
            ]
        ),
        attachment_path="D:/khsd-ap-bots/data/vestis.pdf",
    )
    result = execute_voucher_entry(test_plan, test_mode=True)
    print("Voucher Entry Result:")
    print(result)
