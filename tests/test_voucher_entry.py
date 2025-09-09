import random
from app.schemas import ExtractedInvoiceData
from app.bots.voucher_entry import voucher_playwright_bot


def test_voucher_entry():
    print("Running test voucher entry with sample data...")
    # Random invoice number
    invoice = str(random.randint(1000000, 9999999))
    test_classmobile_invoice_data = ExtractedInvoiceData(
        purchase_order="KERNH-CON21057",
        invoice_number=invoice,
        invoice_date="8/1/2025",
        total_amount=625.00,
        sales_tax=0,
        merchandise_amount=625.00,
        miscellaneous_amount=0.00,
        shipping_amount=0.00,
    )
    filepath = "./data/sample.pdf"
    classmobile_result = voucher_playwright_bot(
        test_classmobile_invoice_data,
        filepath=filepath,
        rent_line="FY25",
        test_mode=True,
        royal_style_entry=False,
    )
    assert classmobile_result.voucher_id not in [
        "Duplicate",
        "Out of Balance",
        "Invalid PO",
        f"No FY25 Rent Line on PO",
    ]

    classmobile_duplicate = voucher_playwright_bot(
        test_classmobile_invoice_data,
        filepath=filepath,
        rent_line="FY25",
        test_mode=True,
        royal_style_entry=False,
    )
    assert classmobile_duplicate.voucher_id == "Duplicate"

    classmobile_norent = voucher_playwright_bot(
        ExtractedInvoiceData(
            purchase_order="KERNH-CON21057",
            invoice_number=str(random.randint(1000000, 9999999)),
            invoice_date="8/1/2025",
            total_amount=625.00,
            sales_tax=0,
            merchandise_amount=625.00,
            miscellaneous_amount=0.00,
            shipping_amount=0.00,
        ),
        filepath=filepath,
        rent_line="FY20",
        test_mode=True,
        royal_style_entry=False,
    )
    assert classmobile_norent.voucher_id == "No FY20 Rent Line on PO"

    test_royalstyle_invoice_data = ExtractedInvoiceData(
        purchase_order="KERNH-APO0001234",
        invoice_number=str(random.randint(1000000, 9999999)),
        invoice_date="8/1/2025",
        total_amount=1100.00,
        sales_tax=0,
        merchandise_amount=1100.00,
        miscellaneous_amount=0.00,
        shipping_amount=0.00,
    )
    royalstyle_invalid_result = voucher_playwright_bot(
        test_royalstyle_invoice_data,
        filepath=filepath,
        test_mode=True,
        royal_style_entry=True,
    )
    assert royalstyle_invalid_result.voucher_id == "Invalid PO"

    test_royalstyle_invoice_data = ExtractedInvoiceData(
        purchase_order="KERNH-APO950043I",
        invoice_number=str(random.randint(1000000, 9999999)),
        invoice_date="8/1/2025",
        total_amount=1100.00,
        sales_tax=0,
        merchandise_amount=1100.00,
        miscellaneous_amount=0.00,
        shipping_amount=0.00,
    )
    royalstyle_result = voucher_playwright_bot(
        test_royalstyle_invoice_data,
        filepath=filepath,
        test_mode=True,
        royal_style_entry=True,
    )
    assert royalstyle_result.voucher_id not in [
        "Duplicate",
        "Out of Balance",
        "Invalid PO",
        f"No FY25 Rent Line on PO",
    ]
    
    cdw_result = voucher_playwright_bot(
        ExtractedInvoiceData(
            purchase_order="KERNH-0000220344",
            invoice_number="AC2AL5S",
            invoice_date="8/27/2025",
            total_amount=625.00,
            sales_tax=0,
            merchandise_amount=625.00,
            miscellaneous_amount=0.00,
            shipping_amount=0.00,
        ),
        filepath = "./data/sample.pdf",
        test_mode=True,
        royal_style_entry=False,
        attach_only=True,
    )
    assert cdw_result.voucher_id not in ["Duplicate", "Out of Balance", "Invalid PO", f"No FY25 Rent Line on PO"]

    no_cdw_result = voucher_playwright_bot(
        ExtractedInvoiceData(
            purchase_order="KERNH-0000220344",
            invoice_number="AC2AL5S",
            invoice_date="8/27/2025",
            total_amount=625.00,
            sales_tax=0,
            merchandise_amount=625.00,
            miscellaneous_amount=0.00,
            shipping_amount=0.00,
        ),
        filepath = "./data/sample.pdf",
        test_mode=True,
        royal_style_entry=False,
        attach_only=True,
    )
    assert no_cdw_result.voucher_id in ["No voucher"]
