# Step 2 — Crop profile, variety, and farmer-friendly UI

## A. Existing data flow and missing-variety finding

Inspection covered the Crop page, Home summary, registration/date form, profile editor, selection loading and drafts in `frontend/src/main.js`; the API client and locale catalogues; the crop-cycle and profile schemas/models/routers; the profile service and catalogue queries; and existing frontend/backend tests.

The existing ownership is:

- A crop cycle belongs to a selected field and references the crop catalogue through `crop_id`.
- The cycle's nullable `variety` string stores the selected variety code. Its `agronomic_profile_code` references the configured regional production profile.
- `CropVariety` and `VarietyProfile` supply the catalogue and compatibility relationships. The existing `/wheat-varieties` endpoint filters the supported Wheat/NWPZ catalogue by production conditions.
- `PUT /crop-cycles/{id}/agronomic-profile` validates the profile against the cycle's crop and validates the variety against the chosen profile, then persists the selection on the cycle.
- Cycle reads already include `variety`, and Home already consumed `cycle.variety`. Date edits use a separate endpoint and preserve these selection fields.

**There was no omitted Home API property to fix.** The optional selection was deferred to a separate, technical-looking form, while registration did not clearly expose that next step. A null variety produced the old generic “Variety not configured” message without a direct editing action.

At inspection time, both active cycles in the configured database already had saved varieties and profiles. The previously reported missing-value state could not be reproduced in those current records; they were not cleared or replaced. Automated tests cover both genuinely missing and configured selections.

## B. Actual files modified

- `frontend/src/main.js`: compact overview, scoped editing, optional-variety action from Home, consolidated lifecycle, revised page hierarchy, catalogue gating, safe draft handling, save synchronization, and stale-request guards.
- `frontend/src/api/client.js`: the existing profile catalogue method now accepts the selected crop name instead of always querying Wheat.
- `frontend/src/styles.css`: small overview/action/error styles using the existing theme and responsive conventions.
- `frontend/src/locales/en/translation.json` and `frontend/src/locales/hi/translation.json`: overview, editing, optional-value, registration, lifecycle, and catalogue messages.
- `frontend/tests/alignment.test.mjs`: focused Step 2 cases and updates to tests that expected the previous form/card arrangement. Fixtures use the actual supported Wheat crop name.
- `backend/app/services/agronomic_profile_service.py`: retain an omitted variety during unrelated profile edits and preserve existing stage fields instead of clearing them.
- `backend/app/routers/agronomic_profiles.py`: distinguish an omitted `variety_code` from an explicitly submitted null.
- `backend/tests/test_agronomic_profiles.py`: saved variety read-back, edit preservation, explicit clearing, compatibility rejection, and crop-specific catalogue checks.
- `README.md` and `CROP_PROFILE_UI_REPORT.md`: updated handoff documentation.

Vite regenerated `frontend/dist/`. No schema, migration, dependency, weather service, geocoding service, irrigation controller, or firmware change was made.

## C. Crop page before and after

Before, the page repeated Home's device/sensor summary, showed a large unavailable growth-stage card, placed an always-visible agronomic form prominently, repeated crop-cycle details, and displayed separate unavailable lifecycle/recommendation/next-stage cards.

The page now follows this order:

1. **Crop Overview**: saved crop, farm, field, optional variety, sowing date, existing crop age, and configured irrigation/sowing conditions. Optional missing values use localized text rather than fabricated zeroes.
2. **Crop Lifecycle**: actual cycle status and expected/actual harvest dates, followed by one explanation of the unconfigured stage-estimation feature.
3. **Environmental Conditions**: existing sensor values, units, validity handling, and timestamps; a compact soil description when available.
4. **Weather Forecast**: the existing card, including field-aware location, approximation label, timestamps, loading/error states, and refresh behavior.
5. **Advanced Agronomic / Technical Details**, collapsed by default: existing source provenance, documented variety windows/notes, soil references, and weather reference values.

The growing-condition form appears only when requested. Home's irrigation/device/activity panels are not duplicated on Crop. Existing documented variety notes remain available in advanced details.

## D. Variety selection and save flow

Registration continues to create the crop cycle first. Its existing profile API requires a persisted cycle ID, so the UI explains the supported second step rather than attempting an unvalidated variety write during registration:

`Save crop and sowing date → Crop → Edit Variety & Growing Conditions → choose conditions and optional compatible variety → Save`.

Home also has a direct **Edit Variety & Growing Conditions** action when the registered cycle has no variety. The missing-value label is **Not selected (optional)**.

The editor uses the existing production-condition options and a select control populated from the existing filtered catalogue. Nothing fabricates or guesses a variety. **I don't know / Not sure** explicitly saves null when chosen. Wheat options are never offered to another crop. The current catalogue is regional Wheat data, so its scope is explained; unsupported crops receive a clear message and can still use date editing.

The existing profile PUT validates and saves the selection. Its successful response updates the selected cycle's profile/variety fields and the Crop summary immediately; Home consumes that same saved selection. A subsequent application load reads the persisted cycle and resolved profile again. No parallel local crop database was introduced.

## E. Editing and preservation

- **Edit Crop Details** prepopulates sowing and expected harvest dates, uses the existing date-only PUT, preserves variety/profile/ownership, and returns to Crop after saving. Registration still returns to Home, preserving the first-time flow.
- **Edit Variety & Growing Conditions** prepopulates the saved selection and production conditions, uses the existing profile PUT, and closes to the updated summary on success.
- Both edit paths have clear save and cancellation/back actions. Profile Cancel discards its unsaved draft without changing saved records. Unsaved profile entries survive ordinary asynchronous rerenders and language switches; they are intentionally discarded on cancellation or field change.
- Changing conditions retains the old variety in the draft. If it becomes incompatible, the editor asks the farmer to choose a compatible replacement or explicitly choose the unknown option; it never silently clears the saved variety.
- Validation feedback appears by the variety/condition input where appropriate. Failed saves retain the draft and expose a localized error rather than internal server details.
- Catalogue errors provide retry actions. Request versions prevent earlier filter results or an old field's save response from replacing the current field's state.

The backend now distinguishes omission from removal: omitting `variety_code` retains the saved variety, while explicitly sending null removes it. A retained variety still must be compatible with a replacement profile; incompatible changes are rejected without overwriting the saved choice. Profile saves also retain existing `current_stage` and `stage_override` values. This fixes unrelated-field loss and does not calculate or display an estimated stage.

## F. Lifecycle and Step 3 boundary

The existing calendar-based crop-age calculation is unchanged. Available cycle dates and status remain visible. One lifecycle message reserves space for validated future stage, next-stage, and recommendation information. It does not invent stage names, timings, progress percentages, thresholds, or irrigation advice.

No growth-stage estimation was implemented. The current resolver continues to return unconfigured stage information, and unvalidated stored stage strings are not promoted into the farmer-facing lifecycle.

## G. Verification

Final results:

- **67 frontend tests passed**.
- **50 backend tests passed**.
- **Vite production build passed**.

Focused cases cover configured/missing overviews, section order, optional values, crop-specific options, variety save/read-back and refresh persistence, date/profile edit preservation, cancellation, drafts through rerenders, validation failures, rapid filter requests, field switches during saves, and the registration-to-profile explanation. Existing English/Hindi, onboarding, location/weather provenance, dashboard, sensor, and irrigation regressions also passed.

Commands:

```powershell
# frontend/
.\node_modules\node\bin\node.exe --test tests/*.test.mjs
.\node_modules\node\bin\node.exe node_modules/vite/bin/vite.js build

# backend/
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Node tests and Vite required their normal child-process access beyond the initial sandbox. Backend integration cases use disposable PostgreSQL schemas; no normal demonstration records were edited. Existing simulated pump-failure test logs are expected passing cases and do not operate a physical pump.

## H. Remaining limitations

- Browser inventory was empty. No manual desktop/mobile visual check or complete browser workflow was performed. Automated render/event tests and the build are not substitutes for that check.
- The supported variety catalogue remains Wheat in Western Uttar Pradesh / NWPZ. Other crops/regions are not given invented entries, and location does not automatically establish a matching agronomic region.
- Variety selection remains the supported second step after registration; it is not part of the date-only creation/edit payload. The dependency and next action are now explicit.
- Unsaved drafts do not persist across a full browser refresh. Successfully saved crop/profile data remains database-backed, and the existing selected farm/field preference is preserved.
- Existing future-sowing-date/domain validations remain in place. This step does not change agronomic rules, reference data, weather semantics, authentication/demo identity, pump control, or sensor calculations.

## I. Manual browser review

1. Start/restart FastAPI and Vite; no migration is required for Step 2.
2. Select the intended field and open Crop. Check crop, farm, field, variety, dates, age, and production conditions in the overview.
3. Open **Edit Variety & Growing Conditions**. Confirm saved values are prepopulated and only compatible options are listed. Choose a listed variety or the unknown option, then Save. Check both Crop and Home.
4. Refresh the browser and confirm the saved selection and selected farm/field persist.
5. Open **Edit Crop Details**, change a valid date, and Save. Verify the variety and growing conditions remain unchanged and the app returns to Crop.
6. Make an unsaved growing-condition change, switch language, then Cancel. Verify saved values remain unchanged. Change conditions so the current variety is incompatible and verify the explicit correction message.
7. Review the single lifecycle explanation, sensor units/timestamps, weather location/approximation/fetched timestamps, and collapsed technical details.
8. Switch fields and verify overviews and catalogue state follow the selected field. Confirm onboarding, location editing, weather refresh, and existing irrigation controls still work.
9. Repeat in Hindi and at a narrow/mobile width; check action labels, form controls, navigation, and the existing emergency control remain usable.
