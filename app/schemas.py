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

class VoucherRunLog(BaseModel):
    runid: str
    vendor: str
    processed: int = 0
    successes: int = 0
    duplicates: int = 0
    failures: int = 0

class VoucherProcessLog(BaseModel):
    runid: str
    filename: str
    voucher_id: str
    amount: float
    invoice: str
    status: str

class PDFExtractionResult(BaseModel):
    extracted_text: str
    image_base64: str
    success: bool
    description: str