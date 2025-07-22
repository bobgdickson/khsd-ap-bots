import os, time
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from .ps_utils import ps_target_frame, ps_find_retry

load_dotenv()  # Load .env into environment

USERNAME = os.getenv("PEOPLESOFT_USERNAME")
PASSWORD = os.getenv("PEOPLESOFT_PASSWORD")
TEST = 'no'
print(f"Using test mode: {TEST}")
if TEST == 'yes':
    PS_BASE_URL = os.getenv("PEOPLESOFT_TEST_ENV", "https://kdhr92.hosted.cherryroad.com/")
else:
    PS_BASE_URL = os.getenv("PEOPLESOFT_ENV")

print(f"Using username: {USERNAME}")

invoices = [
    # Add your invoices here
    '123.pdf'
]


with sync_playwright() as p:
    t0 = time.time()
    print("Starting PeopleSoft voucher entry bot...")
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()

    page.goto(PS_BASE_URL)

    # Step 2: Wait and fill email
    page.wait_for_selector('input#i0116')
    page.fill('input#i0116', USERNAME)
    page.click('input[type="submit"]')  # "Next" button

    # Step 3: Wait and fill password
    page.wait_for_selector('input#i0118')
    page.fill('input#i0118', PASSWORD)
    page.click('input[type="submit"]')  # "Sign in" button

    page.wait_for_load_state('networkidle')

    for invoice in invoices:

        page.goto(PS_BASE_URL + "TODO voucher entry page URL")
        page.wait_for_load_state('networkidle')

        # TODO Voucher Entry Logic

        

        pass

    browser.close()
    t1 = time.time()
    print(f"✅ Uncheck bot completed in {t1 - t0:.2f} seconds.")
    print(f"Average time per EMPLID: {(t1 - t0) / len(invoices):.2f} seconds.")
    print("All done! 🎉")
