from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import database, models
from ..schemas import BotRunCancelRequest, BotRunOut

router = APIRouter(prefix="/bot-runs", tags=["bot_runs"])


@router.get("", response_model=List[BotRunOut])
def list_bot_runs(
    bot_name: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(database.get_db),
) -> List[models.BotRun]:
    query = db.query(models.BotRun)
    if bot_name:
        query = query.filter(models.BotRun.bot_name == bot_name)
    if status:
        query = query.filter(models.BotRun.status == status)
    return query.order_by(models.BotRun.created_at.desc()).all()


@router.get("/{runid}", response_model=BotRunOut)
def get_bot_run(runid: str, db: Session = Depends(database.get_db)) -> models.BotRun:
    run = db.query(models.BotRun).filter(models.BotRun.runid == runid).one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run '{runid}' not found")
    return run


@router.post("/{runid}/cancel", response_model=BotRunOut)
def cancel_bot_run(
    runid: str,
    payload: Optional[BotRunCancelRequest] = Body(default=None),
    db: Session = Depends(database.get_db),
) -> models.BotRun:
    run = db.query(models.BotRun).filter(models.BotRun.runid == runid).one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run '{runid}' not found")

    if run.status in {"completed", "failed", "cancelled"}:
        raise HTTPException(status_code=400, detail=f"Run is already {run.status}")

    run.cancel_requested = True
    if run.status not in {"cancel_requested"}:
        run.status = "cancel_requested"
    if payload and payload.reason:
        run.message = payload.reason

    db.commit()
    db.refresh(run)
    return run
