from playwright.sync_api import sync_playwright, PlaywrightTimeoutError
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
