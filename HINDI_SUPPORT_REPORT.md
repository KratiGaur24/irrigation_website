# Hindi support and connection review

The existing Vite/JavaScript frontend now uses i18next to switch between English and Hindi across all five screens. The actual project does not use React, Tailwind, or Streamlit; its current structure and visual design have been retained.

## Implementation

- `frontend/src/i18n.js` initializes bundled English/Hindi resources, defaults to English, validates saved preferences, and stores the selection under `kisan-jal.language` in localStorage. Switching still works if storage is blocked.
- `frontend/src/locales/en/translation.json` and `frontend/src/locales/hi/translation.json` hold the translations. Components use keys and interpolation instead of embedded Hindi.
- The navbar provides **English | हिन्दी**, with keyboard focus and the selected language exposed through `aria-pressed`.
- Switching updates the current screen, navigation, document language/title/description, dates, durations, tooltips, empty/error states, controller explanations, crop notes, and confirmations without reloading or issuing API calls.
- Already displayed command outcomes retain their original codes/data and are translated when rendered. Unsaved variety input and crop conditions survive language changes and asynchronous renders.
- Sensor readings, measurements, API payloads, record identifiers, crop/variety names, source organizations, and unknown API values remain intact. Known status/condition labels are localized for display only. Unknown error details use a localized fallback instead of exposing internal information.
- Hindi uses Latin numeric digits. Dates retain the browser's local timezone; Hindi time uses a 24-hour clock.
- Flexible navigation, controls, headings, and cards accommodate longer labels. Hindi uses available Devanagari system fonts, with no additional font download required.

## Connection fixes

The existing crop profile form sends `PUT`, but FastAPI's CORS middleware previously permitted only `GET`, `POST`, and `OPTIONS`. Added `PUT` to the permitted methods and verified the browser preflight. Endpoint definitions and payloads are unchanged.

Updated the compatible development dependency resolution for `source-map-js` to address the advisory reported by npm. The final installation reported zero vulnerabilities.

No irrigation decision rules, sensor calculations, pump lifecycle logic, ESP32 transport, database schemas, records, or migrations were changed.

## Verification

- **37 frontend tests passed:** the original 26 checks plus 11 localization checks. Coverage includes both switching directions across every existing screen, preference persistence through new app initialization, blocked/invalid storage, translated metadata, resource parity/interpolation, unchanged numeric values/data, no requests on language selection, unsaved crop input, pending commands, existing emergency warnings, populated session history/faults, and agronomic notes.
- **25 backend integration tests passed:** 23 existing tests plus CORS checks. PostgreSQL tests create isolated disposable schemas and use simulated control; no physical pump is operated.
- **Production build passed:** `npm run build` / the project-local Vite executable.
- **Live connection smoke check passed:** the real frontend API client loaded the configured backend and rendered every existing screen in Hindi. Health, farms, fields, crop cycles, soil profiles, devices, sensor readings, stored weather, irrigation availability/session/history, agronomic catalogue, and varieties returned HTTP 200. The selected crop's unsaved agronomic profile correctly returned HTTP 409 and rendered as unconfigured.

Commands from `frontend/`:

```powershell
npm test
npm run build
```

If npm is absent from PATH, run the two test files with the bundled runtime:

```powershell
.\node_modules\node\bin\node.exe tests/alignment.test.mjs
.\node_modules\node\bin\node.exe tests/i18n.test.mjs
.\node_modules\node\bin\node.exe node_modules/vite/bin/vite.js build
```

Backend checks, from `backend/`:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Existing limitations and pending visual verification

The configured field currently has no active soil profile, no saved agronomic profile selection, and no upcoming stored weather forecast. Those states are handled and translated. Weather retrieval remains an explicit refresh operation; the connection review did not trigger a provider refresh.

Automatic irrigation decisions and real ESP32 pump command transport remain unimplemented. Current manual control uses simulation. Localization does not enable these features or claim a physical pump has stopped without acknowledgement.

The repository has no login/authentication UI, dedicated notifications, analytics, or settings pages to translate. Existing updates, warnings, and configuration forms are covered.

The Browser skill found no available browser in this session. Actual desktop/mobile rendering, overflow, Devanagari appearance, and browser refresh behavior therefore remain **visually unverified**. Automated render and persistence checks passed, and responsive CSS was updated, but those checks do not replace visual browser testing.
