from pydantic import BaseModel
from typing import List, Optional
from datetime import date


class JournalHeader(BaseModel):
    business_unit: str
    journal_date: date
    description: str


class JournalLine(BaseModel):
    fund: Optional[str] = None
    resource: Optional[str] = None
    goal: Optional[str] = None
    function: Optional[str] = None
    account: Optional[str] = None
    site: Optional[str] = None
    department: Optional[str] = None
    project_id: Optional[str] = None
    class_field: Optional[str] = None  # "class" is reserved
    amount: float
    line_description: Optional[str] = None


class JournalEntryPlan(BaseModel):
    header: JournalHeader
    lines: List[JournalLine]
