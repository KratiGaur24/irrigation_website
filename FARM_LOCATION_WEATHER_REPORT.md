# Step 1.5 — Farm location and weather integration

## A. Confirmed root cause

The Step 1 setup form stored `location_name` only. It did not resolve that text to coordinates. The existing weather service required both coordinates on the selected **field** and rejected refresh without them, even if coordinates existed on its farm. The dashboard only read stored weather until Refresh was pressed and showed the same generic empty message for missing location and missing forecast.

Read-only inspection of the configured database found two farms with no coordinate pairs, two fields with one configured coordinate pair, and 504 stored weather records. Thus weather data was not universally absent: newly created fields had no usable weather location. The existing routes already associated weather with `field_id`; that relationship was retained.

## B. Files changed

Backend:

- `backend/app/services/location_service.py` — new Open-Meteo geocoding adapter and shared coordinate resolution.
- `backend/app/routers/locations.py` — new validated `GET /locations/search?q=...&language=en|hi` endpoint, restricted to India.
- `backend/app/services/weather_service.py` — resolve field/farm coordinates, save forecast coordinate provenance, distinguish an empty forecast from a provider failure.
- `backend/app/routers/weather.py` — effective-location read endpoint and current-weather filtering by field and requested coordinates.
- `backend/app/routers/farms.py` — apply only explicitly submitted edit properties.
- `backend/app/schemas.py` — validated optional coordinate pairs for farm setup/editing; weather response provenance fields.
- `backend/app/models/__init__.py` — nullable requested coordinates on weather records.
- `backend/app/main.py` — register the location router.
- `backend/alembic/versions/0005_weather_location.py` — additive provenance migration.
- `backend/tests/test_location_weather.py` — provider mocks and disposable PostgreSQL integration tests.

Frontend:

- `frontend/src/main.js` — location search, explicit result selection, advanced coordinate confirmation, weather-location states, and refresh after a confirmed location save.
- `frontend/src/api/client.js` — geocoding and effective-weather-location methods.
- `frontend/src/api/types.js`, `frontend/src/api/types.d.ts` — location/provenance response types.
- `frontend/src/styles.css` — small location form/result additions using the existing visual theme and responsive grid.
- `frontend/src/locales/en/translation.json`, `frontend/src/locales/hi/translation.json` — localized location and weather states.
- `frontend/tests/alignment.test.mjs` — location selection, persistence payloads, stale requests, editing, cached weather, localization, and onboarding regressions.

Documentation: `README.md` and this report. Vite regenerated `frontend/dist/`.

## C. Farmer experience

Farm setup and **More → Edit Farm** now contain **Farm Location (optional)**, with the placeholder **Enter village, town or district** and the example **Bareilly, Uttar Pradesh**.

1. Enter a place and press **Search locations**.
2. Review the matches, including available administrative areas and country. Nothing is automatically selected.
3. Choose the intended result. The form shows the chosen location and explains that a place-based forecast is approximate for the field.
4. Press **Save and Continue** to confirm persistence. Search and selection alone do not update the database.
5. The selected field's weather is reloaded and refreshed through the existing weather service. Farm editing retains the existing return to More; open Home to view the weather card. Initial farm/field creation still returns to Home.

The advanced section accepts known coordinates only after **Confirm these coordinates**, then the same final save. Latitude must be −90 to 90 and longitude −180 to 180; zero is valid. Manual coordinates are optional.

No matches and lookup failures have separate messages. A farmer can still save textual farm information without a resolved location. Searching without choosing a replacement preserves previously saved valid coordinates and their location name. Unrelated farm, field, crop, profile, sensor, and irrigation properties are not reset.

## D. Data flow and weather states

`Farm/field → complete valid coordinate pair → existing FastAPI weather refresh → Open-Meteo → field-bound PostgreSQL snapshots → existing Weather Forecast card`.

The backend uses one policy for reads and refreshes:

1. A valid, complete field coordinate pair takes priority.
2. Otherwise use a valid, complete pair from that field's own farm; label it approximate.
3. Otherwise report missing location. Never combine one coordinate from a field with another from its farm.

`GET /fields/{field_id}/weather/location` exposes the resolved source, label, coordinates, and approximate flag. Existing refresh/latest/forecast routes and weather units remain in use. GETs read storage; they do not call the provider. Explicit refresh and saving a chosen location can request a new forecast.

The card distinguishes missing location (with Edit Farm action), loading, stored forecast, temporary service failure, no stored snapshot for the effective location, and a provider response with no usable forecast. Stored values show forecast and fetched timestamps. Failed refresh preserves a matching cached snapshot. Null measurements remain unavailable rather than becoming fabricated zeroes. Weather remains separate from sensor measurements.

Field switches invalidate pending responses and reset weather/location state. A successful location edit reloads the selected field before refreshing. Old snapshots cannot appear under new coordinates, including when the replacement refresh fails.

## E. Database and compatibility

Existing nullable `farms.latitude/longitude`, `farms.location_name`, and `fields.latitude/longitude` were reused. Farm coordinates are not copied into fields, and no location is inferred from free text without a chosen result.

Alembic migration **0005_weather_location** adds two nullable, range-checked columns to `weather_records`: `request_latitude` and `request_longitude`. This is necessary because existing snapshots stored only the field ID and could not prove which coordinates produced them after a location edit. The migration was applied successfully to the configured database.

No legacy coordinates were fabricated. Old snapshots remain available from the weather history API, but snapshots with unknown coordinate provenance are excluded from current latest/forecast reads. **Press Refresh once to repopulate current weather after upgrading.** No tables were recreated, no owner relationships changed, and no demonstration farm, field, or crop was edited. After migration the original counts were unchanged: two farms, two fields, one configured field pair, and 504 weather rows.

## F. Verification

Final automated results:

- **56 frontend tests passed**, including the existing dashboard, crop, irrigation, onboarding, localization, and new location tests.
- **45 backend tests passed**, including 14 new location/weather tests using mocked external providers and disposable PostgreSQL schemas.
- **Vite production build passed**.
- **Alembic upgrade to 0005 passed**.

Commands:

```powershell
# frontend/
.\node_modules\node\bin\node.exe --test tests/*.test.mjs
.\node_modules\node\bin\node.exe node_modules/vite/bin/vite.js build

# backend/
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Node test/build processes needed expanded child-process access. Initial sandboxed live network calls could not connect; the same read-only probe with network access succeeded. The backend suite logs its existing simulated pump timeout/failure cases as expected; the tests pass and no physical pump is operated.

Separately from mocks, live provider probes succeeded: searching **Bareilly, Uttar Pradesh** returned three choices (Bareilly, Bareilly Jn, and Bareilly Airport), and the forecast request returned **HTTP 200**, **168 hourly timestamps**, and **Asia/Kolkata**. This was a read-only provider probe using returned coordinates, not a browser workflow or a change to a saved farm.

## G. Remaining limits

- Browser inventory was empty, so desktop/mobile visual verification and the complete saved-location browser workflow were **not performed**. Responsive styles were reused and automated event/render tests passed, but they do not replace a browser check.
- Open-Meteo uses GeoNames-based location search with administrative qualifiers and optional translated names. Coverage and naming do not establish exact farm boundaries; village availability and spelling can vary. The UI offers nearby-place search with an approximate label and optional known coordinates. These choices follow the [official geocoding API documentation](https://open-meteo.com/en/docs/geocoding-api).
- Farm fallback is approximate even when a coordinate is manually confirmed; a farm point need not be the selected field's exact position. Existing explicit field coordinates continue to take priority, and the edit form explains this. There is no new field-coordinate editing screen.
- Network outages, rate limiting, or provider availability may still prevent refresh. A valid existing cached forecast remains visible with its timestamps; a missing/new location cannot reuse another location's forecast.
- This remains the existing shared demo application without new authentication. No dependency, irrigation rule, sensor calculation, ESP32 firmware, crop growth-stage calculation, or release/GitHub operation was introduced.

## H. Manual browser checklist

1. Start/restart FastAPI and Vite. The migration has already been applied to this configured database; on another checkout run `python -m alembic upgrade head` from `backend/`.
2. Open Home and select the intended farm under More. To test farm fallback, use a field without explicit coordinates; fields with their own pair intentionally retain priority.
3. Open **More → Edit Farm**. Search **Bareilly, Uttar Pradesh**. Confirm multiple results appear and no choice is automatic.
4. Choose the intended result and press **Save and Continue**. Open Home and use weather Refresh if desired.
5. Verify the displayed location/source, approximate label, real provider values, forecast timestamp, and last-refresh timestamp.
6. Refresh the browser. Confirm location and selected farm/field persist.
7. Switch farms/fields; verify previous weather does not leak into the new selection.
8. Edit to a different confirmed location; verify old-location forecasts disappear even if refresh fails. Confirm that crop and irrigation pages still work.
9. Try an unlisted place and a failed lookup. Confirm saving the farm remains possible and existing confirmed coordinates survive an unselected search.
10. Repeat in Hindi and a narrow viewport. Check result buttons, advanced inputs, navigation, and the existing emergency control remain usable.
