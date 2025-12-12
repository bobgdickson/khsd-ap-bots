from datetime import datetime
from typing import Any, Optional

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


class ScholarshipExtractedCheckAuthorization(BaseModel):
    name: str
    amount: float
    invoice_number: str


class KheduJournalExtractedData(BaseModel):
    name: str
    amount: float
    journal_type: str
    description: str
    source_account: str
    destination_account: str


class BotRunOut(BaseModel):
    runid: str
    bot_name: str
    status: str
    cancel_requested: bool
    test_mode: bool
    context: Optional[dict[str, Any]] = None
    message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class BotRunCancelRequest(BaseModel):
    reason: Optional[str] = None


class PaylineExcelItem(BaseModel):
    tab_name: str
    hr_requestor: str
    month_requested: str
    site: str
    emplid: str
    empl_rcd: int
    ern_ded_code: str
    amount: float
    earnings_begin_dt: str
    earnings_end_dt: str
    notes: Optional[str] = None

class PaylineExcelError(BaseModel):
    row_number: int
    tab_name: str
    error: str

class PaylineExcelExtractedData(BaseModel):
    items: list[PaylineExcelItem]
    errors: Optional[list[PaylineExcelError]] = None

class PaylineEntryResult(BaseModel):
    success: bool
    pay_group: str
    pay_end_dt: str
    off_cycle: str
    page_num: int
    line_num: int
    addl_nbr: int
    emplid: str
    amount: float

class PaylineRunLog(BaseModel):
    runid: str
    processed: int = 0
    successes: int = 0
    failures: int = 0


class DirectDepositExtractResult(BaseModel):
    emplid: str
    name: str
    date: datetime
    ssn: str
    bank_name: str
    routing_number: str
    bank_account: str
    checking_account: bool
    savings_account: bool
    amount_dollars: float
    amount_percentage: float


class DirectDepositProcessLog(BaseModel):
    runid: str
    emplid: str
    name: str
    bank_name: str
    routing_number: str
    bank_account: str
    amount_dollars: float
    status: str
    success: bool
    message: Optional[str] = None


class DepositEntryResult(BaseModel):
    success: bool
    message: Optional[str] = None