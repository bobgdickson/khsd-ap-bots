from typing import List, Dict
from anyio import from_thread
from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session
from pydantic import BaseModel
from . import models, database
from .routes import process_log, bots_voucher_entry, bot_runs
from urllib.parse import unquote
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="AI Bot Process Log API")
app.include_router(process_log.router)
app.include_router(bots_voucher_entry.router)
app.include_router(bot_runs.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ExtractInvoiceIn(BaseModel):
    filename: str

@app.on_event("startup")
def on_startup():
    # create tables if they do not exist
    models.Base.metadata.create_all(bind=database.engine)


@app.get("/runids", response_model=List[str])
def list_runids(db: Session = Depends(database.get_db)):
    """List all distinct run IDs in the process log."""
    rows = db.query(models.BotProcessLog.runid).distinct().all()
    return [row[0] for row in rows]


@app.get("/runids/status_counts", response_model=Dict[str, int])
def status_counts(runid: str = Query(...), db: Session = Depends(database.get_db)):
    """Get count of each status for run IDs starting with the given value."""
    rows = (
        db.query(
            models.BotProcessLog.status,
            func.count(models.BotProcessLog.id)
        )
        .filter(models.BotProcessLog.runid.like(f"{runid}%"))
        .group_by(models.BotProcessLog.status)
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"No entries found for runid starting with '{runid}'")
    return {status: count for status, count in rows}


@app.delete("/runids/{runid}")
def delete_runid(runid: str, db: Session = Depends(database.get_db)):
    """Delete all log entries for a given run ID."""
    deleted = db.query(models.BotProcessLog).filter(models.BotProcessLog.runid == runid).delete()
    if deleted == 0:
        raise HTTPException(status_code=404, detail=f"No entries found to delete for runid '{runid}'")
    db.commit()
    return {"deleted": deleted}

@app.post("/extract_invoice")
def extract_invoice(payload: ExtractInvoiceIn):
    
    """
    Run the invoice_agent extraction process for the given filename and return the result.
    """
    filename = payload.filename
    from .bots.invoice_agent import run_invoice_extraction  # Adjust import as needed
    print(f"Extracting invoice from: {filename}")
    try:
        result = from_thread.run(run_invoice_extraction, filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return result.final_output

