import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';
import { sensorHistory, upcomingForecasts, cropAge, deviceAvailable } from '../src/data.js';
import { elapsedSeconds, durationLabel, controlLabel } from '../src/irrigation.js';
import { i18n, t, locale, changeLanguage, valueLabel, messageLabel } from '../src/i18n.js';
import en from '../src/locales/en/translation.json' with { type: 'json' };
import hi from '../src/locales/hi/translation.json' with { type: 'json' };

const now = Date.now();
const iso = offset => new Date(now + offset).toISOString();
const latest = { recorded_at: iso(-1000), sensor_valid: true, soil_moisture_pct: '37.5', temperature_c: '28.2', humidity_pct: '62', flow_rate_lpm: '0' };
const forecast = { forecast_time: iso(3600000), fetched_at: iso(-60000), temperature_c: '24.1', rain_probability_pct: '70', forecast_rainfall_mm: '3.2', humidity_pct: '75', eto_mm: '0.2', source: 'open-meteo' };
const fields = [{ field_id: 'field-a', farm_id: 'farm-a', field_name: 'Test field A' }, { field_id: 'field-b', farm_id: 'farm-b', field_name: 'Test field B' }];
const source = (await readFile(new URL('../src/main.js', import.meta.url), 'utf8'))
  .replace(/^import .*;\r?\n/gm, '')
  .replace(/boot\(\);\s*$/, 'globalThis.app = { state, boot, render, loadFieldData, loadHistory, loadIrrigation, saveAgronomic, loadVarieties, loadAgronomic, refreshWeather };');

function harness(overrides = {}, storage = new Map()) {
  const listeners = {};
  const root = { innerHTML: '', addEventListener: (event, callback) => { listeners[event] = callback; } };
  const calls = [];
  const api = {
    health: async () => ({ status: 'ok' }), fields: async () => fields, farms: async () => [],
    field: async id => fields.find(item => item.field_id === id),
    cropCycles: async () => [{ crop_cycle_id: 'cycle-a', status: 'active', crop: { crop_name: 'Wheat' }, sowing_date: '2026-01-01', current_stage: 'Unvalidated stage' }],
    soilProfiles: async () => [], devices: async () => [{ device_name: 'Test device', status: 'inactive' }],
    sensorReadings: async () => [latest], weatherLatest: async () => forecast,
    weatherLocation: async id => ({ status: 'configured', label: fields.find(item => item.field_id === id)?.field_name || 'Test field A', latitude: 28, longitude: 79, source: 'field', approximate: false }),
    sensorHistory: async () => [latest], weatherForecast: async () => [forecast], refreshWeather: async () => { calls.push('refresh'); },
    irrigationControl: async () => ({ control_mode: 'hardware', available: false, start_available: false, message: 'Pump control not configured.' }),
    irrigationActive: async () => null, irrigationHistory: async () => [],
    agronomicProfiles: async () => [{ code: 'timely', crop: 'Wheat', country: 'India', state: 'Uttar Pradesh', region: 'Western Uttar Pradesh', zone_code: 'NWPZ', zone_name: 'North Western Plains Zone', sowing_condition: 'timely', irrigation_condition: 'irrigated', verification_status: 'official_verified', source_organization: 'ICAR-IIWBR', source_url: 'https://iiwbr.org.in/' }],
    agronomicProfile: async () => { throw Object.assign(new Error('Agronomic profile is not configured'), { status: 409 }); },
    wheatVarieties: async () => [{ code: 'HD 3226', display_name: 'HD 3226', sowing_condition: 'timely', irrigation_condition: 'irrigated' }],
    updateAgronomicProfile: async () => { throw new Error('Not configured in this fixture'); },
    ...overrides,
  };
  const context = vm.createContext({ localStorage: { getItem: key => storage.get(key), setItem: (key, value) => storage.set(key, value) }, document: { querySelector: () => root }, api, icon: () => '', sensorHistory, upcomingForecasts, cropAge, deviceAvailable, elapsedSeconds, durationLabel, controlLabel, i18n, t, locale, changeLanguage, valueLabel, messageLabel, Date, console });
  vm.runInContext(source, context);
  return { app: context.app, root, calls, change: target => listeners.change({ target }), input: target => listeners.input({ target }), click: dataset => listeners.click({ target: { closest: () => ({ dataset }) }, preventDefault() {} }) };
}

test('forecast rows are upcoming, nearest first and newest snapshot per time', () => {
  const result = upcomingForecasts([{ ...forecast, forecast_time: iso(-3600000) }, { ...forecast, forecast_time: iso(7200000) }, { ...forecast, fetched_at: iso(-120000) }, forecast], now);
  assert.equal(result.length, 2);
  assert.equal(result[0], forecast);
  assert.ok(Date.parse(result[0].forecast_time) < Date.parse(result[1].forecast_time));
});

test('sensor history excludes future readings and sorts newest first', () => {
  const older = { ...latest, recorded_at: iso(-50000) };
  assert.deepEqual(sensorHistory([older, { ...latest, recorded_at: iso(100000) }, latest], now), [latest, older]);
});

test('crop age uses calendar dates; statuses do not match inactive/disconnected', () => {
  assert.equal(cropAge('2026-09-26', new Date(2026, 8, 27, 0, 1)), 1);
  assert.equal(cropAge('2026-09-28', new Date(2026, 8, 27)), null);
  assert.equal(cropAge(null), null);
  assert.equal(deviceAvailable('inactive'), false);
  assert.equal(deviceAvailable('disconnected'), false);
  assert.equal(deviceAvailable('online'), true);
});

test('all pages retain neutral controls and distinguish forecasts from sensor readings', async () => {
  const { app, root, calls } = harness();
  await app.boot();
  assert.match(root.innerHTML, /37.5/);
  assert.match(root.innerHTML, /24.1°C/);
  assert.match(root.innerHTML, /Weather Forecast/);
  assert.match(root.innerHTML, /Forecast rainfall/);
  assert.doesNotMatch(root.innerHTML, /led-green/);
  for (const page of ['home', 'crop', 'irrigation', 'history', 'more']) {
    app.state.page = page;
    if (page === 'history') await app.loadHistory();
    app.render();
    assert.doesNotMatch(root.innerHTML, /Unvalidated stage|No rain expected|Weather History|raw_adc/);
    const buttons = root.innerHTML.match(/<button\b[^>]*>[\s\S]*?<\/button>/g) || [];
    for (const button of buttons.filter(item => /Start Manual Irrigation|Stop Irrigation|Emergency|Automatic|>Manual</.test(item))) assert.match(button, /disabled/);
  }
  assert.equal(calls.length, 0, 'Read-only navigation must not refresh weather');
});

test('invalid latest reading does not silently substitute an older valid reading', async () => {
  const { app, root } = harness({ sensorReadings: async () => [{ ...latest, sensor_valid: false }, { ...latest, recorded_at: iso(-60000), soil_moisture_pct: '99.9' }] });
  await app.boot();
  assert.match(root.innerHTML, /Latest reading invalid/);
  assert.doesNotMatch(root.innerHTML, /99.9/);
});

test('weather and sensor endpoint errors are isolated from crop data and each other', async () => {
  for (const endpoint of ['weatherLatest', 'sensorReadings']) {
    const { app, root } = harness({ [endpoint]: async () => { throw new Error('internal database UUID must not be exposed'); } });
    await app.boot();
    assert.match(root.innerHTML, /Wheat/);
    assert.match(root.innerHTML, endpoint === 'weatherLatest' ? /37.5/ : /24.1°C/);
    assert.doesNotMatch(root.innerHTML, /internal database UUID/);
  }
});

test('no field produces empty history rather than an endless loading state', async () => {
  const { app, root } = harness({ fields: async () => [] });
  await app.boot(); app.state.page = 'history'; await app.loadHistory();
  assert.match(root.innerHTML, /No sensor reading available/);
  assert.match(root.innerHTML, /No upcoming weather forecast available/);
  assert.doesNotMatch(root.innerHTML, /Loading sensor history/);
});

test('late field responses cannot overwrite the newly selected field', async () => {
  let resolveOld;
  const old = new Promise(resolve => { resolveOld = resolve; });
  const { app } = harness({ sensorReadings: id => id === 'field-a' ? old : Promise.resolve([{ ...latest, soil_moisture_pct: 22 }]) });
  const first = app.loadFieldData('field-a');
  await app.loadFieldData('field-b');
  resolveOld([{ ...latest, soil_moisture_pct: 88 }]); await first;
  assert.equal(app.state.activeFieldId, 'field-b');
  assert.equal(app.state.sensors.data[0].soil_moisture_pct, 22);
});

test('history sections render independently while one request is pending', async () => {
  let resolveForecast;
  const delayed = new Promise(resolve => { resolveForecast = resolve; });
  const { app, root } = harness({ weatherForecast: () => delayed });
  await app.boot(); app.state.page = 'history';
  const loading = app.loadHistory();
  await new Promise(resolve => setImmediate(resolve));
  assert.match(root.innerHTML, /37.5/);
  assert.match(root.innerHTML, /Loading weather forecast/);
  resolveForecast([forecast]); await loading;
});

test('failed weather refresh preserves stored data with an explicit error', async () => {
  const { app, root, click } = harness({ refreshWeather: async () => { throw new Error('offline'); } });
  await app.boot(); await click({ action: 'refresh-weather' });
  assert.match(root.innerHTML, /Weather refresh failed\. Any stored forecast below is unchanged/);
  assert.match(root.innerHTML, /24.1°C/);
  assert.equal(app.state.weatherRefreshing, false);
});

test('past forecasts stay labelled predictions, and never appear in upcoming rows', async () => {
  const past = { ...forecast, forecast_time: iso(-3600000) };
  const { app, root } = harness({ weatherLatest: async () => past, weatherForecast: async () => [past] });
  await app.boot(); assert.match(root.innerHTML, /Past forecast · Not observed weather/);
  app.state.page = 'history'; await app.loadHistory();
  assert.match(root.innerHTML, /No upcoming weather forecast available/);
});

test('late weather refresh and history responses stay with their original field', async () => {
  let finishRefresh, finishHistory;
  const delayedRefresh = new Promise(resolve => { finishRefresh = resolve; });
  const delayedHistory = new Promise(resolve => { finishHistory = resolve; });
  const { app, click } = harness({
    refreshWeather: () => delayedRefresh,
    weatherLatest: async id => ({ ...forecast, temperature_c: id === 'field-a' ? 99 : 21 }),
    weatherForecast: id => id === 'field-a' ? delayedHistory : Promise.resolve([{ ...forecast, temperature_c: 21 }]),
  });
  await app.boot();
  const refreshing = click({ action: 'refresh-weather' });
  app.state.page = 'history'; const loading = app.loadHistory();
  await app.loadFieldData('field-b');
  finishRefresh(); finishHistory([{ ...forecast, temperature_c: 99 }]);
  await Promise.all([refreshing, loading]);
  assert.equal(app.state.weather.data.temperature_c, 21);
  assert.equal(app.state.history.forecast.data[0].temperature_c, 21);
});

test('missing readings and profiles remain empty across Crop, Irrigation and More', async () => {
  const { app, root } = harness({ sensorReadings: async () => [], cropCycles: async () => [], devices: async () => [], weatherLatest: async () => null });
  await app.boot();
  app.state.page = 'crop'; app.render();
  assert.match(root.innerHTML, /No active crop cycle configured/);
  assert.match(root.innerHTML, /No soil profile configured/);
  assert.doesNotMatch(root.innerHTML, /Growth-stage estimation is not yet configured/);
  assert.match(root.innerHTML, /Weather data unavailable/);
  app.state.page = 'irrigation'; app.render();
  assert.match(root.innerHTML, /No active irrigation session/);
  assert.match(root.innerHTML, /No irrigation history available yet/);
  app.state.page = 'more'; app.render();
  assert.match(root.innerHTML, /No field device is configured/);
});

test('API client requests forecasts and bounds sensor reads without provider refresh', async () => {
  const clientSource = (await readFile(new URL('../src/api/client.js', import.meta.url), 'utf8'))
    .replace('import.meta.env?.VITE_API_BASE_URL', 'undefined').replace(/^export /gm, '');
  const urls = [];
  const context = vm.createContext({ window: { location: { hostname: '127.0.0.1' } }, fetch: async (url, options) => { urls.push([url, options]); return { ok: true, json: async () => [] }; }, Date });
  vm.runInContext(`${clientSource}\nglobalThis.client = api;`, context);
  await context.client.weatherForecast('field-a'); await context.client.sensorHistory('field-a');
  assert.match(urls[0][0], /\/weather\/forecast\?limit=168$/);
  assert.match(urls[1][0], /sensor-readings\?limit=50&to=/);
  assert.ok(urls.every(([url]) => !url.includes('/refresh') && !url.includes('/weather/history')));
});

const sessionFixture = () => ({ event_id: 'test-session', field_id: 'field-a', status: 'started', mode: 'MANUAL', control_mode: 'simulated', command_acknowledged: true, started_at: iso(-65000), ended_at: null, current_flow_rate_lpm: null, current_water_used_litres: null, current_moisture_pct: '37.5' });
const controlFixture = active => ({ available: true, start_available: !active, control_mode: 'simulated', message: 'Simulation only. No physical pump is controlled.' });

test('manual start waits for backend confirmation and repeated clicks issue only one request', async () => {
  let session = null, finishStart, starts = 0;
  const startResponse = new Promise(resolve => { finishStart = () => { session = sessionFixture(); resolve(session); }; });
  const { app, root, click } = harness({
    irrigationControl: async () => controlFixture(session), irrigationActive: async () => session,
    startIrrigation: async () => { starts++; return startResponse; },
  });
  await app.boot(); app.state.page = 'irrigation'; app.render();
  assert.match(root.innerHTML, /No active irrigation session/);
  assert.match(root.innerHTML, /data-action="start-irrigation" >/);
  const pending = click({ action: 'start-irrigation' });
  await click({ action: 'start-irrigation' });
  assert.equal(starts, 1);
  assert.match(root.innerHTML, /Starting…/);
  assert.equal(app.state.irrigationActive.data, null);
  finishStart(); await pending;
  assert.equal(app.state.irrigationActive.data.event_id, 'test-session');
  assert.match(root.innerHTML, /Started manually by the farmer\/operator/);
  assert.match(root.innerHTML, /Simulation · No physical pump control/);
  assert.match(root.innerHTML, /Flow sensor data unavailable/);
  assert.doesNotMatch(root.innerHTML, /target volume|progress percent|moisture target/i);
  app.state.page = 'home'; app.render();
  assert.match(root.innerHTML, /Manual irrigation active/);
  assert.doesNotMatch(root.innerHTML, /Start Manual Irrigation|Stop Irrigation|Current session/);
});

test('stop is confirmed by backend before active state changes, then history and sensors refresh', async () => {
  let session = sessionFixture(), events = [], finishStop, sensorReads = 0;
  const stopResponse = new Promise(resolve => { finishStop = () => { const ended = { ...session, status: 'completed', ended_at: iso(0), duration_seconds: 65, water_used_litres: null }; events = [ended]; session = null; resolve(ended); }; });
  const { app, root, click } = harness({
    irrigationControl: async () => controlFixture(session), irrigationActive: async () => session,
    irrigationHistory: async () => events, stopIrrigation: async () => stopResponse,
    sensorReadings: async () => { sensorReads++; return [latest]; },
  });
  await app.boot(); app.state.page = 'irrigation'; app.render();
  const pending = click({ action: 'stop-irrigation' });
  assert.equal(app.state.irrigationActive.data.status, 'started');
  finishStop(); await pending;
  assert.equal(app.state.irrigationActive.data, null);
  assert.equal(app.state.irrigationHistory.data[0].status, 'completed');
  assert.equal(sensorReads, 2);
  assert.match(root.innerHTML, /No active irrigation session/);
  assert.match(root.innerHTML, /1 min 5 sec/);
});

test('409 start conflict reloads the backend session instead of creating local state', async () => {
  let session = null;
  const { app, click } = harness({
    irrigationControl: async () => controlFixture(session), irrigationActive: async () => session,
    startIrrigation: async () => { session = sessionFixture(); throw Object.assign(new Error('conflict'), { status: 409 }); },
  });
  await app.boot(); await click({ action: 'start-irrigation' });
  assert.equal(app.state.irrigationActive.data, session);
});

test('emergency acknowledgement failure is visible and never presented as stopped', async () => {
  const session = { ...sessionFixture(), status: 'failed', command_acknowledged: false };
  let calls = 0;
  const { app, root, click } = harness({
    irrigationControl: async () => controlFixture(session), irrigationActive: async () => session,
    emergencyStop: async () => { calls++; return { acknowledged: false, control_mode: 'simulated', message: 'No acknowledgement' }; },
  });
  await app.boot(); app.state.page = 'irrigation';
  await click({ action: 'emergency-stop' });
  assert.equal(calls, 1);
  assert.match(root.innerHTML, /Pump-off NOT confirmed/);
  assert.equal(app.state.irrigationActive.data.ended_at, null);
  assert.doesNotMatch(root.innerHTML.match(/<button[^>]*data-action="emergency-stop"[^>]*>/)[0], /disabled/);
});

test('emergency stop sends immediately and repeats after an in-flight start settles', async () => {
  let session = null, finishStart, stops = 0;
  const response = new Promise(resolve => { finishStart = () => { session = sessionFixture(); resolve(session); }; });
  const { app, click } = harness({
    irrigationControl: async () => controlFixture(session), irrigationActive: async () => session,
    startIrrigation: () => response,
    emergencyStop: async () => { stops++; session = null; return { acknowledged: true, control_mode: 'simulated', session: null }; },
  });
  await app.boot(); const starting = click({ action: 'start-irrigation' });
  const emergency = click({ action: 'emergency-stop' });
  assert.equal(stops, 1);
  finishStart(); await Promise.all([starting, emergency]);
  assert.equal(stops, 2);
  assert.equal(app.state.irrigationActive.data, null);
});

test('field switch during irrigation command cannot replace the new field state', async () => {
  let finishStart;
  const response = new Promise(resolve => { finishStart = () => resolve(sessionFixture()); });
  const { app, click } = harness({
    irrigationControl: async () => controlFixture(null), irrigationActive: async () => null,
    startIrrigation: () => response,
  });
  await app.boot(); const pending = click({ action: 'start-irrigation' });
  await app.loadFieldData('field-b'); finishStart(); await pending;
  assert.equal(app.state.activeFieldId, 'field-b');
  assert.equal(app.state.irrigationActive.data, null);
});

test('elapsed display derives only from backend timestamps and stops at persisted duration', () => {
  const session = sessionFixture();
  assert.equal(elapsedSeconds(session, now), 65);
  assert.equal(durationLabel(elapsedSeconds(session, now)), '1 min 5 sec');
  assert.equal(elapsedSeconds({ ...session, ended_at: iso(-1000), duration_seconds: 64 }, now + 100000), 64);
});

test('irrigation client uses the real POST endpoints and preserves conflict status', async () => {
  const clientSource = (await readFile(new URL('../src/api/client.js', import.meta.url), 'utf8'))
    .replace('import.meta.env?.VITE_API_BASE_URL', 'undefined').replace(/^export /gm, '');
  const calls = [];
  const context = vm.createContext({ window: { location: { hostname: '127.0.0.1' } }, fetch: async (url, options) => { calls.push([url, options.method]); return { ok: false, status: 409, json: async () => ({ detail: 'Already active' }) }; } });
  vm.runInContext(`${clientSource}\nglobalThis.client = api;`, context);
  for (const name of ['startIrrigation', 'stopIrrigation', 'emergencyStop']) await assert.rejects(context.client[name]('field-a'), error => error.status === 409);
  assert.deepEqual(calls.map(([url, method]) => [url.split('/').at(-1), method]), [['start', 'POST'], ['stop', 'POST'], ['emergency-stop', 'POST']]);
});

function agronomicForm({ sowing = 'timely', irrigation = 'irrigated', variety = '' } = {}) {
  const values = { '#sowing-condition': sowing, '#irrigation-condition': irrigation, '#variety-code': variety };
  return { querySelector: selector => ({ value: values[selector] }) };
}

test('Crop setup shows Western UP/NWPZ and saves an unknown variety as null', async () => {
  let payload;
  const resolved = { crop_cycle_id: 'cycle-a', profile: { code: 'timely', crop: 'Wheat', region: 'Western Uttar Pradesh', zone_code: 'NWPZ', zone_name: 'North Western Plains Zone', sowing_condition: 'timely', irrigation_condition: 'irrigated', verification_status: 'official_verified', source_organization: 'ICAR-IIWBR', source_url: 'https://iiwbr.org.in/' }, sowing_date: '2026-01-01', agricultural_date: '2026-09-27', days_after_sowing: 269, selected_variety: null, profile_specificity: 'regional', variety_message: 'You can continue without selecting a variety.', current_stage: null, stage_status: 'not_configured' };
  const { app, root } = harness({ updateAgronomicProfile: async (_id, body) => { payload = body; return resolved; } });
  await app.boot(); app.state.page = 'crop'; app.render();
  assert.match(root.innerHTML, /Western Uttar Pradesh/);
  assert.match(root.innerHTML, /North Western Plains Zone \(NWPZ\)/);
  assert.match(root.innerHTML, /I don&#39;t know \/ Not sure/);
  await app.saveAgronomic(agronomicForm());
  assert.equal(payload.profile_code, 'timely');
  assert.equal(payload.variety_code, null);
  assert.equal(app.state.agronomicProfile.data.profile_specificity, 'regional');
  assert.match(root.innerHTML, /Regional agronomic profile saved without a variety/);
});

test('compatible selected variety is saved and unlisted variety is blocked locally', async () => {
  const calls = [];
  const resolved = { crop_cycle_id: 'cycle-a', profile: { code: 'timely', sowing_condition: 'timely', irrigation_condition: 'irrigated', verification_status: 'official_verified', source_organization: 'ICAR', source_url: 'https://icar.org.in/' }, sowing_date: '2026-01-01', agricultural_date: '2026-09-27', days_after_sowing: 269, selected_variety: { code: 'HD 3226', display_name: 'HD 3226', sowing_window_start: '11-05', sowing_window_end: '11-25', first_irrigation_about_das: 21 }, profile_specificity: 'variety', variety_message: 'Variety-specific official metadata is available.', current_stage: null, stage_status: 'not_configured' };
  const { app, root } = harness({ updateAgronomicProfile: async (_id, body) => { calls.push(body); return resolved; } });
  await app.boot(); app.state.page = 'crop';
  await app.saveAgronomic(agronomicForm({ variety: 'HD 3226' }));
  assert.equal(calls[0].profile_code, 'timely');
  assert.equal(calls[0].variety_code, 'HD 3226');
  assert.match(root.innerHTML, /First irrigation about 21 DAS/);
  assert.match(root.innerHTML, /not an automatic pump rule/i);
  app.state.page = 'crop'; app.render();
  await app.saveAgronomic(agronomicForm({ variety: 'Made Up Wheat' }));
  assert.equal(calls.length, 1);
  assert.match(root.innerHTML, /Choose a compatible variety/);
});

test('production-condition change requests a backend-filtered variety list', async () => {
  const filters = [];
  const { app } = harness({ wheatVarieties: async (sowing, irrigation) => { filters.push([sowing, irrigation]); return []; } });
  await app.boot();
  await app.loadVarieties('early', 'irrigated');
  await app.loadVarieties('timely', 'restricted_irrigation');
  assert.ok(filters.some(pair => pair[0] === 'early' && pair[1] === 'irrigated'));
  assert.ok(filters.some(pair => pair[0] === 'timely' && pair[1] === 'restricted_irrigation'));
});

test('agronomic API client sends PUT selection and filtered catalogue queries', async () => {
  const clientSource = (await readFile(new URL('../src/api/client.js', import.meta.url), 'utf8'))
    .replace('import.meta.env?.VITE_API_BASE_URL', 'undefined').replace(/^export /gm, '');
  const requests = [];
  const context = vm.createContext({ window: { location: { hostname: '127.0.0.1' } }, fetch: async (url, options = {}) => { requests.push([url, options]); return { ok: true, json: async () => ({}) }; }, JSON });
  vm.runInContext(`${clientSource}\nglobalThis.client = api;`, context);
  await context.client.wheatVarieties('timely', 'restricted_irrigation');
  await context.client.updateAgronomicProfile('cycle-a', { profile_code: 'restricted', variety_code: null });
  assert.match(requests[0][0], /sowing_condition=timely&irrigation_condition=restricted_irrigation/);
  assert.equal(requests[1][1].method, 'PUT');
  assert.deepEqual(JSON.parse(requests[1][1].body), { profile_code: 'restricted', variety_code: null });
});

test('language selector updates every existing page both ways without changing values or calling APIs', async () => {
  let reads = 0;
  const { app, root, click } = harness({ fields: async () => { reads++; return fields; } });
  await app.boot();
  const data = JSON.stringify([app.state.field, app.state.cycles, app.state.sensors, app.state.weather, app.state.irrigationActive]);
  const pageLabels = { home: 'navigation.home', irrigation: 'navigation.irrigation', crop: 'navigation.crop', history: 'navigation.history', more: 'navigation.more' };
  try {
    for (const [page, key] of Object.entries(pageLabels)) {
      await click({ page });
      const before = reads;
      await click({ action: 'language', language: 'hi' });
      assert.match(root.innerHTML, new RegExp(`<h1>${t(key)}</h1>`));
      assert.match(root.innerHTML, /data-language="hi"[^>]*aria-pressed="true"/);
      const visible = root.innerHTML.replace(/<[^>]*>/g, ' ').replace(/&[^;]+;/g, ' ')
        .replace(/English|KJ|Wheat|Test field [AB]|Test device|Open-Meteo|open-meteo|HD 3226|NWPZ|ICAR-IIWBR|ET0|L\/min|m\/s|mm|°C|\bL\b/g, '');
      assert.doesNotMatch(visible, /[A-Za-z]{2,}/, `${page} has untranslated interface text: ${visible}`);
      assert.doesNotMatch(root.innerHTML, /common\.[a-zA-Z]|navigation\.[a-zA-Z]|irrigation\.[a-zA-Z]/);
      await click({ action: 'language', language: 'en' });
      assert.match(root.innerHTML, new RegExp(`<h1>${t(key)}</h1>`));
      assert.equal(reads, before, 'Language selection must not make data requests');
    }
    assert.equal(JSON.stringify([app.state.field, app.state.cycles, app.state.sensors, app.state.weather, app.state.irrigationActive]), data);
  } finally { await changeLanguage('en'); }
});

test('Hindi empty states and API failures never show internal errors', async () => {
  const { app, root } = harness({ fields: async () => { throw new Error('database secret'); } });
  await app.boot();
  try {
    await changeLanguage('hi');
    for (const page of ['home', 'crop', 'irrigation', 'history', 'more']) {
      app.state.page = page;
      if (page === 'history') await app.loadHistory();
      app.render();
      assert.doesNotMatch(root.innerHTML, /database secret|unavailable|not configured|No active|Loading/);
      assert.match(root.innerHTML, /[\u0900-\u097f]/);
    }
  } finally { await changeLanguage('en'); }
});

test('language change preserves unsaved crop conditions and variety entry', async () => {
  const { app, root, input, click } = harness();
  await app.boot(); app.state.page = 'crop'; app.render();
  const form = { querySelector: selector => ({ value: selector === '#sowing-condition' ? 'timely' : 'irrigated' }) };
  input({ id: 'variety-code', value: 'HD 3226', form });
  try {
    await click({ action: 'language', language: 'hi' });
    assert.match(root.innerHTML, /id="variety-code"[^>]*value="HD 3226"/);
    assert.equal(app.state.agronomicDraft.sowing, 'timely');
    assert.equal(app.state.agronomicDraft.irrigation, 'irrigated');
    await click({ action: 'language', language: 'en' });
    assert.match(root.innerHTML, /id="variety-code"[^>]*value="HD 3226"/);
  } finally { await changeLanguage('en'); }
});

test('a pending command and its acknowledgement follow the selected language without sending another command', async () => {
  let starts = 0, session = null, finish;
  const promise = new Promise(resolve => { finish = () => { session = sessionFixture(); resolve(session); }; });
  const { app, root, click } = harness({
    irrigationControl: async () => controlFixture(session), irrigationActive: async () => session,
    startIrrigation: async () => { starts++; return promise; },
  });
  await app.boot(); app.state.page = 'irrigation'; app.render();
  const request = click({ action: 'start-irrigation' });
  try {
    await click({ action: 'language', language: 'hi' });
    assert.match(root.innerHTML, new RegExp(hi.irrigation.starting));
    assert.equal(starts, 1);
    finish(); await request;
    assert.match(root.innerHTML, new RegExp(hi.irrigation.startedNotice));
    assert.match(root.innerHTML, /37.5%/);
    assert.doesNotMatch(root.innerHTML, /manual session started|Simulation ·/);
    await click({ action: 'language', language: 'en' });
    assert.match(root.innerHTML, /manual session started/);
    assert.equal(starts, 1);
  } finally { await changeLanguage('en'); }
});

test('already displayed emergency failure warnings and crop confirmations translate immediately', async () => {
  const { app, root, click } = harness({
    irrigationControl: async () => controlFixture(null),
    emergencyStop: async () => ({ acknowledged: false, control_mode: 'simulated', message: en.messages.offUnconfirmed }),
  });
  await app.boot();
  await click({ action: 'emergency-stop' });
  assert.match(root.innerHTML, /Pump-off NOT confirmed/);
  try {
    await click({ action: 'language', language: 'hi' });
    assert.match(root.innerHTML, /पंप बंद होने की पुष्टि नहीं मिली/);
    assert.doesNotMatch(root.innerHTML, /Pump-off|not acknowledged/);
    app.state.page = 'crop';
    app.state.agronomicNotice = { error: false, messageKey: 'crop.savedRegional' }; app.render();
    assert.match(root.innerHTML, new RegExp(hi.crop.savedRegional));
    await click({ action: 'language', language: 'en' });
    assert.match(root.innerHTML, /Regional agronomic profile saved without a variety/);
    assert.match(root.innerHTML, /Pump-off NOT confirmed/);
  } finally { await changeLanguage('en'); }
});

test('Hindi covers populated profile notes, session history, faults and controller explanations', async () => {
  const selectedVariety = { code: 'HD 3226', display_name: 'HD 3226', sowing_window_start: '11-01', sowing_window_end: '11-20', first_irrigation_about_das: 21 };
  const { app, root } = harness({
    irrigationControl: async () => ({ ...controlFixture(null), message: en.messages.simulation }),
    irrigationHistory: async () => [{ ...sessionFixture(), status: 'failed', ended_at: iso(-100), fault_code: 'STOP_UNCONFIRMED', trigger_reason: 'manual farmer request', duration_seconds: 65 }],
    agronomicProfile: async () => ({ profile: { irrigation_condition: 'irrigated', sowing_condition: 'timely', verification_status: 'official_verified', source_url: 'https://iiwbr.org.in/', source_organization: 'ICAR-IIWBR' }, selected_variety: selectedVariety, days_after_sowing: 21, sowing_window_match: false, variety_message: en.messages.knownVariety }),
  });
  await app.boot();
  try {
    await changeLanguage('hi');
    app.state.page = 'crop'; app.render();
    assert.match(root.innerHTML, new RegExp(hi.messages.knownVariety));
    assert.match(root.innerHTML, /पहली सिंचाई बुवाई के करीब 21 दिन बाद/);
    assert.match(root.innerHTML, /11-01 से 11-20/);
    assert.match(root.innerHTML, /आधिकारिक जानकारी से जाँचा गया/);
    assert.doesNotMatch(root.innerHTML, /Production profile|First irrigation|Selected date|official verified| sown/);
    app.state.page = 'irrigation'; app.render();
    assert.match(root.innerHTML, new RegExp(hi.messages.simulation));
    assert.match(root.innerHTML, /बंद होने की पुष्टि नहीं मिली/);
    assert.match(root.innerHTML, /किसान ने सिंचाई की माँग की/);
    assert.match(root.innerHTML, /1 मिनट 5 सेकंड/);
    assert.doesNotMatch(root.innerHTML, /START_|STOP_|MANUAL|manual farmer|physical pump/);
  } finally { await changeLanguage('en'); }
});

test('recorded Crop sections render in order with the profile always visible and technical details collapsed', async () => {
  const { app, root, click } = harness();
  await app.boot(); await click({ page: 'crop' });
  const headings = ['Growth stage not configured', 'Agronomic profile', 'Crop cycle', 'Crop lifecycle', 'Crop recommendations', 'Next stage', 'Crop environment', 'Weather Forecast', 'Soil profile', 'Technical crop details'];
  let previous = -1;
  for (const heading of headings) {
    const position = root.innerHTML.indexOf(heading);
    assert.ok(position > previous, `${heading} follows the preceding recorded section`);
    previous = position;
  }
  assert.match(root.innerHTML, /id="agronomic-form"/);
  assert.match(root.innerHTML, /Save agronomic profile/);
  assert.equal((root.innerHTML.match(/class="metric-card"/g) || []).length, 4);
  assert.equal((root.innerHTML.match(/class="panel weather-panel"/g) || []).length, 1);
  assert.match(root.innerHTML, /<details class="panel technical-details">/);
  assert.doesNotMatch(root.innerHTML, /<details[^>]*\bopen\b|Edit Crop|Crop overview|Advanced crop details/);
});

test('all fields remain selectable across farms and More shows the selected field farm without management actions', async () => {
  const farms = [{ farm_id: 'farm-a', farm_name: 'Farm A' }, { farm_id: 'farm-b', farm_name: 'Farm B' }];
  const { app, root, change, click } = harness({ farms: async () => farms });
  await app.boot();
  assert.match(root.innerHTML, /value="field-a"/);
  assert.match(root.innerHTML, /value="field-b"/);
  await change({ id: 'field-selector', value: 'field-b' });
  assert.equal(app.state.activeFieldId, 'field-b');
  await click({ page: 'more' });
  assert.match(root.innerHTML, /Farm B/);
  assert.doesNotMatch(root.innerHTML, /Farm A|farm-selector|data-action="(?:add-|edit-|search-location)/);
});

test('empty data keeps all original pages available without forced setup or automatic writes', async () => {
  const { app, root, click, calls } = harness({ fields: async () => [], farms: async () => [] });
  await app.boot();
  for (const page of ['home', 'crop', 'irrigation', 'history', 'more']) {
    await click({ page });
    assert.match(root.innerHTML, new RegExp(`<h1>${t(`navigation.${page}`)}</h1>`));
    assert.doesNotMatch(root.innerHTML, /journey-form|add-farm|add-field|add-crop|edit-farm|edit-crop|search-location|Demo access/);
  }
  assert.equal(calls.length, 0);
});

test('restored profile form preserves a failed draft and updates Crop and Home after a successful save', async () => {
  let fail = true, saved = null;
  const profile = { code: 'timely', irrigation_condition: 'irrigated', sowing_condition: 'timely' };
  const { app, root, click } = harness({
    updateAgronomicProfile: async (_id, body) => {
      if (fail) throw new Error('private database detail');
      saved = body;
      return { profile, selected_variety: { code: 'HD 3226', display_name: 'HD 3226' } };
    },
  });
  await app.boot(); await click({ page: 'crop' });
  await app.saveAgronomic(agronomicForm({ variety: 'HD 3226' }));
  assert.match(root.innerHTML, /id="variety-code"[^>]*value="HD 3226"/);
  assert.match(root.innerHTML, /Agronomic profile could not be saved/);
  assert.doesNotMatch(root.innerHTML, /private database detail/);
  fail = false;
  await app.saveAgronomic(agronomicForm({ variety: 'HD 3226' }));
  assert.equal(saved.variety_code, 'HD 3226');
  await click({ page: 'home' });
  assert.match(root.innerHTML, /HD 3226/);
  await click({ page: 'crop' });
  assert.match(root.innerHTML, /id="agronomic-form"/);
  assert.match(root.innerHTML, /id="variety-code"[^>]*value="HD 3226"/);
});

test('rapid variety filters and field switches reject stale catalogue and profile-save results', async () => {
  let finishOld, finishSave;
  const old = new Promise(resolve => { finishOld = resolve; });
  const saved = new Promise(resolve => { finishSave = resolve; });
  const { app } = harness({
    wheatVarieties: async sowing => sowing === 'early' ? old : [{ code: 'HD 3226', display_name: 'HD 3226' }],
    updateAgronomicProfile: async () => saved,
  });
  await app.boot();
  const request = app.loadVarieties('early', 'irrigated');
  await app.loadVarieties('timely', 'irrigated');
  finishOld([{ code: 'Old condition variety' }]); await request;
  assert.equal(app.state.varieties.data[0].code, 'HD 3226');
  const save = app.saveAgronomic(agronomicForm({ variety: 'HD 3226' }));
  await app.loadFieldData('field-b');
  finishSave({ profile: { code: 'old-field-profile' }, selected_variety: { code: 'Old field variety' } });
  await save;
  assert.equal(app.state.activeFieldId, 'field-b');
  assert.equal(app.state.agronomicSaving, false);
  assert.notEqual(app.state.agronomicProfile.data?.profile?.code, 'old-field-profile');
});

test('unsupported crops never request Wheat varieties and catalogue failures have localized retry', async () => {
  let reads = 0;
  const unsupported = harness({ cropCycles: async () => [{ crop_cycle_id: 'other', status: 'active', crop: { crop_name: 'Rice' } }], wheatVarieties: async () => { reads++; return []; } });
  await unsupported.app.boot(); await unsupported.click({ page: 'crop' });
  assert.equal(reads, 0);
  assert.doesNotMatch(unsupported.root.innerHTML, /id="variety-code"/);
  let fail = true;
  const { app, root, click } = harness({ agronomicProfiles: async () => { if (fail) throw new Error('private catalogue failure'); return []; } });
  await app.boot(); await click({ page: 'crop' });
  assert.match(root.innerHTML, /data-action="retry-agronomic"/);
  assert.doesNotMatch(root.innerHTML, /private catalogue failure|common\.retry/);
  fail = false; await click({ action: 'retry-agronomic' });
  assert.doesNotMatch(root.innerHTML, /data-action="retry-agronomic"/);
});
