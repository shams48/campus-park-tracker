from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import db
import occupancy

STATIC_DIR = Path(__file__).parent / "static"


def _to_iso_utc(s: str) -> str:
    # SQLite default datetime('now') returns "YYYY-MM-DD HH:MM:SS" (UTC, no Z).
    # Normalize to ISO 8601 with Z so JS Date can parse it as UTC.
    s = s.replace(" ", "T")
    return s if s.endswith("Z") else s + "Z"


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="Campus Park Tracker", version="0.1.0", lifespan=lifespan)


class EventIn(BaseModel):
    lot_id: int
    type: Literal["in", "out"]


def _shape_lot(lot: dict) -> dict:
    return {
        "id": lot["id"],
        "name": lot["name"],
        "capacity": lot["capacity"],
        "occupancy": lot["occupancy"],
        "free": lot["capacity"] - lot["occupancy"],
        "status": occupancy.status_label(lot["occupancy"], lot["capacity"]),
    }


@app.get("/api/lots")
def list_lots() -> list[dict]:
    return [_shape_lot(l) for l in db.get_lots_with_occupancy()]


@app.post("/api/events", status_code=201)
def create_event(payload: EventIn) -> dict:
    lot = db.get_lot(payload.lot_id)
    if not lot:
        raise HTTPException(status_code=404, detail="Lot not found")

    current = db.get_occupancy(payload.lot_id)
    try:
        occupancy.validate_event(
            current=current, capacity=lot["capacity"], event_type=payload.type
        )
    except occupancy.OccupancyError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    db.record_event(payload.lot_id, payload.type)
    new_current = db.get_occupancy(payload.lot_id)
    return {
        "lot_id": payload.lot_id,
        "occupancy": new_current,
        "capacity": lot["capacity"],
        "free": lot["capacity"] - new_current,
        "status": occupancy.status_label(new_current, lot["capacity"]),
    }


@app.get("/api/events")
def list_events(limit: int = Query(default=100, ge=1, le=500)) -> list[dict]:
    return [
        {
            "id": e["id"],
            "lot_id": e["lot_id"],
            "lot_name": e["lot_name"],
            "type": e["event_type"],
            "created_at": _to_iso_utc(e["created_at"]),
        }
        for e in db.list_events(limit=limit)
    ]


@app.delete("/api/events/{event_id}", status_code=204)
def delete_event(event_id: int) -> None:
    if not db.delete_event(event_id):
        raise HTTPException(status_code=404, detail="Event not found")


@app.get("/api/lots/{lot_id}/history")
def lot_history(lot_id: int, minutes: int = Query(default=60, ge=1, le=1440)) -> dict:
    lot = db.get_lot(lot_id)
    if not lot:
        raise HTTPException(status_code=404, detail="Lot not found")

    now = datetime.now(timezone.utc)
    since = now - timedelta(minutes=minutes)
    since_sqlite = since.strftime("%Y-%m-%d %H:%M:%S")

    baseline, events = db.get_history(lot_id, since_sqlite)
    points = [{"t": since.isoformat().replace("+00:00", "Z"), "occupancy": baseline}]
    current = baseline
    for e in events:
        current += 1 if e["event_type"] == "in" else -1
        points.append({"t": _to_iso_utc(e["created_at"]), "occupancy": current})
    points.append({"t": now.isoformat().replace("+00:00", "Z"), "occupancy": current})

    return {
        "lot_id": lot_id,
        "lot_name": lot["name"],
        "capacity": lot["capacity"],
        "minutes": minutes,
        "points": points,
    }


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def root() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/admin")
def admin() -> FileResponse:
    return FileResponse(STATIC_DIR / "admin.html")
