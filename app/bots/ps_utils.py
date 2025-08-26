from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
import time

def ps_target_frame(page):
    """Get the main PeopleSoft frame, usually 'TargetContent'."""
    return page.frame(name="TargetContent")

def ps_find(page, label_or_selector, timeout=5000):
    """
    Try to find an input inside PeopleSoft intelligently.
    - First tries get_by_role("textbox", name=label)
    - Then input[name=...] or input[id=...]
    """
    frame = ps_target_frame(page)

    # Try get_by_role with accessible name (label)
    try:
        locator = frame.get_by_role("textbox", name=label_or_selector)
        locator.wait_for(timeout=timeout)
        return locator
    except PlaywrightTimeoutError:
        pass

    # Try input[name=...] or id=...
    try:
        locator = frame.locator(f'input[name="{label_or_selector}"], input[id="{label_or_selector}"]')
        locator.wait_for(timeout=timeout)
        return locator
    except PlaywrightTimeoutError:
        pass

    raise Exception(f"❌ Could not find '{label_or_selector}' using role or input name/id.")

def ps_find_button(page, label_or_selector, timeout=5000):
    """
    Try to find a button inside PeopleSoft intelligently.
    - First tries get_by_role("button", name=label)
    - Then button[name=...] or button[id=...]
    """
    frame = ps_target_frame(page)

    try:
        locator = frame.get_by_role("button", name=label_or_selector)
        locator.wait_for(timeout=timeout)
        return locator
    except PlaywrightTimeoutError:
        pass

    try:
        locator = frame.locator(f'button[name="{label_or_selector}"], button[id="{label_or_selector}"]')
        locator.wait_for(timeout=timeout)
        return locator
    except PlaywrightTimeoutError:
        pass

    raise Exception(f"❌ Could not find button '{label_or_selector}' using role or button name/id.")

def ps_find_retry(page, label_or_selector, timeout=3000, retries=2, delay=1):
    """Retry wrapper for ps_find in case frame is still refreshing or being detached."""
    for attempt in range(retries):
        try:
            return ps_find(page, label_or_selector, timeout)
        except Exception as e:
            print(f"Retry {attempt + 1} for '{label_or_selector}' (reason: {e})")
            time.sleep(delay)
    raise Exception(f"❌ Failed to find '{label_or_selector}' after {retries} attempts.")

def ps_find_button_retry(page, label_or_selector, timeout=3000, retries=2, delay=1):
    """Retry wrapper for ps_find_button in case frame is still refreshing or being detached."""
    for attempt in range(retries):
        try:
            return ps_find_button(page, label_or_selector, timeout)
        except Exception as e:
            print(f"Retry {attempt + 1} for button '{label_or_selector}' (reason: {e})")
            time.sleep(delay)
    raise Exception(f"❌ Failed to find button '{label_or_selector}' after {retries} attempts.")

def handle_peoplesoft_alert(page, timeout=3000):
    """Detects and returns PeopleSoft alert text, clicking OK is up to caller."""
    try:
        alert = page.locator("#alertmsg")
        alert.wait_for(timeout=timeout)
        text = alert.text_content()
        print(f"❌ PeopleSoft Modal: {text.strip()}")
        return text.strip()
    except PlaywrightTimeoutError:
        return None

def find_modal_button(page, label: str, timeout: int = 2000):
    """
    Searches through ptModFrame_0..9 for a button with the given label.
    Returns the locator if found, else raises RuntimeError.
    """
    for i in range(0, 10):  # adjust if you expect more
        try:
            locator = page.locator(f"iframe[name='ptModFrame_{i}']")
            frame = locator.content_frame
            button = frame.get_by_role("button", name=label, exact=True)
            button.wait_for(timeout=timeout)
            print(f"Found '{label}' in ptModFrame_{i}")
            return button
        except Exception:
            continue
    raise RuntimeError(f"Button '{label}' not found in any ptModFrame_X iframe")

# ----------------------------------------------------------------------
# New streamlined helpers
# ----------------------------------------------------------------------

def handle_alerts(page) -> tuple[str | None, bool, bool]:
    """
    Handles PS alerts and returns (alert_text, duplicate_flag, out_of_balance_flag).
    Clicks OK automatically when alert is found.
    """
    alert_text = handle_peoplesoft_alert(page)
    duplicate = out_of_balance = False
    if alert_text:
        ok_button = page.get_by_role("button", name="OK")
        try:
            ok_button.click()
        except Exception:
            pass
        if "Duplicate" in alert_text:
            duplicate = True
        elif "out of balance" in alert_text.lower():
            out_of_balance = True
    return alert_text, duplicate, out_of_balance

def ps_wait(page, factor=1, base=3000):
    """Simple wrapper to avoid repeating wait_for_timeout math."""
    page.wait_for_timeout(base * factor)

def find_rent_line(page, rent_line: str) -> bool:
    """
    Loops through PO lines looking for a rent line containing rent_line text.
    Uses 'Show next row' button until exhausted. Returns True if found.
    """
    target_frame = ps_target_frame(page)
    while True:
        try:
            target_frame.get_by_text(rent_line).wait_for(timeout=3000)
            print(f"✅ Found rent line {rent_line}")
            return True
        except PlaywrightTimeoutError:
            print("No rent line, going next...")
            try:
                next_button = page.locator("iframe[name='TargetContent']").content_frame.get_by_role("button", name="Show next row")
                next_button.wait_for(state="visible", timeout=3000)
                next_button.click()
                page.wait_for_timeout(3000)  # give PS time to refresh the grid
            except PlaywrightTimeoutError:
                print(f"❌ Rent line {rent_line} not found, and no more rows.")
                return False

def get_voucher_id(page) -> str:
    """
    Scrape the Voucher ID from the TargetContent frame after save.
    Waits until it's visible and no longer 'NEXT'.
    """
    frame = ps_target_frame(page)
    loc = frame.locator("#win0divVOUCHER_VOUCHER_ID")
    loc.wait_for(state="visible", timeout=10000)
    vid = loc.inner_text().strip()
    return vid

def handle_modal_sequence(page, labels: list[str], file: str | None = None):
    """
    Clicks through a sequence of buttons in ptModFrame_X modals.
    Optionally attaches a file when the 'Browse' step is encountered.
    """
    for label in labels:
        button = find_modal_button(page, label)
        if label.lower() == "browse" and file:
            with page.expect_file_chooser() as fc_info:
                button.click(force=True)
            fc_info.value.set_files(file)
        else:
            button.click()
        page.wait_for_timeout(1000)
