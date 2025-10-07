from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

from dateutil import parser


def normalize_date(date_str: str) -> str:
    """Convert various date formats into mm/dd/yyyy."""
    try:
        dt = parser.parse(date_str, dayfirst=False, fuzzy=True)
        return dt.strftime("%m/%d/%Y")
    except Exception:
        return None


def generate_runid(
    identifier: str,
    test_mode: bool = False,
    *,
    bot_name: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    initial_status: str = "pending",
) -> str:
    """Generate a run identifier and persist a BotRun record."""
    from app import database, models
    from sqlalchemy.exc import IntegrityError

    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    prefix = "test-" if test_mode else ""
    runid = f"{prefix}{identifier.capitalize()}-{timestamp}"

    session = database.SessionLocal()
    try:
        bot_run = models.BotRun(
            runid=runid,
            bot_name=bot_name or identifier,
            status=initial_status,
            cancel_requested=False,
            test_mode=test_mode,
            context=context,
        )
        session.add(bot_run)
        session.commit()
    except IntegrityError:
        session.rollback()
        runid = f"{runid}-{uuid4().hex[:4]}"
        bot_run = models.BotRun(
            runid=runid,
            bot_name=bot_name or identifier,
            status=initial_status,
            cancel_requested=False,
            test_mode=test_mode,
            context=context,
        )
        session.add(bot_run)
        session.commit()
    finally:
        session.close()

    return runid


def get_invoices_in_data():
    data_dir = Path("data")
    if not data_dir.exists():
        print("Data directory does not exist. Please create it and add invoice files.")
        return []
    invoices = [str(file) for file in data_dir.glob("*.pdf")]
    if not invoices:
        print("No invoice files found in the 'data' directory.")
    print(f"Found {len(invoices)} invoice files in 'data' directory.")
    return invoices


def _merge_context(existing: Optional[Dict[str, Any]], updates: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if updates is None:
        return existing
    combined = dict(existing or {})
    combined.update(updates)
    return combined


def get_bot_run(runid: str):
    from app import database, models

    session = database.SessionLocal()
    try:
        run = session.query(models.BotRun).filter(models.BotRun.runid == runid).one_or_none()
        if run:
            session.expunge(run)
        return run
    finally:
        session.close()


def update_bot_run_status(
    runid: str,
    status: str,
    *,
    message: Optional[str] = None,
    context_updates: Optional[Dict[str, Any]] = None,
    cancel_requested: Optional[bool] = None,
    session=None,
) -> bool:
    from app import database, models

    owns_session = session is None
    session = session or database.SessionLocal()
    try:
        bot_run = session.query(models.BotRun).filter(models.BotRun.runid == runid).one_or_none()
        if bot_run is None:
            return False
        bot_run.status = status
        if cancel_requested is not None:
            bot_run.cancel_requested = cancel_requested
        if message is not None:
            bot_run.message = message
        if context_updates:
            bot_run.context = _merge_context(bot_run.context, context_updates)
        session.commit()
        return True
    finally:
        if owns_session:
            session.close()


def request_run_cancel(runid: str, *, message: Optional[str] = None) -> bool:
    from app import database, models

    session = database.SessionLocal()
    try:
        bot_run = session.query(models.BotRun).filter(models.BotRun.runid == runid).one_or_none()
        if bot_run is None or bot_run.status in {"completed", "failed", "cancelled"}:
            return False
        bot_run.cancel_requested = True
        if bot_run.status not in {"cancelled", "failed"}:
            bot_run.status = "cancel_requested"
        if message:
            bot_run.message = message
        session.commit()
        return True
    finally:
        session.close()


def is_run_cancel_requested(runid: str) -> bool:
    from app import database, models

    session = database.SessionLocal()
    try:
        flag = (
            session.query(models.BotRun.cancel_requested)
            .filter(models.BotRun.runid == runid)
            .scalar()
        )
        return bool(flag)
    finally:
        session.close()
