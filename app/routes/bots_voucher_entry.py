import os
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from ..bots.utils.misc import generate_runid, update_bot_run_status
from ..bots.voucher_entry import get_vendor_directory, run_vendor_entry

router = APIRouter(prefix="/bots/voucher-entry", tags=["bots"])

RUN_BOTS_LOCALLY = os.getenv("RUN_BOTS_LOCALLY", "false").lower() in {"1", "true", "yes", "y"}


class VoucherEntryRequest(BaseModel):
    vendor_key: str
    test_mode: bool = True
    rent_line: str = "FY26"
    attach_only: bool = False
    apo_override: Optional[str] = None
    additional_instructions: Optional[str] = None


class VoucherEntryAccepted(BaseModel):
    runid: str
    message: str = "Voucher entry run scheduled"


def _run_voucher_entry_job(payload: dict, runid: str) -> None:
    try:
        run_vendor_entry(
            vendor_key=payload["vendor_key"],
            test_mode=payload["test_mode"],
            rent_line=payload["rent_line"],
            attach_only=payload["attach_only"],
            apo_override=payload["apo_override"],
            additional_instructions=payload["additional_instructions"],
            runid=runid,
        )
    except Exception as exc:  # pragma: no cover - console logging for operator awareness
        print(f"[voucher_entry] Background run {runid} failed: {exc}")
        update_bot_run_status(runid, "failed", message=str(exc))


@router.post("", response_model=VoucherEntryAccepted, status_code=202)
def trigger_voucher_entry(payload: VoucherEntryRequest, background_tasks: BackgroundTasks) -> VoucherEntryAccepted:
    if not RUN_BOTS_LOCALLY:
        raise HTTPException(status_code=503, detail="Bot execution is disabled. Set RUN_BOTS_LOCALLY=1 to enable local runs.")

    try:
        vendor_path = get_vendor_directory(payload.vendor_key, payload.test_mode)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"Unknown vendor_key '{payload.vendor_key}'") from exc

    if not vendor_path.exists():
        raise HTTPException(status_code=400, detail=f"Vendor directory {vendor_path} not found")

    invoices = list(vendor_path.glob("*.pdf"))
    if not invoices:
        raise HTTPException(status_code=404, detail=f"No invoices found in {vendor_path}")

    runid = generate_runid(
        payload.vendor_key,
        payload.test_mode,
        bot_name="voucher_entry",
        context={
            "vendor_key": payload.vendor_key,
            "test_mode": payload.test_mode,
            "rent_line": payload.rent_line,
            "attach_only": payload.attach_only,
        },
        initial_status="queued",
    )
    background_tasks.add_task(_run_voucher_entry_job, payload.model_dump(), runid)

    return VoucherEntryAccepted(runid=runid)
