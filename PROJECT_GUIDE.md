# Smart Irrigation App — Complete Project Guide

This is the single starting document for understanding, setting up, running, and extending this project.

**Project folder:** `D:\Smart_irrigation_App\project`  
**App name:** Kisan Jal  
**Documentation checked against the code:** 7 October 2026

Examples below use Windows PowerShell. Replace sample passwords and `PASTE_...` identifiers before running a command. Configuration examples contain placeholders, not the contents of your private `.env` files.

## Contents

1. [What the project currently does](#1-what-the-project-currently-does)
2. [Architecture and data flow](#2-architecture-and-data-flow)
3. [Codebase map and reading order](#3-codebase-map-and-reading-order)
4. [Software and configuration requirements](#4-software-and-configuration-requirements)
5. [First-time setup](#5-first-time-setup)
6. [Commands for normal use](#6-commands-for-normal-use)
7. [Frontend behavior and language support](#7-frontend-behavior-and-language-support)
8. [Backend and API reference](#8-backend-and-api-reference)
9. [Database and migrations](#9-database-and-migrations)
10. [Manual irrigation and safety behavior](#10-manual-irrigation-and-safety-behavior)
11. [Sensor, weather, and agronomic requirements](#11-sensor-weather-and-agronomic-requirements)
12. [API examples](#12-api-examples)
13. [Tests and verification](#13-tests-and-verification)
14. [What still needs implementation](#14-what-still-needs-implementation)
15. [How to extend the codebase](#15-how-to-extend-the-codebase)
16. [Troubleshooting](#16-troubleshooting)
17. [Build and deployment preparation](#17-build-and-deployment-preparation)
18. [Command reference and supporting documents](#18-command-reference-and-supporting-documents)

## 1. What the project currently does

The project is a field monitoring dashboard with database-backed manual irrigation sessions, stored weather forecasts, crop profile selection, and English/Hindi presentation.

The actual frontend is **plain JavaScript ES modules, Vite, and custom CSS**. The backend is **FastAPI, SQLAlchemy, Alembic, and PostgreSQL**. React, Tailwind, and Streamlit are not used in the current codebase.

| Feature | Current implementation |
| --- | --- |
| Home | Field/crop summary, sensor measurements, stored weather, recent updates, device information |
| Irrigation | Backend-confirmed manual start, stop, emergency stop, current session, closed-session history |
| Crop | Active crop cycle, Western UP/NWPZ wheat profile selection, optional compatible variety, source information |
| History | Past sensor measurements, upcoming stored weather forecasts, irrigation events |
| More | Farm/field information, device/firmware details, weather source and timestamps |
| English/Hindi | Whole-interface switching, separate translation files, saved language preference |
| Sensor ingestion | `POST /sensor-readings` accepts records for a registered `device_code` |
| Weather retrieval | Explicit refresh from Open-Meteo using field coordinates; snapshots saved in PostgreSQL |
| Pump simulation | Implemented; acknowledgements never operate a physical pump |
| Physical ESP32 pump transport | Not implemented; hardware control currently reports unavailable |
| Automatic irrigation | Disabled; no implemented decision engine or scheduler |
| Login and authorization | No implemented login UI, authentication routes, or per-user API access enforcement |
| Notifications, analytics, settings | No dedicated working pages/APIs; some supporting database tables exist |

Database tables and response fields can exist before their associated feature is implemented. Their presence does not mean automatic decisions, notifications, or water-balance calculations already run.

## 2. Architecture and data flow

```mermaid
flowchart LR
    UI[Browser: Vite JavaScript frontend] <-->|JSON HTTP API| API[FastAPI routers]
    API <--> SERVICES[Application services]
    API <--> DB[(PostgreSQL)]
    SERVICES <--> DB
    SERVICES -->|Explicit weather refresh| WEATHER[Open-Meteo]
    SERVICES --> SIM[Simulated command acknowledgement]
    DEVICE[External sensor sender] -->|POST /sensor-readings| API
    SERVICES -. Future command adapter .-> ESP[Physical ESP32 pump controller]
```

The diagram's dashed pump-control connection is future work. There is no ESP32 firmware or implemented MQTT/HTTP relay command transport in this repository.

### Dashboard reads

1. `frontend/index.html` loads `frontend/src/main.js`.
2. `boot()` requests API health, fields, and farms.
3. The selected field loads crop cycles, soil, devices, sensor readings, weather, and irrigation state through `src/api/client.js`.
4. Each section tracks `loading`, `ready`, `empty`, or `error`. A section failure does not erase successfully loaded sections.
5. The UI renders records returned by the API. It does not infer a moisture threshold or a pump decision.
6. Version counters prevent late field/history/irrigation responses from replacing the state of a newly selected field.

### Writes

- Crop setup sends a `PUT` to save the production profile and optional variety.
- Irrigation buttons send `POST` requests and wait for backend confirmation.
- Weather refresh sends a `POST`; normal dashboard `GET` requests do not fetch new provider weather.
- An external sensor sender posts measurements; the backend finds the registered device and derives its field ID.

The browser does not continuously poll sensor or pump state. Navigation, explicit refreshes, initial loading, and command completion cause reads. The one-second elapsed-time timer changes display text only.

## 3. Codebase map and reading order

```text
project/
├── PROJECT_GUIDE.md                    This complete guide
├── README.md                           Short setup overview
├── HINDI_SUPPORT_REPORT.md              Localization and connection review
├── FRONTEND_ALIGNMENT_REPORT.md         Earlier frontend alignment review
├── MANUAL_IRRIGATION_PHASE1.md          Manual control design and limitations
├── MANUAL_IRRIGATION_EXAMPLES.json      Example irrigation responses
├── AGRONOMIC_PROFILE_PHASE2.md          Regional crop profile design
├── frontend/
│   ├── package.json                     npm scripts and dependency ranges
│   ├── package-lock.json                Resolved npm dependencies
│   ├── start.cmd                        Launch using bundled Node on Windows
│   ├── vite.config.js                   Development server configuration
│   ├── index.html                       HTML entry point
│   ├── .env.example                     Public API URL configuration example
│   ├── public/logo.svg                  Static logo asset
│   ├── src/
│   │   ├── main.js                      App state, pages, events, API orchestration
│   │   ├── styles.css                   Visual design and responsive layouts
│   │   ├── icons.js                     SVG icon rendering
│   │   ├── data.js                      Presentation filtering/sorting/date helpers
│   │   ├── irrigation.js                Elapsed duration and control labels
│   │   ├── i18n.js                      Language initialization and label helpers
│   │   ├── locales/en/translation.json  English text resources
│   │   ├── locales/hi/translation.json  Hindi text resources
│   │   └── api/
│   │       ├── client.js                Shared API request functions
│   │       ├── types.js                 JSDoc data definitions
│   │       └── types.d.ts               TypeScript interface declarations
│   ├── tests/alignment.test.mjs         UI behavior and localization integration tests
│   ├── tests/i18n.test.mjs              Language/resource/storage tests
│   ├── node_modules/                   Installed dependencies; generated
│   └── dist/                           Production build; generated
└── backend/
    ├── requirements.txt                Python dependency ranges
    ├── .env.example                     Backend configuration example
    ├── alembic.ini                      Migration configuration
    ├── alembic/env.py                   Settings and SQLAlchemy metadata wiring
    ├── alembic/versions/                Four ordered schema migrations
    ├── app/
    │   ├── main.py                      FastAPI application, router registration, CORS
    │   ├── config.py                    Environment settings
    │   ├── database.py                  Engine, base model, session factory
    │   ├── dependencies.py              Request-scoped database sessions
    │   ├── models/__init__.py           SQLAlchemy tables and relationships
    │   ├── schemas.py                   General API payload/response validation
    │   ├── schemas_irrigation.py        Control/session/emergency response models
    │   ├── schemas_agronomic.py         Crop profile selection/resolution models
    │   ├── routers/                     Farm, field, crop, device, soil, sensor,
    │   │                                weather, irrigation, agronomic endpoints
    │   ├── services/
    │   │   ├── device_control_service.py      Command transport boundary and simulation
    │   │   ├── irrigation_control_service.py Session lifecycle, locks, measurements
    │   │   ├── weather_service.py            Provider fetch/validation/persistence
    │   │   └── agronomic_profile_service.py  Profile compatibility and resolution
    │   └── db/
    │       ├── seed.py                  Minimal linked demo records + catalogue
    │       └── seed_agronomic.py        Regional catalogue only
    ├── tests/test_manual_irrigation.py  PostgreSQL/manual control integration tests
    ├── tests/test_agronomic_profiles.py PostgreSQL/crop profile integration tests
    ├── tests/test_frontend_connection.py CORS preflight checks
    └── .venv/                          Local Python environment; generated
```

### Suggested reading order

1. Read this guide's feature status and setup sections.
2. Read `backend/app/main.py`, `config.py`, and `database.py` to understand application initialization.
3. Read `models/__init__.py` alongside `schemas.py` to understand persisted data versus request/response data.
4. Read a router and its service together, starting with irrigation or weather.
5. Read `frontend/src/api/client.js`, then `main.js` to follow browser interactions.
6. Read `data.js`, `irrigation.js`, and `i18n.js` for presentation behavior.
7. Read the tests before changing session handling, concurrency, compatibility, or localization.

The frontend is JavaScript with JSDoc/interface references. It has no separate TypeScript compilation/typecheck script. Most page rendering is currently in `main.js`, rather than separate component files.

## 4. Software and configuration requirements

### Required software

| Requirement | Purpose / project detail |
| --- | --- |
| Windows PowerShell | Commands in this guide; other systems need equivalent paths |
| Python | The README targets Python 3.11+ for new setup; the existing environment was verified on Python 3.10.8 |
| PostgreSQL server | Required database; SQLite is not a supported substitute for these migrations/tests |
| PostgreSQL client or pgAdmin | Create the database and inspect records |
| Node.js and npm | Install frontend dependencies; use Node 22.12+ to match the pinned Node 22 runtime family |
| Web browser | Open and visually test the frontend |
| Internet access | Initial dependency installation and explicit weather refresh |

`frontend/package.json` pins a project-local Node runtime to `22.23.3`. You still need an existing npm installation to install dependencies the first time. After installation, `start.cmd` can launch the app without Node/npm on PATH.

The installed Vite package declares Node compatibility as `^20.19.0 || >=22.12.0`; the project-local Node 22 runtime satisfies it. The frontend uses JSON import attributes and ES modules.

You do not need Redis, Docker, an MQTT broker, or an attached ESP32 for the existing simulated app. Those services are not configured in the current repository.

### Python dependencies

`backend/requirements.txt` contains:

| Package | Declared range | Role |
| --- | --- | --- |
| FastAPI | `>=0.115,<1` | API routes, validation integration, API documentation |
| Uvicorn | `>=0.30,<1`, standard extras | Development/application server |
| SQLAlchemy | `>=2.0,<3` | PostgreSQL models and queries |
| Alembic | `>=1.13,<2` | Schema migrations |
| psycopg | `>=3.2,<4`, binary extras | PostgreSQL driver |
| Pydantic | `>=2.8,<3` | Payload/response validation |
| pydantic-settings | `>=2.4,<3` | Environment configuration |
| httpx | `>=0.27,<1` | Weather HTTP requests and test support |

Python dependencies use version ranges; there is no Python dependency lockfile. npm has `package-lock.json`; use `npm ci` when reproducing the checked-in frontend dependency resolution.

### Environment variables

| Variable | Where | Required/default | Purpose |
| --- | --- | --- | --- |
| `DATABASE_URL` | `backend/.env` or environment | Required | `postgresql+psycopg://...` SQLAlchemy connection URL |
| `IRRIGATION_CONTROL_MODE` | Backend | Defaults to `hardware` if omitted | Set `simulated` for existing local development |
| `CORS_ORIGINS` | Backend | Four local origins shown below | Comma-separated browser origins allowed to access API |
| `DEMO_USER_PASSWORD` | Shell environment while seeding | Required by `app.db.seed` | Password used to create the demo user's hash |
| `DEMO_USER_EMAIL` | Shell environment while seeding | Defaults to `demo@example.test` | Demo seed user identity |
| `VITE_API_BASE_URL` | `frontend/.env` | Client has fallbacks | Public backend URL used by the browser |

Backend example:

```dotenv
DATABASE_URL=postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/smart_irrigation_db
IRRIGATION_CONTROL_MODE=simulated
CORS_ORIGINS=http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:5500,http://localhost:5500
```

Frontend example:

```dotenv
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Keep the database password in the backend configuration. `VITE_*` values are exposed to the browser and must not contain database credentials or private secrets. Password characters reserved in URLs must be percent-encoded in `DATABASE_URL`.

Backend `.env` is resolved relative to the working directory. Run backend commands from `backend/`. Restart the API after changing backend configuration; restart Vite after changing frontend environment settings. Build again if a production frontend API URL changes.

The API URL client precedence is: `VITE_API_BASE_URL`, then `window.APP_CONFIG.apiBaseUrl`, then `http://<browser-hostname>:8000`. The code supports the `APP_CONFIG` fallback, but the current HTML does not populate it.

## 5. First-time setup

Follow these steps on a fresh machine. If `.venv`, `.env`, and database records already exist, use [normal run commands](#6-commands-for-normal-use) instead of recreating them.

### Step 1 — Check tools

```powershell
Set-Location 'D:\Smart_irrigation_App\project'
py --list
node --version
npm --version
psql --version
```

`psql` can be replaced with pgAdmin's Query Tool if it is not on PATH. Use your installed Python version if the launcher cannot find 3.11; the project's existing Python 3.10 environment passed its current tests.

### Step 2 — Create the Python environment and install packages

```powershell
Set-Location 'D:\Smart_irrigation_App\project\backend'
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

You can optionally activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

All commands in this guide use the environment's executable explicitly, so activation is not required. This also avoids PowerShell activation-policy problems.

### Step 3 — Create configuration files without overwriting existing ones

```powershell
Set-Location 'D:\Smart_irrigation_App\project\backend'
if (-not (Test-Path -LiteralPath '.env')) {
    Copy-Item -LiteralPath '.env.example' -Destination '.env'
}
notepad .env
```

Set the actual database URL and keep `IRRIGATION_CONTROL_MODE=simulated` for the current implementation.

```powershell
Set-Location 'D:\Smart_irrigation_App\project\frontend'
if (-not (Test-Path -LiteralPath '.env')) {
    Copy-Item -LiteralPath '.env.example' -Destination '.env'
}
notepad .env
```

### Step 4 — Create the PostgreSQL database

Start the PostgreSQL service. For a new database, run this once:

```powershell
psql -h localhost -U postgres -c "CREATE DATABASE smart_irrigation_db;"
```

Or execute this SQL in pgAdmin while connected to an existing administration database:

```sql
CREATE DATABASE smart_irrigation_db;
```

Use the role, host, port, database name, and password that match `DATABASE_URL`. An existing database does not need to be recreated.

### Step 5 — Apply all migrations

```powershell
Set-Location 'D:\Smart_irrigation_App\project\backend'
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
```

The current head is `0004_agronomic_profiles`. Starting the API does not automatically create or migrate tables.

### Step 6 — Seed the demo records

```powershell
Set-Location 'D:\Smart_irrigation_App\project\backend'
$env:DEMO_USER_PASSWORD = 'REPLACE_WITH_A_LOCAL_DEMO_PASSWORD'
.\.venv\Scripts\python.exe -m app.db.seed
Remove-Item Env:DEMO_USER_PASSWORD
```

This creates missing linked demo entities: user, farm, field, Wheat crop, active crop cycle, and `ESP32-DEMO-001` device. It also seeds the regional catalogue: three profiles, ten varieties, and eleven compatibility mappings.

The seed is idempotent for its intended demo identities and catalogue keys. It preserves existing rows; it does not reset an existing demo user's password or overwrite farmer crop selections. A newly created crop cycle uses the seed machine's current date as its sowing date. The demo device starts with status `not_configured`.

The seed does **not** add field coordinates, sensor measurements, weather, soil measurements, sensor calibrations, stage timing, water-balance results, or irrigation rules. Empty states after seeding are therefore expected.

To add only the catalogue to an existing database:

```powershell
.\.venv\Scripts\python.exe -m app.db.seed_agronomic
```

The demo password hash is not a working login feature; no login flow has been implemented.

### Step 7 — Install frontend packages

```powershell
Set-Location 'D:\Smart_irrigation_App\project\frontend'
npm ci
```

Use `npm install` when intentionally adding/updating dependencies and commit the matching lockfile. Dependencies install into `frontend/node_modules/`, including the bundled Node executable. The frontend does not use a Python virtual environment.

### Step 8 — Start the two services

Run the backend and frontend in separate terminals using the next section.

## 6. Commands for normal use

### Terminal 1 — Backend

```powershell
Set-Location 'D:\Smart_irrigation_App\project\backend'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Terminal 2 — Frontend

```powershell
Set-Location 'D:\Smart_irrigation_App\project\frontend'
.\start.cmd
```

Alternative if npm is on PATH:

```powershell
npm run dev
```

Both launch the same frontend. Do not start both simultaneously unless you deliberately want two servers.

| URL | Purpose |
| --- | --- |
| `http://127.0.0.1:5173` | Farmer dashboard; use the actual URL printed by Vite |
| `http://127.0.0.1:8000/health` | API process health response |
| `http://127.0.0.1:8000/docs` | Swagger UI with request/response schemas and Try it out |
| `http://127.0.0.1:8000/redoc` | Alternative API documentation |
| `http://127.0.0.1:8000/openapi.json` | Machine-readable API contract |

Check the backend:

```powershell
Invoke-RestMethod 'http://127.0.0.1:8000/health'
Invoke-RestMethod 'http://127.0.0.1:8000/fields'
```

`/health` returns `{"status":"ok"}` without querying PostgreSQL. Also request `/fields` or `/farms` to verify actual database connectivity. Stop each server with **Ctrl+C** in its terminal. PostgreSQL is a separate service.

## 7. Frontend behavior and language support

### Files and responsibilities

| File | Main responsibilities |
| --- | --- |
| `main.js` | State objects, page HTML, event delegation, command guards, async section loading |
| `api/client.js` | GET/POST/PUT requests, URL configuration, encoded identifiers, HTTP error status |
| `data.js` | Sensor history ordering, upcoming forecast filtering/deduplication, calendar crop age, device availability labels |
| `irrigation.js` | Elapsed duration from backend timestamps and localized duration/control labels |
| `i18n.js` | Resource loading, validated preferences, language changes, metadata and message/enum labels |
| `styles.css` | Cards, navigation, responsive rules, Devanagari fonts and longer-label wrapping |
| `icons.js` | Local SVG icons |

Home requests up to five recent sensor records; History requests up to fifty. Future sensor records are filtered out by presentation helpers. An invalid latest reading is visibly marked; the dashboard does not silently substitute an older valid reading as if it were latest.

Forecast presentation uses the newest stored snapshot for each forecast time and shows upcoming times first. Stored past forecasts are labelled as predictions, not actual observed weather.

### English/Hindi implementation

- The navbar displays **English | हिन्दी**.
- English is the default; the saved choice is stored under `kisan-jal.language` in localStorage.
- Only `en` and `hi` are accepted. Invalid or blocked storage falls back safely.
- Language switching rerenders the interface without reloading or sending data/pump requests.
- Translation keys live in separate JSON resources, grouped by navigation, dashboard, weather, crop, irrigation, history, farm, common text, known values, and messages.
- Sensor values, IDs, crop/variety names, database records, and API payload keys remain unchanged.
- Dates use the browser's local timezone. Hindi keeps Latin numeric digits and uses 24-hour time.
- Displayed command notices store their outcome data and translate on render, so an existing warning changes language too.
- Unsaved crop conditions and variety text survive a language change.
- HTML helpers escape translated/interpolated output before insertion. Use the existing escaping conventions when adding new UI.

For new visible text, add the same key and interpolation parameters to both JSON files. Use `t('group.key')` for text values or the existing `h()` helper for escaped HTML text. Do not put Hindi/English language ternaries directly into page templates.

`messageLabel()` currently maps recognized English backend messages to resource keys. If a backend message changes, update this map's resource entries. Unknown technical error details produce a localized fallback; unknown ordinary data values remain unchanged.

## 8. Backend and API reference

`app/main.py` registers the routers and CORS middleware. `dependencies.py` supplies a request-scoped SQLAlchemy session. Schemas validate inputs; routers perform existence checks and call services or database queries.

CORS permits `GET`, `POST`, `PUT`, and `OPTIONS` for configured origins, with `Accept` and `Content-Type` headers. Adding `PUT` fixed browser crop-profile saves. Cookies/credentialed CORS are not enabled.

The current routes have no authentication dependency. CORS is a browser-origin policy, not access control. Before exposing farmer records or pump commands beyond a local development setup, implement the access protections described in the roadmap.

### General records

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Process health; no DB check |
| GET | `/crops` | Crop catalogue |
| GET / POST | `/farms` | List / create farm |
| GET | `/farms/{farm_id}` | One farm |
| GET | `/farms/{farm_id}/fields` | Farm's fields |
| GET / POST | `/fields` | List / create field, including optional coordinates |
| GET | `/fields/{field_id}` | One field |
| GET / POST | `/crop-cycles` | List / create crop cycle |
| GET | `/crop-cycles/{crop_cycle_id}` | One crop cycle |
| GET | `/fields/{field_id}/crop-cycles` | Field crop cycles |
| GET / POST | `/soil-profiles` | List / create soil profile |
| GET | `/soil-profiles/{soil_profile_id}` | One soil profile |
| GET | `/fields/{field_id}/soil-profiles` | Field soil profiles |
| GET / POST | `/devices` | List / register device |
| GET | `/devices/{device_id}` | One device |
| GET | `/devices/code/{device_code}` | Device lookup by sender code |
| GET | `/fields/{field_id}/devices` | Field devices |

There is no general `PATCH`/`PUT` for fields/devices/crop cycles and no record-deletion API. The crop profile selection has its own specific `PUT` route.

### Sensor measurements

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/sensor-readings` | Ingest measurements for a registered `device_code` |
| GET | `/sensor-readings` | Optional field/device and time filters |
| GET | `/devices/{device_id}/sensor-readings` | Device readings |
| GET | `/fields/{field_id}/sensor-readings` | Field readings |

Read endpoints accept `from`, `to`, and `limit`; the general endpoint also accepts `device_id` and `field_id`. Default limit is 100, maximum 1000. Results are newest first. Send ISO timestamps with an explicit timezone, for example `2026-10-07T08:00:00Z`.

### Weather

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/fields/{field_id}/weather/refresh` | Fetch provider data and save snapshots |
| GET | `/fields/{field_id}/weather/latest` | Stored forecast near current time, or earliest available fallback |
| GET | `/fields/{field_id}/weather/forecast` | Upcoming forecasts; default 168, maximum 500 |
| GET | `/fields/{field_id}/weather/history` | Stored snapshots; `from`, `to`, `limit`, default 100, maximum 500 |

`weather/history` exists in the API, but its records are forecast snapshots. The frontend uses `weather/forecast` rather than treating stored forecasts as observed weather history.

### Manual irrigation

All routes below use `/fields/{field_id}/irrigation` as their prefix.

| Method | Suffix | Purpose |
| --- | --- | --- |
| GET | `/control` | Mode, controller availability, start availability and explanation |
| POST | `/start` | Create acknowledged manual session; success HTTP 201 |
| POST | `/stop` | Complete an active session when off is acknowledged |
| POST | `/emergency-stop` | Independent off request; inspect `acknowledged` |
| GET | `/active` | Open session, including unresolved failures, or JSON null |
| GET | `/history` | Closed sessions; newest first, default 50, maximum 200 |

Irrigation history supports `from` and `to` as inclusive boundaries on session **start time**, and requires timezone-aware filter values. An emergency response can be HTTP 200 with `acknowledged=false`; HTTP success alone is not pump-off confirmation.

### Agronomic profiles

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/agronomic-profiles` | Active profiles; filters `crop`, `region`, `zone` |
| GET | `/wheat-varieties` | Compatible varieties; filters `zone`, `sowing_condition`, `irrigation_condition` |
| GET | `/crop-cycles/{crop_cycle_id}/agronomic-profile` | Resolve saved selection, DAS and optional variety metadata |
| PUT | `/crop-cycles/{crop_cycle_id}/agronomic-profile` | Validate and save `{profile_code, variety_code}` |

`variety_code` can be `null`. An unconfigured crop profile returns HTTP 409; the UI handles it as a setup state. Use `/docs` for the exact current payload fields and response schemas.

### Common response meanings

| Code | Typical meaning in this app |
| --- | --- |
| 200 | Read/processed operation; emergency acknowledgement still needs inspection |
| 201 | Created record or started session |
| 404 | Missing referenced record or unknown device code |
| 409 | Existing session, incompatible profile/variety, unconfigured profile, or database conflict |
| 422 | Invalid payload, timestamp range, coordinates, or query limit |
| 502 | Provider/command acknowledgement problem |
| 503 | Unavailable transport, timeout, or persistence failure |

## 9. Database and migrations

### Entity relationships

The main ownership chain is `users → farms → fields`. Fields have devices, crop cycles, soil profiles, sensor readings, weather records, and irrigation events. Crop cycles reference the crop catalogue and optionally a regional agronomic profile. Variety compatibility is stored separately from farmer selections.

| Table | Role / implementation status |
| --- | --- |
| `users` | Farmer identity/password hashes; authentication flow still missing |
| `farms` | Farm owner and general location |
| `fields` | Field area, irrigation method, optional field coordinates |
| `crops` | Crop catalogue |
| `crop_cycles` | Sowing/harvest dates, status, selected regional profile/variety |
| `crop_stage_parameters` | Scientific stage parameters; validated regional timing not configured |
| `soil_profiles` | Measured/reference soil characteristics and provenance |
| `devices` | Registered device code, field link, status and last report time |
| `sensor_calibrations` | Calibration records; no complete calibration workflow/API |
| `sensor_readings` | Append-only sensor observations |
| `weather_records` | Forecast snapshots and provider provenance |
| `water_balance_records` | Water-balance storage foundation; no active calculation service |
| `rule_configurations` | Operational rule storage foundation; no automatic rule engine |
| `irrigation_events` | Manual session lifecycle, command provenance and measurements |
| `notifications` | Notification storage foundation; no working notifications API/UI |
| `agronomic_profiles` | Region/zone/production conditions and source information |
| `crop_varieties` | Named variety catalogue |
| `variety_profiles` | Variety-to-production-profile compatibility and official notes |

Domain entity identifiers generally use PostgreSQL UUIDs. Sensor/weather/water-balance histories use identity BIGINT keys. Agronomic profile and variety catalogues use string codes; `variety_profiles` uses a composite key.

Foreign keys generally use `ON DELETE RESTRICT`; relationship definitions avoid cascading deletion of history. Check the model and migration before changing ownership or deleting referenced records. Nullable scientific inputs remain null rather than being filled with invented defaults.

### Migration order

| Revision | Changes |
| --- | --- |
| `0001_database_v2` | Initial domain, observations, scientific/reference and operational tables |
| `0002_add_field_location` | Field latitude/longitude and location metadata |
| `0003_manual_irrigation` | Command provenance, baseline sensor reference, one-open-session-per-field index |
| `0004_agronomic_profiles` | Regional/variety catalogue, compatibility, crop profile references |

Migration `0003` adds a partial unique index for irrigation events where `ended_at IS NULL`. Existing duplicate open sessions can prevent applying it; they require explicit review rather than automatic history deletion.

### Database commands

From `backend/`:

```powershell
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic history
.\.venv\Scripts\python.exe -m alembic upgrade head
```

With `psql`, connect to the project database:

```powershell
psql -h localhost -U postgres -d smart_irrigation_db
```

Then inspect:

```sql
\dt
\d+ fields
\d+ sensor_readings
\d+ irrigation_events
SELECT * FROM alembic_version;
SELECT field_id, field_name, latitude, longitude FROM fields;
SELECT code, region, sowing_condition, irrigation_condition FROM agronomic_profiles;
```

`\dt` and `\d+` are psql commands, not SQL for pgAdmin. In pgAdmin use its object browser and the SQL `SELECT` statements.

## 10. Manual irrigation and safety behavior

### Controller selection

The service expects exactly one field device with type `irrigation_controller` or `pump_controller`. In simulation only, if there is one device and no typed controller, that device can be used as the development controller. Multiple ambiguous candidates are rejected.

Simulation relaxes device-online/last-seen checks and labels the result accordingly. Hardware mode is currently unavailable because no physical command adapter exists. Do not use an environment switch as evidence that ESP32 integration has been implemented.

### Session state

| Outcome | Stored status | Session remains open? |
| --- | --- | --- |
| Acknowledged start | `started`, mode `MANUAL` | Yes |
| Acknowledged normal stop | `completed` | No |
| Acknowledged emergency stop | `stopped` | No |
| Definitively rejected start | `failed`, `START_REJECTED` | No |
| Uncertain start/stop/emergency outcome | `failed`, corresponding fault code | Yes, allowing off retry and blocking another start |

An open failed event describes uncertainty. It is not proof that a pump is running or stopped. Simulation cannot close a hardware/legacy session under a different control path.

The backend locks the field row while changing session state. A start is validated and its event flushed before sending the command. An unconfirmed command remains retryable. If saving fails after a start was attempted, the service attempts compensating emergency-off and returns a failure requiring controller-state review.

The frontend prevents repeated normal clicks, waits for backend confirmation, and refreshes state after commands. Emergency stop can be requested while a normal command is pending; off is sent immediately and repeated once the pending command settles.

### Measurement rules

- Moisture before uses a valid non-future reading.
- Moisture after requires a reading recorded after session start.
- Missing measurements remain null and do not prevent stopping.
- Flow values come from actual stored sensor records.
- Water volume uses a starting cumulative-meter reference and a later valid reading from the same device.
- Counter resets, decreases, missing baselines, or invalid continuity produce unknown volume.
- No water volume is invented from elapsed time multiplied by an assumed flow rate.
- Final duration is persisted from backend start/end timestamps; browser elapsed time is presentation only.

Physical-device commands cannot be committed atomically with a database transaction. Future hardware work needs bounded timeouts, command IDs, duplicate protection, durable reconciliation, and device fail-safe behavior before physical operation.

## 11. Sensor, weather, and agronomic requirements

### Sensor integration

The backend can ingest measurements, but the firmware/network sender is external work. To connect a device:

1. Register it under the correct field with a unique `device_code`.
2. Configure the sender with the reachable backend URL and that code.
3. Send measurements to `POST /sensor-readings` using the schema and units below.
4. Send timezone-aware observation timestamps and meaningful `sensor_valid` values.
5. Implement measured sensor calibration and device authentication before relying on unattended operation.

| Payload field | Meaning / unit |
| --- | --- |
| `device_code` | Required registered sender identifier |
| `raw_adc` | Optional nonnegative raw moisture ADC value |
| `soil_moisture_pct` | 0–100 percent |
| `temperature_c` | Degrees Celsius |
| `humidity_pct` | 0–100 percent |
| `flow_rate_lpm` | Nonnegative litres/minute |
| `flow_pulse_count` | Optional nonnegative pulse count |
| `cumulative_water_litres` | Optional nonnegative measured meter total |
| `sensor_valid` | Boolean; schema defaults to true |
| `recorded_at` | Observation timestamp; defaults to server UTC now if omitted |

Extra sensor payload fields are forbidden. The API derives `device_id` and `field_id`; do not send arbitrary ownership IDs in a sensor payload. Ingestion updates `last_seen_at`, but does not automatically change `device.status` to online and does not convert `raw_adc` into a calibrated percentage.

### Weather requirements

Weather uses **field** latitude/longitude, not farm coordinates. There is no automatic copying or location inference. Creating a field supports coordinates; an existing field currently has no general edit endpoint or farmer location-edit form. Adding a validated edit workflow is future work.

The refresh service requests Open-Meteo hourly/daily series, validates the payload, interprets its IANA timezone, converts timestamps to UTC, and saves a snapshot. Its HTTP timeout is 12 seconds, with a 5-second connection timeout. The current request has no API-key configuration.

Forecast precipitation is stored in `forecast_rainfall_mm`; `actual_rainfall_mm` is left null. Hourly shortwave radiation is converted from mean W/m² to MJ/m² for that hour using `value × 3600 / 1,000,000`. ET0 is provider forecast data; there is no implemented ETc/water-balance service.

Keep `source="open-meteo"` and the frontend attribution. A successful old snapshot does not guarantee a current forecast; request an explicit refresh when needed.

### Agronomic scope

The seeded catalogue covers **Wheat, Western Uttar Pradesh / NWPZ**. Its stated scope excludes Jhansi division; it is not a full India/district crop resolver.

| Profile code | Production conditions |
| --- | --- |
| `wheat-western-up-nwpz-irrigated-timely` | Irrigated, timely sown |
| `wheat-western-up-nwpz-irrigated-early-high-fertility` | Irrigated, early sown, high fertility |
| `wheat-western-up-nwpz-restricted-timely` | Restricted irrigation, timely sown |

The seed contains ten varieties and eleven compatibility mappings. DBW 187 appears in more than one profile. Source URLs/provenance are stored with the catalogue. HD 3226 includes documented sowing-window and first-irrigation notes, which are informational metadata, not pump instructions.

The profile resolver uses the selected profile's agricultural timezone (`Asia/Kolkata` for these seeds) to derive days after sowing. Missing variety is valid. Incompatible profile/variety choices and future sowing dates produce controlled errors. No validated profile-specific stage timing has been configured, so `current_stage` stays null and `stage_status` is `not_configured`.

## 12. API examples

These commands are examples to run against your local app, not commands already executed while writing this guide. Creation/ingestion/control commands change records. Sensor numbers below are artificial demo samples; replace them with real measurements for actual device data.

### Identify records

```powershell
$apiBase = 'http://127.0.0.1:8000'
Invoke-RestMethod "$apiBase/fields" | Format-Table field_id, field_name, farm_id
$fieldId = 'PASTE_FIELD_UUID'
Invoke-RestMethod "$apiBase/fields/$fieldId/crop-cycles"
Invoke-RestMethod "$apiBase/fields/$fieldId/devices"
```

### Submit a demo sensor reading after seeding

```powershell
$sensorBody = @{
    device_code = 'ESP32-DEMO-001'
    soil_moisture_pct = 32.0
    temperature_c = 28.0
    humidity_pct = 60.0
    flow_rate_lpm = 0.0
    sensor_valid = $true
    recorded_at = (Get-Date).ToUniversalTime().ToString('o')
} | ConvertTo-Json
Invoke-RestMethod "$apiBase/sensor-readings" -Method Post -ContentType 'application/json' -Body $sensorBody
```

### Read sensor and weather data

```powershell
Invoke-RestMethod "$apiBase/fields/$fieldId/sensor-readings?limit=5"
Invoke-RestMethod "$apiBase/fields/$fieldId/weather/latest"
Invoke-RestMethod "$apiBase/fields/$fieldId/weather/forecast?limit=168"
```

Refresh only after field coordinates are configured:

```powershell
Invoke-RestMethod "$apiBase/fields/$fieldId/weather/refresh" -Method Post
```

### Save a crop profile without guessing the variety

```powershell
$cycleId = 'PASTE_CROP_CYCLE_UUID'
$profileBody = @{
    profile_code = 'wheat-western-up-nwpz-irrigated-timely'
    variety_code = $null
} | ConvertTo-Json
Invoke-RestMethod "$apiBase/crop-cycles/$cycleId/agronomic-profile" -Method Put -ContentType 'application/json' -Body $profileBody
```

The Crop page provides this workflow too; its list is filtered by production conditions.

### Try simulated manual control

First verify the mode rather than assuming it:

```powershell
$controlState = Invoke-RestMethod "$apiBase/fields/$fieldId/irrigation/control"
if ($controlState.control_mode -ne 'simulated') {
    throw 'This example requires simulated control mode.'
}
if (-not $controlState.start_available) {
    throw $controlState.message
}
Invoke-RestMethod "$apiBase/fields/$fieldId/irrigation/start" -Method Post
Invoke-RestMethod "$apiBase/fields/$fieldId/irrigation/active"
Invoke-RestMethod "$apiBase/fields/$fieldId/irrigation/stop" -Method Post
Invoke-RestMethod "$apiBase/fields/$fieldId/irrigation/history?limit=50"
```

For a separate emergency attempt:

```powershell
$emergencyResult = Invoke-RestMethod "$apiBase/fields/$fieldId/irrigation/emergency-stop" -Method Post
$emergencyResult
if (-not $emergencyResult.acknowledged) {
    Write-Warning 'Pump-off was not confirmed; inspect the returned state and retry as appropriate.'
}
```

## 13. Tests and verification

### Frontend tests

From `frontend/`:

```powershell
npm test
npm run build
```

If npm is not on PATH but dependencies exist:

```powershell
.\node_modules\node\bin\node.exe tests/alignment.test.mjs
.\node_modules\node\bin\node.exe tests/i18n.test.mjs
.\node_modules\node\bin\node.exe node_modules/vite/bin/vite.js build
```

These frontend tests use Node's test runner and mocked API/render harnesses; they do not require a running backend or browser. Coverage includes independent section failures, stale responses, field switching, forecast labeling, invalid latest readings, command confirmation/repeated-click handling, emergency races, crop selection, and English/Hindi behavior.

### Backend tests

From `backend/`:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

PostgreSQL must be running and `DATABASE_URL` valid. The test role needs permission to create/drop test schemas. Tests create uniquely named disposable schemas, execute the actual migrations there, and clean up afterwards. Pump tests use simulated/test adapters and do not operate hardware.

### Most recent verified results

| Check | Result from the localization/connection review |
| --- | --- |
| Frontend tests | 37 passed: 32 behavior/integration tests + 5 i18n tests |
| Backend tests | 25 passed: 15 manual irrigation + 8 agronomic + 2 CORS tests |
| Production frontend build | Passed |
| npm vulnerability report after compatible dependency update | Zero reported vulnerabilities at that check |
| Live frontend API client against local backend | All existing pages rendered with stored data; expected HTTP 409 for an unsaved agronomic selection |
| Desktop/mobile visual browser verification | Pending; no browser was available in that session |

These are recorded results, not a guarantee that a later dependency install or code change passes. The current guide does not replace rerunning checks after implementation work.

At that review, the selected field had no active soil profile, no saved agronomic profile selection, and no upcoming stored forecast. These were data/setup states rather than missing route connections.

### Manual acceptance checks

1. Open all five pages and check loading, empty, ready, and API-error states.
2. Switch English → Hindi → English on each page, then refresh to check preference persistence.
3. Check narrow mobile and desktop widths for clipped text, Devanagari rendering, menus, controls, and table scrolling.
4. Enter an unsaved crop variety, switch language, and verify it remains.
5. Verify manual simulation start/stop/history, repeated clicks, and emergency failure messages.
6. Stop the API temporarily and verify unavailable sections do not claim fresh data or confirmed control.

## 14. What still needs implementation

The following are implementation requirements, not features already delivered.

| Work area | Required implementation | Main code area |
| --- | --- | --- |
| Login/permissions | Login/session or token flow, password verification, owner/role access checks on reads and commands, device credentials | New auth routes/dependencies; `users`, frontend |
| Field/device management | Edit forms/endpoints, validated location updates, reliable device registration/status workflow | `routers/fields.py`, `devices.py`, schemas, frontend |
| Sensor firmware/calibration | ESP32 sender, payload protocol, measured calibration, validity rules, clock/error handling | External firmware; sensor ingestion and calibration models |
| Physical pump adapter | Choose transport, authenticate devices, bounded acknowledgements, command IDs/deduplication, durable reconciliation | `device_control_service.py`, irrigation service, firmware |
| Hardware safety | Tested relay/pump behavior, independent stop/fail-safe, verified flow handling, device outage/restart behavior | Firmware, hardware adapter, integration tests |
| Crop stages | Source-backed region/profile timings and validated stage resolution | `crop_stage_parameters`, agronomic service |
| Water balance | Validated soil inputs, root depth/crop coefficients, ETc, available water/depletion calculations and persisted snapshots | New service; soil/stage/water-balance models |
| Automatic decisions | Documented rules for moisture/water status, rain handling, safety, explanation codes and manual override | New decision service; `rule_configurations` |
| Automatic execution | Scheduler/worker, locking/deduplication, command lifecycle integration and audit history | New orchestration; irrigation service |
| Notifications | Event generation, API, read/acknowledgement state, localized UI | `notifications` plus new routes/services/page |
| Analytics | Aggregation APIs and charts using measured water/session data with clear missing-value handling | New queries/services/frontend page |
| Settings | Persisted farmer preferences/configuration, validation, permissions and UI | New schema/API/page as needed |
| Production operations | Dependency reproducibility, deployment configuration, HTTPS, backups, monitoring and end-to-end checks | Environment/build/deployment tooling |

Suggested order: complete measured field/sensor setup and access control, validate physical manual control independently, establish scientific inputs/stage logic, then add automatic decision/execution behavior. Build notifications/analytics/settings around those explicit backend contracts. Keep automatic control disabled until its inputs and safety behavior are validated.

Do not infer a universal moisture threshold from the current dashboard or turn the HD 3226 informational note into an automatic pump schedule.

## 15. How to extend the codebase

### Add a backend capability

1. Define the request/response contract in the appropriate schema module.
2. Implement business behavior in a service; keep transport behavior behind its adapter.
3. Add routes and register a new router in `app/main.py` if needed.
4. Use `get_db` and explicit transaction/error handling. Preserve null measurements and historical provenance.
5. For schema changes, update SQLAlchemy models and add an Alembic revision.
6. Review generated SQL, foreign keys, constraints, existing-row backfills, and upgrade/downgrade behavior before applying it.
7. Add behavior tests, including failure/concurrency cases for pump commands.

To generate a new migration from `backend/`:

```powershell
.\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "describe_the_schema_change"
```

This creates a draft migration; generation does not prove the migration is correct. Do not edit old applied revisions to represent new changes.

### Connect the frontend

1. Add a method in `src/api/client.js` rather than scattering direct fetch calls across page renderers.
2. Update `types.js` and `types.d.ts` for new fields/contracts.
3. Add state/loading/error/empty handling and guard responses against field changes.
4. Add page rendering/events using the existing visual/escaping conventions.
5. Add all visible text to both language files, including validation, tooltips, confirmations, and empty states.
6. Preserve unsaved form state across asynchronous renders.
7. Test the actual HTTP method and CORS preflight for cross-origin writes.

For substantial future growth, page rendering/state can be split from `main.js` into modules without requiring a framework conversion. A React migration would be a separate architectural change.

### Preserve current behavior

Maintain backend authority for command outcomes. Do not optimistically show pump-on/off confirmation. Keep sensor observations separate from weather predictions, source metadata separate from operational rules, and translated labels separate from database/API codes.

## 16. Troubleshooting

| Symptom | Likely cause / next action |
| --- | --- |
| `python`/`npm` command missing | Use the explicit `.venv`/bundled Node paths; initial frontend install still requires npm |
| PowerShell cannot activate `.venv` | Use `.\.venv\Scripts\python.exe` directly; activation is optional |
| `ModuleNotFoundError: app` or missing `.env` settings | Run the command from `backend/`, using its Python environment |
| Missing `database_url` validation error | Create/edit `backend/.env`; set `DATABASE_URL` |
| PostgreSQL connection/authentication failure | Check service, host/port/database/role, password, and URL encoding |
| `/health` works but field reads fail | Health does not query the DB; inspect database connectivity and migrations |
| Missing relation/column | Apply `alembic upgrade head` against the intended database |
| Migration fails on duplicate open irrigation events | Review those events and controller state explicitly; migration preserves history |
| Seed refuses to run | Set `DEMO_USER_PASSWORD` in the shell; catalogue-only seed does not need it |
| No field shown | Verify `/fields`; apply migrations/seed or create a field |
| Sensor data empty | Seed creates a device but no readings; send registered-device measurements |
| Device last-seen updates but status stays `not_configured` | Ingestion updates the timestamp, not status; status management still needs implementation |
| Manual Start disabled | Inspect `/irrigation/control` and `/active`; check mode, controller ambiguity, errors or an open event |
| Hardware start returns unavailable | Actual ESP32 command transport is not implemented |
| Pump-off unconfirmed | Inspect acknowledgement and active event; do not treat HTTP 200 alone as confirmation |
| Weather refresh returns 422 | Set valid coordinates on the field; farm location does not substitute for them |
| Weather provider fails | Check internet/provider response; stored forecasts remain available when loaded |
| No upcoming weather forecast | Old snapshots may exist; use explicit refresh after coordinates/network are configured |
| Crop profile returns 409 | It can be unconfigured, incompatible, or have a future sowing date; select/save an appropriate profile |
| Crop stage remains unconfigured | Expected until validated stage timing is implemented |
| Browser CORS error | Match exact scheme/host/port in `CORS_ORIGINS`; restart API; `localhost` and `127.0.0.1` are distinct origins |
| Vite chooses 5174 instead of 5173 | Port 5173 is busy; stop the other instance or add the actual origin to CORS |
| `npm run preview` cannot load API data | Preview commonly uses 4173; add that origin to backend CORS before using it |
| Changed frontend API URL is ignored | Restart Vite, or rebuild `dist` for production |
| Language does not survive refresh | Browser storage may be blocked or the origin changed; preferences are per origin |
| Hindi text looks clipped | Check mobile widths/fonts/wrapping; actual visual browser checks remain pending |
| `ZoneInfoNotFoundError` on Windows | Install `tzdata` into the backend environment, then retry profile/weather operations |
| Backend integration tests cannot create schemas | Use a local/test PostgreSQL role with schema creation permission |
| Vite/Node `spawn EPERM` under an agent sandbox | The process sandbox may block child helpers; run the command in an allowed terminal/context |

If Windows timezone data is missing:

```powershell
Set-Location 'D:\Smart_irrigation_App\project\backend'
.\.venv\Scripts\python.exe -m pip install tzdata
```

`tzdata` is not explicitly listed in the current `requirements.txt`; add it to the project's dependency declaration if your supported setup requires it.

## 17. Build and deployment preparation

Build the frontend:

```powershell
Set-Location 'D:\Smart_irrigation_App\project\frontend'
npm run build
```

The output is `frontend/dist/`. Serve that output with your chosen static hosting/web server. Source files and `node_modules` are not the production site artifact.

For a **local build preview**, first include the preview origin in the backend's configuration:

```dotenv
CORS_ORIGINS=http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:5500,http://localhost:5500,http://127.0.0.1:4173,http://localhost:4173
```

Restart the API, then run:

```powershell
npm run preview -- --port 4173
```

Or with the bundled executable:

```powershell
.\node_modules\node\bin\node.exe node_modules/vite/bin/vite.js preview --host 127.0.0.1 --port 4173
```

Vite preview is a build-check server, not the production deployment plan.

For deployment, choose a database and application hosting environment, apply migrations there, configure an externally reachable API URL before building the frontend, and set exact frontend origins in backend CORS. The browser must be able to reach that URL; `127.0.0.1` on a remote user's computer is not your deployed server.

The repository currently has no Docker Compose stack, production hosting configuration, background scheduler, or complete authentication layer. Deployment readiness requires these operational decisions plus access control, HTTPS, secret management, backups, monitoring, and end-to-end tests. Continue to label simulated pump operation clearly. Development `--reload` is not a production process-management strategy.

## 18. Command reference and supporting documents

### Commands by working directory

| Directory | Command | Purpose |
| --- | --- | --- |
| `backend/` | `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` | Install Python packages |
| `backend/` | `.\.venv\Scripts\python.exe -m alembic upgrade head` | Apply migrations |
| `backend/` | `.\.venv\Scripts\python.exe -m alembic current` | Show installed revision |
| `backend/` | `.\.venv\Scripts\python.exe -m app.db.seed` | Seed demo + catalogue; password environment variable required |
| `backend/` | `.\.venv\Scripts\python.exe -m app.db.seed_agronomic` | Seed catalogue only |
| `backend/` | `..\.venv\Scripts\python.exe -m app.db.seed_agronomic` | Start local API |
| `backend/` | `.\.venv\Scripts\python.exe -m unittest discover -s tests -v` | Run backend tests |
| `frontend/` | `npm ci` | Install locked dependencies |
| `frontend/` | `.\start.cmd` | Start frontend with bundled Node |
| `frontend/` | `npm run dev` | Start frontend through npm |
| `frontend/` | `npm test` | Run all frontend tests |
| `frontend/` | `npm run build` | Build production assets |
| `frontend/` | `npm run preview -- --port 4173` | Preview build after configuring CORS |
| `frontend/` | `npm audit` | Check current dependency advisories; requires registry access |

### Supporting documents

This guide contains the setup and codebase information needed to get started. These existing files provide historical implementation detail:

- [README.md](README.md): original short setup instructions.
- [MANUAL_IRRIGATION_PHASE1.md](MANUAL_IRRIGATION_PHASE1.md): session transactions, acknowledgement handling, measurement details and hardware boundaries.
- [MANUAL_IRRIGATION_EXAMPLES.json](MANUAL_IRRIGATION_EXAMPLES.json): representative irrigation API responses.
- [AGRONOMIC_PROFILE_PHASE2.md](AGRONOMIC_PROFILE_PHASE2.md): regional scope, catalogue sources and scientific gaps.
- [FRONTEND_ALIGNMENT_REPORT.md](FRONTEND_ALIGNMENT_REPORT.md): earlier frontend/data alignment work.
- [HINDI_SUPPORT_REPORT.md](HINDI_SUPPORT_REPORT.md): localization changes and latest connection review.

Treat the current code, migrations, and `/openapi.json` as the exact contract. Earlier reports describe their own implementation stage and may contain older test counts or past local-runtime observations. Update this guide when adding routes, configuration variables, migrations, pages, or hardware/automatic control.
