from pydantic import BaseModel

class ExtractedInvoiceData(BaseModel):
    purchase_order: str
    invoice_number: str
    invoice_date: str
    total_amount: float
    sales_tax: float
    merchandise_amount: float
    miscellaneous_amount: float
    shipping_amount: float

class VoucherEntryResult(BaseModel):
    voucher_id: str
    duplicate: bool
    out_of_balance: bool
    