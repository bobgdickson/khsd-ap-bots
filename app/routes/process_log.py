from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import database, models

router = APIRouter(prefix="/process-logs", tags=["process_logs"])


class BotProcessLogOut(BaseModel):
    id: int
    runid: str
    filename: Optional[str]
    voucher_id: Optional[str]
    amount: Optional[float]
    invoice: Optional[str]
    status: Optional[str]

    class Config:
        orm_mode = True


@router.get("", response_model=List[BotProcessLogOut])
def list_process_logs(
    runid: Optional[str] = Query(None, description="Filter logs by runid"),
    db: Session = Depends(database.get_db),
) -> List[models.BotProcessLog]:
    query = db.query(models.BotProcessLog)
    if runid:
        query = query.filter(models.BotProcessLog.runid == runid)
    return query.order_by(models.BotProcessLog.id.desc()).all()

