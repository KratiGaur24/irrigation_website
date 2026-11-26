# Manual Irrigation Control Phase 1

Manual session control is implemented and connected to the existing frontend. The local development configuration explicitly uses **simulation**: commands never operate a physical pump. Automatic irrigation, agronomic decisions, water-balance calculations, thresholds and scheduling were not implemented.

## Open the app

The running backend has been checked and reports simulation mode with control available for the existing field. The migration has been applied locally. Open `http://127.0.0.1:5173` and select **Irrigation**. Start Manual Irrigation creates a simulated backend session; Stop completes it; Emergency Stop records an emergency closure. All such sessions are visibly identified as simulations, including in History.

If restarting the services:

```powershell
cd D:\Smart_irrigation_App\project\backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

In a second terminal:

```powershell
cd D:\Smart_irrigation_App\project\frontend
.\start.cmd
```

`IRRIGATION_CONTROL_MODE=simulated` is explicitly set in local `backend/.env` and documented in `.env.example`. Restart the backend after changing this setting. The application default when omitted is `hardware`, which currently reports unavailable and rejects starts because no ESP32 command transport exists.

## Endpoints

All routes are under `/fields/{field_id}/irrigation` and use existing field UUIDs resolved through the API.

| Method | Path | Result |
| --- | --- | --- |
| GET | `/control` | Mode, controller identity/status/last-seen, availability and explanation |
| POST | `/start` | 201, new acknowledged MANUAL session; 409 if already open; 503 if control unavailable |
| POST | `/stop` | Acknowledged normal closure (`completed`); 409 if no session; 502 if off unconfirmed |
| POST | `/emergency-stop` | Structured safety result with `acknowledged`, mode, message and nullable session |
| GET | `/active` | Open session, including an unresolved failed command, or JSON null |
| GET | `/history` | Closed events, newest first; default 50, maximum 200 |

History supports `from` and `to` as inclusive **start-time** boundaries with timezone-aware timestamps. Invalid limits/ranges return 422. An emergency request reports HTTP 200 for a processed attempt even if `acknowledged=false`; the frontend explicitly checks that boolean and does not treat it as confirmed pump-off. Missing fields/controllers still return controlled client errors.

POST start/stop errors include a clear `detail` message. After an uncertain command, callers should reload `/active`, not infer success from local UI state.

## Service abstraction and device selection

`DeviceControl` exposes `start_pump`, `stop_pump` and independent `emergency_stop` commands. Command responses have acknowledgement, control-mode provenance, explanatory message and a definitive-rejection indicator. Logs explicitly label simulated commands. No MQTT, relay pin logic or device network address was invented.

Controllers are identified by `device_type` of `irrigation_controller` or `pump_controller`. Exactly one candidate must exist. In simulation only, a field with exactly one existing device can use that device as its development controller. Ambiguous multi-device selection is rejected instead of selecting an arbitrary UUID.

Simulation relaxes online/last-seen checks and says so in the availability response/UI. The prepared hardware path requires an available status and a reported last-seen time; no universal stale timeout was introduced. Stops do not depend on online status or sensor availability.

## Lifecycle and safety behavior

| Outcome | Persisted status | Open? |
| --- | --- | --- |
| Acknowledged manual start | `started` | Yes |
| Acknowledged normal stop | `completed` | No |
| Acknowledged emergency stop | `stopped`, reason `manual emergency stop` | No |
| Definitively rejected start | `failed`, `START_REJECTED` | No |
| Uncertain start, stop or emergency acknowledgement | `failed` with corresponding fault | Yes, until off is acknowledged |

All starts use `mode=MANUAL`; no automatic path exists. A failed **open** event is not a claim that the pump is running or off. It reserves the field, blocks another start and allows stop/emergency retry. Repeated emergency requests never start a pump or create another event. An emergency request without an event still attempts the independent off command.

Emergency requests are serialized with starts through the field lock to avoid an off/start race. The frontend can submit an emergency request during a pending normal request; it sends off immediately and repeats off once that request settles. The emergency result is shown globally, including when initiated from the header on Home.

A simulation acknowledgement cannot close a hardware or legacy event. Changing configuration while a session is open produces an explicit mismatch until its original control path is restored. Historical rows retain their original mode label after configuration changes.

## Transaction and failure strategy

1. Lock the PostgreSQL field row and verify there is no open session.
2. Validate the controller, capture available real sensor baseline values and flush the event before sending start. Constraint failures therefore occur before the command.
3. Issue the command through the abstraction; persist the acknowledgement and resulting event state in the same transaction.
4. A definitive rejection closes a failed event. An ambiguous acknowledgement leaves an open failed event for retry.
5. If persistence fails after any start command was attempted, roll back and attempt emergency-off, log its acknowledgement, and return 503 directing the caller to verify controller state.
6. Stop/emergency send off before optional sensor reads. Successful closure records end time and duration. If persistence fails, roll back and return an explicit unconfirmed-save response; the previously open event remains available for retry.

A database transaction cannot atomically commit a physical-device command. A process crash or a database outage together with an unacknowledged compensating off cannot be conclusively reconciled by this Phase 1 service. Hardware is deliberately unavailable: a future hardware adapter needs bounded command timeouts, command identity/deduplication and durable reconciliation for that failure window before physical use. No claim of verified physical pump safety is made by simulation.

## Measurements

- Before moisture uses the latest valid, non-future field reading with moisture.
- After moisture uses a valid reading recorded **after session start**; an old pre-session reading is not relabelled as an after reading. Missing values remain null and do not prevent stop.
- Flow comes from actual controller sensor records and includes a measurement timestamp. There is no assumed pump-flow rate or “flow normal” conclusion.
- A stored reference to the valid starting cumulative-meter reading allows water volume to survive API restarts. A later valid reading from the same device is required. Water used is the measured counter difference, rounded to the existing column precision.
- Missing baseline/later measurements, invalid counter continuity, decreases/resets or out-of-range values result in null volume. No volume is calculated from elapsed time or assumed flow.
- Counter difference covers the displayed measurement interval, not a guarantee of complete pump-on/off coverage. No arbitrary freshness limit or exclusive-use assumption was introduced; the active UI exposes baseline/latest meter timestamps when a difference is available.
- Active duration is calculated for the response/display only. Final duration is persisted from start/end timestamps. The browser's one-second timer updates only elapsed text; it sends no commands and runs no irrigation rules.

## Frontend wiring

The existing brand, navigation, cards, palette and page structure are reused. Start is enabled only when the backend reports control available and confirms no open event. Start/Stop show pending state and prevent repeated normal commands. Neither action changes the displayed session optimistically. A 409 triggers a backend-state reload.

After commands, active state, availability, irrigation history and sensor readings are refreshed independently. Stale responses cannot overwrite another selected field. Backend failures are visibly distinct from an empty session. Page navigation and the Irrigation refresh icon reload session state; cross-client changes are not polled in the background.

The Irrigation page shows manual mode, start time, elapsed duration, real measurements, acknowledgement failures, manual farmer/operator explanation, safety/flow information and the previous closed event. Automatic is visible but disabled. No targets, progress percentages or agronomic reasons are shown.

Home contains only a compact irrigation status and a link to the Irrigation page. Header Emergency Stop remains available when there is a configured control path, an open session or a pending command. History uses actual closed events and retains simulation labels.

## Schema change

New migration: `0003_manual_irrigation`, following `0002_add_field_location`. Old migrations were not edited. It adds:

- `control_mode`: durable simulation/hardware provenance; null for legacy events.
- `start_reading_id`: restrictive reference to the cumulative-meter baseline.
- `command_acknowledged`: latest command acknowledgement state.
- Control-mode check constraint and a unique partial index on field for rows with no end time.

These are needed to avoid relabelling simulation history, losing the meter baseline across restarts, hiding uncertain commands, or admitting duplicate open events through another database writer. The existing event table, modes, statuses and measurement columns are reused. If another installation has duplicate open rows, migration fails for explicit review instead of deleting or rewriting history.

## Files created/modified

Backend:

- New: `app/services/device_control_service.py`, `app/services/irrigation_control_service.py`, `app/routers/irrigation.py`, `app/schemas_irrigation.py`, `alembic/versions/0003_manual_irrigation.py`, `tests/test_manual_irrigation.py`.
- Modified: `app/main.py`, `app/config.py`, `app/models/__init__.py`, `.env.example`; local ignored `.env` explicitly enables development simulation.

Frontend:

- New: `src/irrigation.js` for elapsed-time/mode presentation.
- Modified: `src/main.js`, `src/styles.css`, `src/api/client.js`, `src/api/types.js`, `src/api/types.d.ts`, `tests/alignment.test.mjs`.

Documentation: this report, `MANUAL_IRRIGATION_EXAMPLES.json`, and `README.md`.

## Tests and example responses

- **15 backend integration tests passed** against real PostgreSQL in a disposable unique schema, including all three migrations, lifecycle, timestamps/moisture, no-data behavior, measured volume and resets, repeated emergency stop, command failures, configuration mismatch, range/limit validation, concurrent start locking, uniqueness and rollback/compensating off.
- **22 frontend tests passed**, including the existing data-alignment checks and manual lifecycle, duplicate clicks, delayed confirmations, 409 recovery, emergency acknowledgement failure, emergency during pending start, field-switch races, elapsed display and HTTP methods/routes.
- Production Vite build and Python compilation passed.
- The running local API reports simulated control available; both local API and frontend server respond. Lifecycle tests/examples used isolated test tables and did not add demonstration irrigation events to the farmer's history.
- Browser discovery returned no available browser. Visual interaction/responsiveness and actual browser-console verification remain unverified; automated UI tests exercise rendered markup and event handlers.

Run backend tests from `backend` with `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`. Run frontend tests from `frontend` with `.\node_modules\node\bin\node.exe tests/alignment.test.mjs` (or `npm test`).

[Full example start, stop and history responses](MANUAL_IRRIGATION_EXAMPLES.json) were captured from real API calls in the isolated simulation test schema. The example has no sensor fixtures, so moisture/volume remain null. The immediate stop may have a legitimately measured duration of zero seconds; no demonstration duration was invented.

## Remaining hardware dependency

There is no ESP32 pump command endpoint, relay driver or acknowledgement transport in the repository. Implementing and validating that adapter and its failure recovery is required before physical operation. Existing APIs also have no account authorization boundary; this Phase 1 change follows the existing local-development API architecture and does not introduce a production control/authentication system.

Work stops at manual Phase 1. No automatic decision engine, maximum runtime, minimum flow, auto-stop target, notifications, crop-stage logic or water-balance calculations were added.
