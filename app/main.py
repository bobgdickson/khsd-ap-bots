from typing import List, Dict

from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from . import models, database
from urllib.parse import unquote

app = FastAPI(title="AP Bot Process Log API")


@app.on_event("startup")
def on_startup():
    # create tables if they do not exist
    models.Base.metadata.create_all(bind=database.engine)


@app.get("/runids", response_model=List[str])
def list_runids(db: Session = Depends(database.get_db)):
    """List all distinct run IDs in the process log."""
    rows = db.query(models.APBotProcessLog.runid).distinct().all()
    return [row[0] for row in rows]


@app.get("/runids/status_counts", response_model=Dict[str, int])
def status_counts(runid: str = Query(...), db: Session = Depends(database.get_db)):
    """Get count of each status for run IDs starting with the given value."""
    rows = (
        db.query(
            models.APBotProcessLog.status,
            func.count(models.APBotProcessLog.id)
        )
        .filter(models.APBotProcessLog.runid.like(f"{runid}%"))
        .group_by(models.APBotProcessLog.status)
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"No entries found for runid starting with '{runid}'")
    return {status: count for status, count in rows}


@app.delete("/runids/{runid}")
def delete_runid(runid: str, db: Session = Depends(database.get_db)):
    """Delete all log entries for a given run ID."""
    deleted = db.query(models.APBotProcessLog).filter(models.APBotProcessLog.runid == runid).delete()
    if deleted == 0:
        raise HTTPException(status_code=404, detail=f"No entries found to delete for runid '{runid}'")
    db.commit()
    return {"deleted": deleted}
