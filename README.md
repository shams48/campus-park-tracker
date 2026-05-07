# Campus Park Tracker

A real-time campus parking availability system. Drivers see which lots are open, gate events update occupancy live, and an admin dashboard lets staff correct mistaken events.

## What it does

- **Driver dashboard** — live lot status (Available / Near full / Full), free spaces, and a stepped-line chart of the last hour's occupancy.
- **Gate events** — `Car in` / `Car out` buttons simulate gate hardware. Server validates that you cannot enter a full lot or exit an empty one.
- **Admin dashboard** — searchable event log with a delete button. Deleting an event automatically corrects occupancy (event-sourced — no recompute job needed).
- **Auto-generated API docs** at `/docs` (Swagger UI from Pydantic schemas).

## Stack

- **Backend:** Python 3.13, FastAPI, SQLite (plain `sqlite3`, no ORM)
- **Frontend:** Vanilla HTML/CSS/JS, Chart.js for the occupancy chart
- **No build step** — open the file, refresh the browser

## Architecture

Three clean layers, dependencies pointing inward:

```
Browser  ──HTTP──>  app.py          (HTTP layer / FastAPI routes)
                      │
                      ├──>  occupancy.py  (Pure domain — no DB, no HTTP)
                      │
                      └──>  db.py         (Persistence — SQLite)
```

**Key design choice: event sourcing.** Occupancy is *not* stored as a counter on `lots`. It is derived from the `events` table:

```sql
SELECT
  SUM(CASE WHEN event_type = 'in'  THEN 1 ELSE 0 END) -
  SUM(CASE WHEN event_type = 'out' THEN 1 ELSE 0 END) AS occupancy
FROM events WHERE lot_id = ?
```

This means deleting a wrong event in the admin UI automatically corrects the count — no recompute logic needed. The event log is the single source of truth.

**Key design choice: pure domain module.** [`occupancy.py`](occupancy.py) imports neither FastAPI nor SQLite. The validation rules (`validate_event`) and status thresholds (`status_label`) take primitives in, return primitives out. Trivial to unit-test without spinning up a server or a database.

## Run it

Requires Python 3.10+.

```powershell
# Create venv and install deps
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Start the server
python -m uvicorn app:app --reload
```

Then open:

- Driver dashboard: http://127.0.0.1:8000/
- Admin dashboard:  http://127.0.0.1:8000/admin
- API docs:         http://127.0.0.1:8000/docs

The first run creates `campus_park.db` and seeds it with two lots (Lot A: 20 spaces, Lot B: 15 spaces).

## API

| Method | Path                              | Purpose                              |
|--------|-----------------------------------|--------------------------------------|
| GET    | `/api/lots`                       | List lots with current occupancy     |
| POST   | `/api/events`                     | Record a `Car in` / `Car out` event  |
| GET    | `/api/events?limit=N`             | Recent events (admin log)            |
| DELETE | `/api/events/{id}`                | Remove an event (corrects occupancy) |
| GET    | `/api/lots/{id}/history?minutes=N`| Occupancy points for chart           |

`POST /api/events` body:

```json
{ "lot_id": 1, "type": "in" }
```

Returns `409 Conflict` if the event would put the lot into an impossible state (entering a full lot, exiting an empty one).

## Tests

The domain layer is pure (no DB, no HTTP imports), so it can be unit-tested in isolation — no fixtures, no mocks, no test server.

```powershell
pip install -r requirements-dev.txt
python -m pytest -v
```

14 tests cover `validate_event` (entering full lots, exiting empty lots, unknown event types) and `status_label` (the 85% near-full threshold).

## Project layout

```
.
├── app.py            # FastAPI routes (HTTP layer)
├── occupancy.py      # Pure domain rules (validate_event, status_label)
├── db.py             # SQLite persistence (schema, queries, seed)
├── requirements.txt
├── requirements-dev.txt
├── tests/
│   └── test_occupancy.py
└── static/
    ├── index.html    # Driver dashboard
    ├── app.js        # Polling + Chart.js logic
    ├── admin.html    # Admin event log page
    ├── admin.js      # Event table with delete
    └── styles.css    # Dark theme
```

## License

MIT
