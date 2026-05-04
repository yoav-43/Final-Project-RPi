# Website — Fleet Management Dashboard

A Flask web application deployed on Heroku. It receives telemetry from the Raspberry Pi, stores it in a PostgreSQL database, and renders analytics dashboards for reviewing drive sessions.

## Directory Structure

```
Website/
├── wake_up/                  # Flask application (deployed to Heroku)
│   ├── app.py                # Web server: API routes + HTML views
│   ├── init_db.py            # One-time database schema setup
│   ├── Procfile              # Heroku process definition
│   ├── requirements.txt      # Python dependencies
│   ├── .python-version       # Python version pin
│   ├── static/
│   │   └── dashboard.js      # Chart.js rendering and alert table logic
│   └── templates/
│       ├── index.html        # Fleet overview page
│       └── drive.html        # Per-session analytics page
├── mac_aliases.txt           # Shell aliases for macOS (bash/zsh)
└── win_aliases.txt           # PowerShell functions for Windows
```

## Database Schema

Two tables managed by `init_db.py`:

**`drives`** — one row per drive session:

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL PK | Auto-incremented session ID. |
| `device_id` | VARCHAR(50) | Identifier of the Raspberry Pi. |
| `start_time` | TIMESTAMP | Set when `/api/start_drive` is called. |
| `end_time` | TIMESTAMP | Updated on every telemetry heartbeat; finalized by `/api/end_drive`. |
| `total_alerts` | INTEGER | Incremented whenever `is_distracted=true` or `perclos > 25`. |
| `video_url` | TEXT | Cloudinary CDN URL, set by `/api/end_drive`. |

**`drive_logs`** — one row per telemetry sample (~1 Hz):

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL PK | |
| `drive_id` | INTEGER FK | References `drives(id)`, cascades on delete. |
| `timestamp` | TIMESTAMP | Server-side insertion time. |
| `ear_value` | FLOAT | Eye Aspect Ratio. |
| `perclos_score` | FLOAT | % of frames with closed eyes. |
| `is_distracted` | BOOLEAN | True if head pose exceeded thresholds. |
| `head_yaw` | FLOAT | Horizontal head rotation (degrees). |
| `head_pitch` | FLOAT | Vertical head rotation (degrees). |

## API Endpoints

| Method | Route | Description |
|--------|-------|-------------|
| `POST` | `/api/start_drive` | Creates a new `drives` row. Returns `{"drive_id": int}`. |
| `POST` | `/api/telemetry` | Inserts a `drive_logs` row and updates the heartbeat + alert counter. |
| `POST` | `/api/end_drive` | Sets `end_time` and `video_url` on the `drives` row. |
| `GET` | `/api/history/<drive_id>` | Returns all `drive_logs` rows for a session as JSON (used by Chart.js). |
| `GET` | `/` | Renders the fleet overview dashboard (`index.html`). |
| `GET` | `/drive/<drive_id>` | Renders the per-session analytics dashboard (`drive.html`). |

## Web Dashboards

### Fleet Overview (`/`)

- Dark-themed table listing all drive sessions.
- Shows device ID, start/end times, total alert count, and a link to the session recording.
- Clicking any row navigates to that session's analytics page.
- Active sessions (no `end_time`) are shown with a green "● Active" indicator.

### Session Analytics (`/drive/<id>`)

- Embedded video player (Cloudinary MP4 stream).
- Four **Chart.js** line charts rendered from `/api/history/<id>`:
  - PERCLOS Score (%)
  - Eye Aspect Ratio
  - Head Yaw (horizontal)
  - Head Pitch (vertical)
- Alert log table listing every timestamp where fatigue or distraction was detected.

## Deployment

### Prerequisites

- [Heroku CLI](https://devcenter.heroku.com/articles/heroku-cli) installed and logged in.
- A Heroku app with the **Heroku Postgres** add-on attached.
- The `DATABASE_URL` config var is set automatically by the add-on.

### First-Time Setup

```bash
# Add the Heroku remote (run once)
heroku git:remote -a your-app-name

# Deploy only the website subdirectory
git subtree push --prefix Website/wake_up heroku main

# Initialize the database schema
heroku run python init_db.py
```

### Subsequent Deployments

```bash
git subtree push --prefix Website/wake_up heroku main
```

### Alias Shortcuts

Source the appropriate file for your OS to get shorthand commands:

**macOS / Linux (bash/zsh):**
```bash
source Website/mac_aliases.txt
deploy      # git subtree push to Heroku
db-init     # heroku run python init_db.py
backup      # git add . && commit && push to GitHub
```

**Windows (PowerShell):**
```powershell
. .\Website\win_aliases.txt
deploy
db-init
backup
```

## Local Development

```bash
cd Website/wake_up
pip install -r requirements.txt
export DATABASE_URL="postgresql://user:pass@localhost/wakeup"
python app.py
```

The app runs on `http://localhost:5000` in debug mode.

## Dependencies

```
flask
gunicorn
psycopg2-binary
requests
cloudinary
```
