# Agronomic Profile Foundation — Phase 2

## Implemented scope

This phase adds one deliberately limited agronomic scope: Wheat in Western Uttar Pradesh (excluding Jhansi division), in the North Western Plains Zone (NWPZ). It supports irrigated early/high-fertility, irrigated timely-sown, and restricted-irrigation timely-sown production profiles. It does not infer a district, variety, growth stage, irrigation need, or pump command.

## Data model and migration

Alembic migration `0004_agronomic_profiles.py` adds:

- `agronomic_profiles`: backend-owned region, zone, production conditions, verification, and provenance.
- `crop_varieties`: normalized crop variety identity.
- `variety_profiles`: compatible variety/profile mappings and optional official metadata.
- `crop_cycles.agronomic_profile_code`: the selected profile; the existing nullable `crop_cycles.variety` and `sowing_date` remain in use.
- Profile/variety provenance columns on `crop_stage_parameters`, so future validated stage timing can remain profile-specific.

`crop_stage_parameters` remains the scientific stage store. No Western-UP timing values were invented or seeded.

## Official seed catalogue

The idempotent `app.db.seed_agronomic` seed adds these official catalogue mappings:

- NWPZ, irrigated, early sown/high fertility: DBW 370, DBW 371, DBW 372, DBW 327, DBW 332, DBW 303, DBW 187.
- NWPZ, irrigated, timely sown: DBW 222, DBW 187, HD 3226.
- NWPZ, restricted irrigation, timely sown: DBW 296.

HD 3226 also stores its documented November 5–25 sowing window, first irrigation at about 21 DAS, and later irrigation as needed. These are informational source-backed fields. They are not automatic control rules.

Sources:

- ICAR-IIWBR technology/variety information: https://iiwbr.org.in/technology-developed/
- ICAR HD 3226 description: https://icar.org.in/en/node/12081

## API and resolution behavior

- `GET /agronomic-profiles` lists profiles and supports crop, region, and zone filters.
- `GET /wheat-varieties` returns a backend-filtered catalogue by zone, sowing condition, and irrigation condition.
- `GET /crop-cycles/{crop_cycle_id}/agronomic-profile` resolves the saved selection.
- `PUT /crop-cycles/{crop_cycle_id}/agronomic-profile` validates and saves a profile plus nullable variety.

Resolution derives DAS from the crop cycle's sowing date and the Asia/Kolkata agricultural date. A missing variety is valid and returns regional specificity. A known variety must have an active mapping to the chosen production profile. Future sowing dates and incompatible crop/profile or variety/profile combinations return controlled validation errors.

Because no validated profile-specific stage timing is present, the resolver returns `current_stage: null` and `stage_status: "not_configured"`.

## Crop page

The existing Crop page now contains a responsive agronomic setup card for the existing sowing date, Western Uttar Pradesh/NWPZ region, irrigation condition, sowing condition, and an optional searchable variety list. Leaving variety blank saves `null` and displays guidance that the farmer can continue without it. The page displays provenance, derived DAS, the truthful unconfigured stage status, and the official HD 3226 notes when applicable.

## Verification

- Backend: 23 tests pass, including required cases A–E, catalogue filtering, unknown profile/crop handling, future sowing dates, migration integrity, and all Manual Irrigation Phase 1 regression tests.
- Frontend: behavior tests cover nullable and compatible varieties, invalid typed varieties, backend-filter requests, and the selection API.
- Migration `0004` was applied and the idempotent catalogue was seeded locally: 3 profiles, 10 varieties, 11 mappings.

## Remaining scientific gaps

- No validated Western-UP/NWPZ crop-stage timing has been configured.
- No full India or district resolver exists; Eastern UP and Jhansi/Bundelkhand remain outside this profile.
- No district popularity, automatic variety selection, crop recommendation, ETc, TAW, RAW, depletion, rain-delay, moisture threshold, target-volume, water-balance, or automatic irrigation logic exists.
- The HD 3226 irrigation note cannot trigger a pump. Later control logic must evaluate field water status, weather, measurements, and safety.
