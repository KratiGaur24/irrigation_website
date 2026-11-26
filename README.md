# Smart Irrigation App

For the complete codebase overview, setup, run/test commands, API reference, and implementation roadmap, start with [PROJECT_GUIDE.md](PROJECT_GUIDE.md).

The repository root is `project/`. The Database V2 backend lives in `backend/` and uses one PostgreSQL schema for development and production.

## Backend setup

Use Python 3.11 or newer and PostgreSQL. From the repository root:

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Set `DATABASE_URL` in `backend/.env`, for example:

```text
DATABASE_URL=postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/smart_irrigation_db
```

Never commit `.env`; it is ignored by `backend/.gitignore`.

Create the PostgreSQL database (from `psql` as a role allowed to create databases):

```sql
CREATE DATABASE smart_irrigation_db;
```

Apply the initial schema:

```powershell
python -m alembic upgrade head
```

Set a demo password in the environment, then seed linked demonstration entities:

```powershell
$env:DEMO_USER_PASSWORD = 'choose-a-local-demo-password'
python -m app.db.seed
```

The seed creates a demo user, farm, field, Wheat crop row, active crop cycle, and ESP32 device. It does not seed any agronomic, soil, calibration, weather, or rule threshold values. The password is stored only as a PBKDF2-SHA256 hash.

Start the API:

```powershell
python -m uvicorn app.main:app --reload
```

Health check: `http://127.0.0.1:8000/health`.

Inspect the schema with pgAdmin's Query Tool or `psql`:

```sql
\dt
\d+ sensor_readings
SELECT * FROM alembic_version;
```

## Data integrity

All entity IDs use PostgreSQL UUIDs; append-only sensor, weather, and water-balance histories use identity BIGINT keys. Foreign keys use `ON DELETE RESTRICT` and ORM relationships do not cascade deletes, preserving historical records. Remove or anonymize related records explicitly before deleting referenced entities. Agronomic reference inputs, field soil measurements, runtime observations, calibration data, water-balance snapshots, and operational rules remain separate.


## Field location and weather Phase 1

Fields may store nullable latitude/longitude and optional location source/accuracy. Farm coordinates remain general farm location and are not copied into fields. Weather uses a valid field coordinate pair first, otherwise a valid farm pair, otherwise asks for location setup. Set the farm location by searching and explicitly choosing a result during farm setup or under More → Edit Farm; the farm fallback is labeled approximate. Field coordinates can still be supplied through the existing `POST /fields` API. The API does not infer agronomic zones. `crop_cycle.regional_profile` remains caller-managed; Western Uttar Pradesh / NWPZ is the only validated MVP profile.

Apply migration `0005_weather_location` with `python -m alembic upgrade head`. It preserves old records and adds nullable requested coordinates to weather snapshots. Forecasts with unknown legacy coordinates remain in history but require a fresh refresh before appearing on the current weather card. See [the Step 1.5 location and weather report](FARM_LOCATION_WEATHER_REPORT.md) for the implementation, checks, and manual browser checklist.

Weather is fetched only through `POST /fields/{field_id}/weather/refresh`; GET endpoints read stored PostgreSQL records. Open-Meteo requests are retained as separate snapshots identified by `fetched_at`; forecast reads select the newest snapshot per forecast timestamp. Forecast precipitation is stored as `forecast_rainfall_mm`; `actual_rainfall_mm` remains null. Hourly shortwave radiation arrives as the preceding-hour mean in W/m? and is converted to MJ/m? per hour (`W/m? ? 3600 / 1,000,000`). Provider local timestamps are interpreted in the returned IANA timezone and stored in UTC. Data is provided by [Open-Meteo](https://open-meteo.com/) and must retain `source="open-meteo"`.
## Frontend dashboard

The frontend uses project-local Node.js dependencies in `frontend/node_modules/`, including a pinned Node.js runtime; it does not need a Python `.venv`. After `npm install`, Windows users can run `frontend/start.cmd` (or `cd frontend` then `.\start.cmd` in PowerShell) to launch the dashboard using that local runtime without changing their system PATH. Open the URL printed by Vite, normally `http://127.0.0.1:5173`, and keep the backend running separately. The `.env` file stores configuration and is separate from the dependency environment.

A lightweight Vite frontend lives in `frontend/` and consumes the FastAPI service through one typed API client. Copy `frontend/.env.example` to `frontend/.env` and set `VITE_API_BASE_URL` if the backend uses a different address. From that directory, run `npm install` and `npm run dev`. The dashboard loads the field, crop cycle, soil profile, device, sensor, and stored weather data independently so a failure in one section does not hide the rest. Weather retrieval uses the refresh icon and also runs after saving a confirmed farm location; ordinary dashboard reads never trigger a provider fetch.

Manual irrigation controls and Emergency Stop now use backend session endpoints. Local development explicitly uses simulation; no physical pump is operated. Automatic mode remains disabled. Moisture values are shown without unvalidated thresholds or recommendations. The logo SVG in `frontend/public/logo.svg` is a local vector recreation of the supplied image reference because the original image file was not present among the project files.

The FastAPI app allows local Vite/preview origins by default. Set `CORS_ORIGINS` in `backend/.env` to a comma-separated list of the deployed frontend origins when hosting the UI elsewhere.

### Frontend alignment

Home separates Field Sensor readings from Weather Forecast values. History uses the existing `/weather/forecast` endpoint for upcoming forecasts; past forecast snapshots are never presented as observed weather history. Crop and Irrigation retain the existing visual system with neutral sections for features awaiting backend support. More exposes available field, device and weather information. See [the alignment report](FRONTEND_ALIGNMENT_REPORT.md) for changes, verification and remaining data gaps.

Run the frontend behavior checks from `frontend/` with `npm test`, or `.\node_modules\node\bin\node.exe tests/alignment.test.mjs` if npm is not on PATH. Test fixtures are isolated from application code.

### English and Hindi

Use **English | हिन्दी** in the navbar to change the whole interface immediately. The preference persists in localStorage; English remains the default. The existing JavaScript frontend uses i18next with separate resource files under `frontend/src/locales/`. Sensor values, API data and irrigation behavior are preserved. `npm test` runs both the behavior and localization tests. See [the Hindi support and connection review](HINDI_SUPPORT_REPORT.md) for implementation details, verification, and existing feature gaps.

### Manual irrigation Phase 1

Apply the new migration with `.\.venv\Scripts\python.exe -m alembic upgrade head` from `backend/`. Set `IRRIGATION_CONTROL_MODE=simulated` in `backend/.env` for explicit development simulation and restart the API. The default `hardware` mode remains unavailable until a real ESP32 command transport is implemented. Open Irrigation to start, stop or emergency-stop a backend session. Simulation labels remain visible in current state and event history.

See [the Phase 1 report](MANUAL_IRRIGATION_PHASE1.md) for endpoints, lifecycle, transaction strategy, measurement handling, tests, migration and remaining hardware dependencies, and [example API responses](MANUAL_IRRIGATION_EXAMPLES.json). Backend tests use a disposable PostgreSQL schema: run `.\.venv\Scripts\python.exe -m unittest discover -s tests -v` from `backend/`.

### Western UP / NWPZ agronomic profile foundation

Step 2 presents a compact Crop Overview, separate **Edit Crop Details** and **Edit Variety & Growing Conditions** actions, one lifecycle placeholder, and collapsed technical references. Variety remains an optional, compatible catalogue selection saved through the existing profile API after crop registration. See [the Step 2 crop profile and UI report](CROP_PROFILE_UI_REPORT.md) for data ownership, editing behavior, checks, limitations, and manual review steps.

Apply migration `0004` and rerun `python -m app.db.seed` to add the official Western Uttar Pradesh/NWPZ wheat catalogue. On the Crop page, choose the irrigation and sowing conditions and optionally select a compatible variety; leaving it blank stores no guessed variety. Profile resolution derives DAS from the existing sowing date and returns `stage_status: not_configured` until validated profile-specific stage timings are added. See [the Phase 2 report](AGRONOMIC_PROFILE_PHASE2.md) for the schema, catalogue, endpoints, sources, verification, and remaining scientific gaps.
