import os, time, asyncio
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from app.bots.ps_utils import ps_target_frame, ps_find_retry, handle_peoplesoft_alert, ps_find_button, ps_find_button_retry
from app.bots.invoice_agent import run_invoice_extraction
from app.schemas import ExtractedInvoiceData

load_dotenv()  # Load .env into environment

USERNAME = os.getenv("PEOPLESOFT_USERNAME")
PASSWORD = os.getenv("PEOPLESOFT_PASSWORD")

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

def voucher_playwright_bot(
        invoice_data: ExtractedInvoiceData, 
        royal_style_entry: bool = False,
        test_mode: bool = False, 
        wait_time: int = 500
    ):
    short_wait = wait_time
    long_wait = wait_time * 3
    apo_flag = False  # Flag to indicate if APO PO is used
    if test_mode == True:
        PS_BASE_URL = os.getenv("PEOPLESOFT_TEST_ENV", "https://kdfq92.hosted.cherryroad.com/") + "psp/KDFQ92"
        print(f"Running in TEST mode against {PS_BASE_URL}")
    else:
        PS_BASE_URL = os.getenv("PEOPLESOFT_ENV") + "psp/KDFP92"
        print(f"Running in PRODUCTION mode against {PS_BASE_URL}")
    if invoice_data:
        print(f"Extracted data for: {invoice_data}")
    else:
        print(f"No invoice data provided, exiting.")
    with sync_playwright() as p:
        print("Starting PeopleSoft voucher entry bot...")
        try:
            # Step 1: Launch browser and go to login page
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

            page.goto(PS_BASE_URL + "/EMPLOYEE/ERP/c/ENTER_VOUCHER_INFORMATION.VCHR_EXPRESS.GBL")
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

            # Handle KERNH prefix in PO
            if invoice_data.purchase_order.startswith("KERNH"):
                # Split KERNH-00012345 into BU and PO
                bu, po = invoice_data.purchase_order.split("-", 1)                      
            else:
                # Assume full PO number is provided
                bu = "KERNH"
                po = invoice_data.purchase_order

            if royal_style_entry:
                # Enters PO on entry screen 'Royal Style'
                if invoice_data.purchase_order != "":
                    po_bu_input = ps_find_retry(page, "PO Business Unit")
                    po_bu_input.fill(bu)    
                    # Set APO Flag to True if PO contains "APO"
                    if "APO" in invoice_data.purchase_order:
                        apo_flag = True

                    po_input.fill(po)

            po_input.focus()
            page.wait_for_timeout(short_wait)
            page.keyboard.press('Tab')
            page.wait_for_timeout(short_wait)
            page.keyboard.press('Tab')
            page.wait_for_timeout(short_wait)
            page.keyboard.press('Tab')
            page.wait_for_timeout(short_wait)
            page.keyboard.press('Enter') 
            page.wait_for_load_state('networkidle')

            # Possible Alert Message at this point
            alert_text = handle_peoplesoft_alert(page)
            if alert_text:
                # Handle specific alert messages if needed
                if "Invalid value" in alert_text:
                    print("❌ Please check the PO number.  Stopping Entry.")
                    return
            
            # Voucher Page now
            if apo_flag and royal_style_entry:
                # APO Checked and PO entered on entry screen, Need to override Merch amount on line 1
                line_amount_input = ps_find_retry(page, "Line Amount")
                line_amount_input.fill(str(invoice_data.merchandise_amount))
                merch_line_input = ps_find_retry(page, "MERCHANDISE_AMT_DL$0")
                merch_line_input.fill(str(invoice_data.merchandise_amount))
                calculate_button = ps_find_retry(page, "VCHR_BAL_WRK_OD_BALANCE_PB")
                calculate_button.click()
                page.wait_for_load_state('networkidle')
            else:
                # Execute Copy from PO style entry  
                #page.pause()               
                copy_from_po_button = ps_find_button(page, "Copy From Source Document")
                copy_from_po_button.click()
                po_bu_search_input = ps_find_retry(page, "PO Unit")
                po_bu_search_input.fill("KERNH")
                po_search_input = ps_find_retry(page, "PO Number")
                po_search_input.fill(po)
                copy_po_input = ps_find_button(page, "Copy PO")
                copy_po_input.click()
                page.wait_for_load_state('networkidle')
                #page.pause()
                # Copy from PO Screen
                frame = ps_target_frame(page)
                search_button = frame.get_by_role("button", name="Search", exact=True)
                search_button.click()
                # Check page for existence of text "Class Leasing" or "Mobile Modular", set class_mobile_flag = True
                page.wait_for_load_state('networkidle')
                try:
                    class_leasing_locator = ps_target_frame(page).get_by_text("CLASS LEASING", exact=True)
                    class_leasing_locator.wait_for(timeout=2000)
                    class_mobile_flag = True
                    print("Class Leasing found in PO, setting class_mobile_flag = True")
                except PlaywrightTimeoutError:
                    try:
                        mobile_modular_locator = ps_target_frame(page).get_by_text("Mobile Modular", exact=True)
                        mobile_modular_locator.wait_for(timeout=2000)
                        class_mobile_flag = True
                        print("Mobile Modular found in PO, setting class_mobile_flag = True")
                    except PlaywrightTimeoutError:
                        class_mobile_flag = False
                        print("Class Leasing or Mobile Modular NOT found in PO, setting class_mobile_flag = False")
                
                # Class Mobile Handling
                if class_mobile_flag:
                    # TODO: Add classmobile logic
                    pass

                # APO Handling just uses the first line, class mobile code above will be on the 'correct' Rent line by this point 
                checkbox = ps_target_frame(page).locator("[id=\"VCHR_PANELS_WRK_LINE_SELECT_PO$0\"]")
                checkbox.check()
                merch_po_line = ps_target_frame(page).locator("[id=\"VCHR_MTCH_WS4_MERCHANDISE_AMT$0\"]")
                merch_po_line.fill(str(invoice_data.merchandise_amount))
                copy_button = ps_target_frame(page).get_by_role("button", name="Copy Selected Lines")
                copy_button.click()
                page.wait_for_load_state('networkidle')
                # Possible Alert Message re Sales Tax at this point
                alert_text = handle_peoplesoft_alert(page)
                if alert_text:
                    # Handle specific alert messages if needed
                    if "Sales Tax" in alert_text:
                        ok_button = ps_target_frame(page).get_by_role("button", name="OK")
                        ok_button.click()

                # Delete auto-added first line (since we copied PO line with chartfields, etc in)
                delete_line = ps_target_frame(page).get_by_role("button", name="Delete row").first
                delete_line.click()
                ok_button = ps_target_frame(page).get_by_role("button", name="OK")
                ok_button.click()
                page.wait_for_load_state('networkidle')
                page.pause()

            # TODO Add Accounting Date FYE override

            # Attachment Handling
            
            attachment_button = ps_target_frame(page).get_by_role("link", name="Attachments")
            attachment_button.click()
            page.wait_for_load_state('networkidle')
            
            page.pause()
            add_attach_button = ps_find_button(page, "Add Attachment")
            add_attach_button.click()
            page.wait_for_load_state('networkidle')

            browse_attach_button = ps_find_button(page, "Browse")
            browse_attach_button.click()
            page.wait_for_load_state('networkidle')

            page.pause()



        finally:
            if 'browser' in locals():
                print("Closing browser...")    
                browser.close()

def run_voucher_entry():
    t0 = time.time()
    invoices = get_invoices_in_data()

    for invoice in invoices:
        print(f"Processing invoice: {invoice}")
        invoice_data = asyncio.run(run_invoice_extraction(invoice)).final_output
        if invoice_data:
            print(f"Extracted data for {invoice}: {invoice_data}")
            voucher_playwright_bot(invoice_data)
        else:
            print(f"Failed to extract data for {invoice}")
    t1 = time.time()
    print(f"✅ Voucher Entry bot completed in {t1 - t0:.2f} seconds.")
    print(f"Average time per invoice: {(t1 - t0) / len(invoices):.2f} seconds.")
    print("All done! 🎉")

def test_voucher_entry():
    print("Running test voucher entry with sample data...")
    test_invoice_data = ExtractedInvoiceData(
        purchase_order="KERNH-APO950043I",
        invoice_number="INV-1001",
        invoice_date="8/1/2025",
        total_amount=1500.00,
        sales_tax=75.00,
        merchandise_amount=1300.00,
        miscellaneous_amount=25.00,
        shipping_amount=100.00
    )
    voucher_playwright_bot(test_invoice_data, test_mode=True, royal_style_entry=True, wait_time=100)

if __name__ == "__main__":
    test_voucher_entry()
    # run_voucher_entry()