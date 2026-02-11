from pydantic import BaseModel, Field
from typing import List, Optional

class InvoiceLine(BaseModel):
    description: str
    quantity: float | None = None
    unit_price: float | None = None
    line_amount: float

class ExtractedInvoice(BaseModel):
    invoice_number: str
    vendor_name: str
    invoice_date: str
    total_amount: float
    purchase_order_raw: Optional[str] = None
    fuzzy_po_candidates: List[str] = Field(default_factory=list)
    lines: List[InvoiceLine]

class POLine(BaseModel):
    po_id: str
    po_line: int
    sched: int
    distrib: int
    description: str
    amount: float
    account: str
    fund: Optional[str] = None
    program: Optional[str] = None

class ValidatedPO(BaseModel):
    po_id: str
    vendor_id: str
    vendor_name: str
    confidence: float = 0.0

class LineMappingEntry(BaseModel):
    po_line: int
    amount: float

class LineMapping(BaseModel):
    strategy: str
    lines: List[LineMappingEntry]

class VoucherEntryPlan(BaseModel):
    po: ValidatedPO
    invoice: ExtractedInvoice
    mapping: LineMapping
    attachment_path: str
    po_lines: Optional[List[POLine]] = None


class ExecutionDecision(BaseModel):
    execute: bool
    reason: str
