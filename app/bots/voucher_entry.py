import os, time, asyncio
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from .ps_utils import ps_target_frame, ps_find_retry
from .invoice_agent import run_invoice_extraction

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

def get_invoices_in_data():
    """
    Get a list of invoice files from the 'data' directory.
    """
    data_dir = Path("data")
    if not data_dir.exists():
        print("Data directory does not exist. Please create it and add invoice files.")
        return []

    invoices = [str(file) for file in data_dir.glob("*.pdf")]
    if not invoices:
        print("No invoice files found in the 'data' directory.")
    print(f"Found {len(invoices)} invoice files in 'data' directory.")
    return invoices

invoices = get_invoices_in_data()

for invoice in invoices:
    print(f"Processing invoice: {invoice}")
    invoice_data = asyncio.run(run_invoice_extraction(invoice)).final_output
    if invoice_data:
        print(f"Extracted data for {invoice}: {invoice_data}")
    else:
        print(f"Failed to extract data for {invoice}")
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

        page.goto(PS_BASE_URL + "psp/KDFP92/EMPLOYEE/ERP/c/ENTER_VOUCHER_INFORMATION.VCHR_EXPRESS.GBL")
        page.wait_for_load_state('networkidle')

        # Voucher Regular Entry Page Logic
        invoice_input = ps_find_retry(page, "Invoice Number")
        invoice_input.fill(invoice_data.invoice_number)
        invoice_date_input = ps_find_retry(page, "Invoice Date")
        invoice_date_input.fill(invoice_data.invoice_date)
        gross_amount_input = ps_find_retry(page, "Gross Invoice Amount")
        gross_amount_input.fill(str(invoice_data.total_amount))
        if invoice_data.shipping_amount > 0:
            shipping_amount_input = ps_find_retry(page, "Freight Amount")
            shipping_amount_input.fill(str(invoice_data.shipping_amount))

        if invoice_data.sales_tax > 0:
            sales_tax_input = ps_find_retry(page, "Sales Tax Amount")
            sales_tax_input.fill(str(invoice_data.sales_tax))

        if invoice_data.miscellaneous_amount > 0:
            misc_amount_input = ps_find_retry(page, "Misc Charge Amount")
            misc_amount_input.fill(str(invoice_data.miscellaneous_amount))
        
        po_input = ps_find_retry(page, "PO Number")
        if invoice_data.purchase_order != "":
            po_bu_input = ps_find_retry(page, "PO Business Unit")
            
            # Handle KERNH prefix
            if invoice_data.purchase_order.startswith("KERNH"):
                # Split KERNH-00012345 into BU and PO
                bu, po = invoice_data.purchase_order.split("-", 1)
                po_bu_input.fill(bu)
                po_input.fill(po)
            else:
                # Assume full PO number is provided
                po_bu_input.fill("KERNH")
                po_input.fill(invoice_data.purchase_order)            
        po_input.focus()
        page.wait_for_timeout(100)
        page.keyboard.press('Tab')
        page.wait_for_timeout(100)
        page.keyboard.press('Tab')
        page.wait_for_timeout(100)
        page.keyboard.press('Tab')
        page.wait_for_timeout(100)
        page.keyboard.press('Enter') 
        page.wait_for_load_state('networkidle')

        # Possible Alert Message at this point
        try:
            page.wait_for_selector('div.alert-message', timeout=5000)
            alert_message = ps_find_retry(page, "alertmsg").inner_text()
            print(f"Alert message: {alert_message}")
        except PlaywrightTimeoutError:
            print("No alert message found.")
        page.pause()
        
        browser.close()

    t1 = time.time()
    print(f"✅ Voucher Entry bot completed in {t1 - t0:.2f} seconds.")
    print(f"Average time per invoice: {(t1 - t0) / len(invoices):.2f} seconds.")
    print("All done! 🎉")
