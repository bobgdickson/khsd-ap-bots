from pathlib import Path
from typing import Optional
import shutil

from app import models, database
from app.bots.utils.misc import generate_runid


def is_numeric_voucher(voucher_id: str | None) -> bool:
    return bool(voucher_id) and str(voucher_id).isdigit()


def move_invoice_file(filepath: str | Path, result: dict, processed_dir: Path | None, duplicates_dir: Path | None):
    """
    Move file based on result status:
    - Numeric voucher_id or duplicate -> move to processed/duplicates respectively.
    - Otherwise leave in place.
    """
    if processed_dir is None or duplicates_dir is None:
        return

    processed_dir.mkdir(exist_ok=True)
    duplicates_dir.mkdir(exist_ok=True)

    voucher_id = result.get("voucher_id")
    duplicate = result.get("duplicate", False)
    src = Path(filepath)

    if duplicate:
        dest = duplicates_dir / src.name
        shutil.move(str(src), dest)
    elif is_numeric_voucher(voucher_id):
        dest = processed_dir / src.name
        shutil.move(str(src), dest)


def log_process_to_db(
    runid: Optional[str],
    filename: str,
    voucher_id: str,
    amount: float,
    invoice_number: str,
    status: str,
):
    """Persist process log similar to voucher_entry."""
    if not runid:
        return
    db = database.SessionLocal()
    try:
        payload = {
            "runid": runid,
            "filename": filename,
            "voucher_id": voucher_id,
            "amount": amount,
            "invoice": invoice_number,
            "status": status,
        }
        orm_row = models.BotProcessLog(**payload)
        db.add(orm_row)
        db.commit()
    finally:
        db.close()


__all__ = ["generate_runid", "is_numeric_voucher", "move_invoice_file", "log_process_to_db"]
