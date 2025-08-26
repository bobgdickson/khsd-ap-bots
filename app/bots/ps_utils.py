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
    - Then full recursive DOM crawl fallback (TODO: optional)
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

    # Optional: add full recursive fallback here if needed

    raise Exception(f"❌ Could not find '{label_or_selector}' using role or input name/id.")

def ps_find_button(page, label_or_selector, timeout=5000):
    """
    Try to find a button inside PeopleSoft intelligently.
    - First tries get_by_role("button", name=label)
    - Then button[name=...] or button[id=...]
    - Then full recursive DOM crawl fallback (TODO: optional)
    """
    frame = ps_target_frame(page)

    # Try get_by_role with accessible name (label)
    try:
        locator = frame.get_by_role("button", name=label_or_selector)
        locator.wait_for(timeout=timeout)
        return locator
    except PlaywrightTimeoutError:
        pass

    # Try button[name=...] or id=...
    try:
        locator = frame.locator(f'button[name="{label_or_selector}"], button[id="{label_or_selector}"]')
        locator.wait_for(timeout=timeout)
        return locator
    except PlaywrightTimeoutError:
        pass

    # Optional: add full recursive fallback here if needed

    raise Exception(f"❌ Could not find button '{label_or_selector}' using role or button name/id.")

def ps_find_retry(page, label_or_selector, timeout=2000, retries=2, delay=1):
    """
    Retry wrapper for ps_find in case frame is still refreshing or being detached.
    """
    for attempt in range(retries):
        try:
            return ps_find(page, label_or_selector, timeout)
        except Exception as e:
            print(f"Retry {attempt + 1} for '{label_or_selector}' (reason: {e})")
            time.sleep(delay)
    raise Exception(f"❌ Failed to find '{label_or_selector}' after {retries} attempts.")

def ps_find_button_retry(page, label_or_selector, timeout=2000, retries=2, delay=1):
    """
    Retry wrapper for ps_find_button in case frame is still refreshing or being detached.
    """
    for attempt in range(retries):
        try:
            return ps_find_button(page, label_or_selector, timeout)
        except Exception as e:
            print(f"Retry {attempt + 1} for button '{label_or_selector}' (reason: {e})")
            time.sleep(delay)
    raise Exception(f"❌ Failed to find button '{label_or_selector}' after {retries} attempts.")

def handle_peoplesoft_alert(page, timeout=2000):
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