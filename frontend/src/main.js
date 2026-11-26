import { i18n, t, locale, changeLanguage, valueLabel, messageLabel } from './i18n.js';
import { api } from './api/client.js';
import { icon } from './icons.js';
import { sensorHistory, upcomingForecasts, cropAge, deviceAvailable } from './data.js';
import { elapsedSeconds, durationLabel, controlLabel } from './irrigation.js';

const root = document.querySelector('#app');
const empty = (message) => ({ status: 'empty', data: null, error: message });
const pending = () => ({ status: 'loading', data: null, error: null });
const ready = (data) => ({ status: 'ready', data, error: null });
const failed = (error) => ({ status: 'error', data: null, error: error instanceof Error ? error.message : t('common.loadError') });
const state = {
  api: pending(), fields: pending(), farms: pending(), activeFieldId: null, field: pending(), cycles: pending(), soil: pending(), devices: pending(), sensors: pending(), weather: pending(),
  page: 'home', moreOpen: false, weatherRefreshing: false, weatherRefreshError: null,
  history: { sensors: pending(), forecast: pending() },
  irrigationControl: pending(), irrigationActive: pending(), irrigationHistory: pending(),
  agronomicProfiles: pending(), agronomicProfile: pending(), varieties: pending(), agronomicDraft: null, agronomicSaving: false, agronomicNotice: null,
};
let fieldVersion = 0;
let historyVersion = 0;
let irrigationVersion = 0;
let varietyVersion = 0;
const irrigationCommands = new Map();
const commandState = () => irrigationCommands.get(state.activeFieldId) || {};

function emergencyButton(compact = false) {
  const disabled = !state.activeFieldId || commandState().emergency || !(state.irrigationControl.data?.available || state.irrigationActive.data || commandState().normal);
  return `<button class="emergency-button ${compact ? 'emergency-compact' : ''}" type="button" data-action="emergency-stop" ${disabled ? 'disabled' : ''} title="${h('irrigation.emergencyHint')}">${icon('alert')}<span>${commandState().emergency ? h('irrigation.sendingStop') : h('irrigation.emergency')}</span></button>`;
}
function commandNotice() {
  const notice = commandState().notice;
  if (!notice) return '';
  let message;
  if (notice.kind === 'emergency') {
    message = notice.error
      ? t('irrigation.offUnconfirmed', { message: messageLabel(notice.apiMessage, 'irrigation.retry') })
      : t('irrigation.acknowledged', { control: controlLabel(notice.controlMode) });
  } else if (notice.kind === 'normal') {
    message = t('irrigation.commandNotice', { control: controlLabel(notice.controlMode), message: t(notice.action === 'start-irrigation' ? 'irrigation.startedNotice' : 'irrigation.completedNotice') });
  } else {
    message = notice.conflict ? t('irrigation.stateChanged') : t('irrigation.errorNotice', {
      summary: t(notice.emergency ? 'irrigation.emergencyUnconfirmed' : 'irrigation.requestUnconfirmed'),
      message: messageLabel(notice.apiMessage, 'irrigation.checkRetry'),
    });
  }
  return `<div class="command-banner ${notice.error ? 'error-note' : ''}" role="status">${esc(message)}</div>`;
}

const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
const h = (key, options) => esc(t(key, options));
const number = (value) => value == null || value === '' || !Number.isFinite(Number(value)) ? null : Number(value);
const fmt = (value, digits = 1) => { const n = number(value); return n == null ? '—' : n.toLocaleString(locale(), { maximumFractionDigits: digits }); };
const parsedDate = value => value ? new Date(/^\d{4}-\d{2}-\d{2}$/.test(value) ? `${value}T00:00:00` : value) : null;
const dateLabel = (value, options = { day: 'numeric', month: 'short', year: 'numeric' }) => Number.isFinite(parsedDate(value)?.getTime()) ? parsedDate(value).toLocaleDateString(locale(), options) : null;
const timeLabel = (value) => Number.isFinite(parsedDate(value)?.getTime()) ? parsedDate(value).toLocaleTimeString(locale(), { hour: 'numeric', minute: '2-digit' }) : null;
const stamp = value => dateLabel(value) ? `${dateLabel(value)} · ${timeLabel(value)}` : t('common.timeUnavailable');
const activeCycle = () => (state.cycles.data || []).find(item => item.status === 'active');
const activeSoil = () => (state.soil.data || []).find(item => item.active);
const latestSensor = () => sensorHistory(state.sensors.data || [])[0];
const measure = (value, unit) => number(value) == null ? '—' : `${fmt(value)}${esc(unit)}`;
const details = rows => `<dl>${rows.map(([label, value]) => `<dt>${esc(label)}</dt><dd>${esc(value ?? t('common.notConfigured'))}</dd>`).join('')}</dl>`;
const table = (headers, rows) => `<div class="table-scroll" tabindex="0" aria-label="${h('common.table')}"><table><thead><tr>${headers.map(label => `<th scope="col">${esc(label)}</th>`).join('')}</tr></thead><tbody>${rows.map(cells => `<tr>${cells.map(cell => `<td>${cell}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
function sectionContent(section, label, content, missing) {
  if (section.status === 'loading') return box(section, t('common.loadingSection', { section: label.toLowerCase() }));
  if (section.status === 'error') return sectionError(section, t('common.sectionUnavailable', { section: label }));
  return content || `<p class="state-note">${esc(missing)}</p>`;
}
function modeSelector() {
  return `<fieldset class="mode-selector"><legend>${h('irrigation.mode')}</legend><button type="button" disabled title="${h('irrigation.autoHint')}">${h('irrigation.auto')}</button><span class="manual-mode">${h('irrigation.manual')}</span></fieldset><p class="support-copy">${h('irrigation.autoHint')}</p>`;
}

function irrigationHistory(previous = false) {
  const rows = state.irrigationHistory.data || [];
  const latest = rows[0];
  const content = previous ? latest ? details([
    [t('irrigation.modeLabel'), valueLabel(latest.mode)], [t('irrigation.controlPath'), controlLabel(latest.control_mode)], [t('irrigation.status'), valueLabel(latest.status)],
    [t('irrigation.started'), stamp(latest.started_at)], [t('irrigation.ended'), stamp(latest.ended_at)],
    [t('irrigation.duration'), durationLabel(latest.duration_seconds)],
    [t('irrigation.measuredWater'), number(latest.water_used_litres) == null ? t('common.unavailable') : `${fmt(latest.water_used_litres)} L`],
    [t('irrigation.moistureBefore'), number(latest.moisture_before_pct) == null ? t('common.unavailable') : `${fmt(latest.moisture_before_pct)}%`],
    [t('irrigation.moistureAfter'), number(latest.moisture_after_pct) == null ? t('common.unavailable') : `${fmt(latest.moisture_after_pct)}%`],
    [t('irrigation.reason'), valueLabel(latest.trigger_reason)], [t('irrigation.fault'), valueLabel(latest.fault_code) || t('common.noneRecorded')],
  ]) : '' : rows.length ? table([t('irrigation.startedEnded'), t('irrigation.modeControl'), t('irrigation.status'), t('irrigation.duration'), t('irrigation.measuredWater'), t('irrigation.moistureBeforeAfter')], rows.map(event => [
    `${esc(stamp(event.started_at))}<br/>${esc(stamp(event.ended_at))}`,
    `${esc(valueLabel(event.mode))}<br/>${esc(controlLabel(event.control_mode))}`,
    `${esc(valueLabel(event.status))}${event.fault_code ? `<br/>${esc(valueLabel(event.fault_code))}` : ''}`,
    esc(durationLabel(event.duration_seconds)), measure(event.water_used_litres, ' L'),
    `${measure(event.moisture_before_pct, '%')} / ${measure(event.moisture_after_pct, '%')}`,
  ])) : '';
  return `<section class="panel detail-card history-panel"><div class="panel-heading"><h2>${h(previous ? 'irrigation.previous' : 'irrigation.history')}</h2></div>${sectionContent(state.irrigationHistory, t('irrigation.historySection'), content, t('irrigation.emptyHistory'))}</section>`;
}

function ago(value) {
  if (!value) return null;
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000));
  if (!Number.isFinite(seconds)) return null;
  if (seconds < 60) return t('common.justNow');
  if (seconds < 3600) return t('common.minutesAgo', { count: Math.floor(seconds / 60) });
  if (seconds < 86400) return t('common.hoursAgo', { count: Math.floor(seconds / 3600) });
  return dateLabel(value, { day: 'numeric', month: 'short' });
}
const box = (value, label = t('common.loading')) => value.status === 'loading' ? `<div class="state-note"><span class="spinner"></span>${esc(label)}</div>` : '';
function sectionError(section, fallback) { return section.status === 'error' ? `<div class="state-note error-note">${icon('alert')}<span>${esc(fallback || messageLabel(section.error))}</span></div>` : ''; }
function sectionEmpty(section, message) { return section.status === 'empty' ? `<div class="state-note">${icon('info')}<span>${esc(message)}</span></div>` : ''; }

function header() {
  const fields = state.fields.data || [];
  const selected = state.activeFieldId || '';
  const fieldPicker = fields.length > 1 ? `<label class="field-select"><span class="sr-only">${h('navigation.chooseField')}</span><select id="field-selector" aria-label="${h('navigation.chooseField')}">${fields.map((field) => `<option value="${esc(field.field_id)}" ${field.field_id === selected ? 'selected' : ''}>${esc(field.field_name)}</option>`).join('')}</select></label>` : `<div class="field-chip">${icon('soil')}<span>${state.fields.status === 'loading' ? t('navigation.findingField') : esc(fields[0]?.field_name || t('navigation.noField'))}</span></div>`;
  const nav = [['home', t('navigation.home')], ['irrigation', t('navigation.irrigation')], ['crop', t('navigation.crop')], ['history', t('navigation.history')]];
  return `<header class="topbar"><a class="brand" href="#home" data-page="home"><img src="/logo.svg" alt="${h('app.logo')}"/><span class="brand-copy"><strong>${h('app.brand')}</strong><span>${h('app.tagline')}</span></span></a>
    ${fieldPicker}<nav class="main-nav" aria-label="${h('navigation.main')}">${nav.map(([name, label]) => `<button class="nav-button ${state.page === name ? 'active' : ''}" data-page="${name}">${icon(name === 'irrigation' ? 'drop' : name === 'crop' ? 'crop' : name === 'history' ? 'history' : 'home')}<span>${label}</span></button>`).join('')}<div class="more-wrap"><button class="nav-button more-button ${state.moreOpen || state.page === 'more' ? 'active' : ''}" data-action="more" aria-expanded="${state.moreOpen}">${icon('more')}<span>${h('navigation.more')}</span><span class="chevron">⌄</span></button>${state.moreOpen ? `<div class="more-menu"><button data-page="more">${h('navigation.farmField')}</button><button data-page="more">${h('navigation.deviceInfo')}</button></div>` : ''}</div></nav>
    <div class="top-actions"><div class="language-selector" role="group" aria-label="${h('navigation.language')}">${['en', 'hi'].map(language => `<button class="language-button" type="button" data-action="language" data-language="${language}" lang="${language}" aria-pressed="${i18n.language === language}">${h(language === 'en' ? 'navigation.english' : 'navigation.hindi')}</button>`).join('<span aria-hidden="true">|</span>')}</div><span class="header-divider"></span><span class="user-avatar" aria-hidden="true">KJ</span><span class="user-copy"><strong>${h('navigation.farmer')}</strong><small>${h('navigation.operator')}</small></span>${emergencyButton(true)}</div>
  </header>`;
}

function statusBanner() {
  const apiOk = state.api.status === 'ready';
  const sensorReadings = sensorHistory(state.sensors.data || []);
  const valid = sensorReadings[0]?.sensor_valid === true;
  let label = t('dashboard.checking');
  let sub = t('dashboard.connecting');
  let isError = false;
  if (state.api.status === 'error') { label = t('dashboard.healthUnavailable'); sub = t('dashboard.otherLoaded'); isError = true; }
  else if (state.api.status === 'ready' && state.fields.status === 'loading') { label = t('dashboard.loadingField'); sub = t('dashboard.readingField'); }
  else if (state.api.status === 'ready' && state.fields.status === 'error') { label = t('dashboard.fieldUnavailable'); sub = t('dashboard.listFailed'); isError = true; }
  else if (state.api.status === 'ready' && state.fields.status === 'empty') { label = t('dashboard.noField'); sub = t('dashboard.addField'); }
  else if (state.api.status === 'ready' && state.sensors.status === 'error') { label = t('dashboard.sensorUnavailable'); sub = t('dashboard.sensorFailed'); isError = true; }
  else if (state.api.status === 'ready' && state.sensors.status === 'loading') { label = t('dashboard.loadingField'); sub = t('dashboard.sensorLoading'); }
  else if (state.api.status === 'ready' && valid) { label = t('dashboard.fieldAvailable'); sub = t('dashboard.recordsSource'); }
  else if (state.api.status === 'ready' && sensorReadings.length) { label = t('dashboard.latestReview'); sub = t('dashboard.latestInvalid'); }
  else if (state.api.status === 'ready') { label = t('dashboard.notReported'); sub = t('dashboard.noValidReading'); }
  if (state.weather.status === 'error' && apiOk) sub += t('dashboard.weatherUnavailableSuffix');
  return `<div class="status-banner ${isError ? 'status-error' : 'status-ok'}"><span class="status-dot"></span><strong>${esc(label)}</strong><span class="status-sub">${esc(sub)}</span><span class="status-source">${h('dashboard.service')}</span></div>`;
}

function fieldSummary() {
  const farm = selectedFarm();
  const cycle = activeCycle();
  const latest = latestSensor();
  const cropTitle = state.cycles.status === 'loading' ? t('dashboard.loadingCrop') : state.cycles.status === 'error' ? t('dashboard.cropUnavailable') : cycle?.crop?.crop_name || t('dashboard.cropNotConfigured');
  const sensorState = state.sensors.status === 'loading' ? t('common.loading') : state.sensors.status === 'error' ? t('dashboard.sensorUnavailable') : latest ? latest.sensor_valid ? t('dashboard.readingAvailable') : t('dashboard.readingReview') : t('dashboard.noSensor');
  const devices = state.devices.data || [];
  const deviceState = state.devices.status === 'loading' ? t('dashboard.loadingDevices') : state.devices.status === 'error' ? t('dashboard.deviceUnavailable') : devices.length ? devices.map(item => valueLabel(item.status) || t('common.unknown')).join(' · ') : t('dashboard.noDevice');
  return `<section class="summary-card"><div class="summary-main"><div class="summary-icon">${icon('crop')}</div><div class="summary-text"><div class="summary-title-row"><h1>${esc(cropTitle)}</h1>${cycle ? `<span class="plot-tag">${esc(valueLabel(cycle.status))}</span>` : ''}</div><div class="summary-meta">${farm?.farm_name ? `<span>${esc(farm.farm_name)}</span><i></i>` : ''}<span>${esc(cycle ? savedVariety() || t('common.notConfigured') : t('dashboard.cropNotConfigured'))}</span></div><div class="sowing-line">${icon('calendar')} ${cycle?.sowing_date ? h('dashboard.sown', { date: dateLabel(cycle.sowing_date) }) : t('dashboard.sowingNotConfigured')}</div></div></div><div class="summary-side"><div class="mini-info"><div class="mini-label">${icon('shield')} ${h('dashboard.fieldDevice')}</div><div class="mini-value">${esc(deviceState)}</div></div><div class="mini-info"><div class="mini-label">${icon('clock')} ${h('dashboard.sensorData')}</div><div class="mini-value">${esc(sensorState)}</div>${latest ? `<small>${h('dashboard.measured', { time: stamp(latest.recorded_at) })}</small>` : ''}</div></div></section>`;
}

function irrigationCard() {
  const session = state.irrigationActive.data;
  const failedSession = session?.status === 'failed';
  const title = state.irrigationActive.status === 'loading' ? t('irrigation.checking') : state.irrigationActive.status === 'error' ? t('irrigation.unavailable') : session ? failedSession ? t('irrigation.pumpUnconfirmed') : t('irrigation.active') : t('irrigation.noActive');
  const path = session?.control_mode || state.irrigationControl.data?.control_mode;
  return `<section class="irrigation-card"><div class="irrigation-head"><div class="irrigation-title"><span class="irrigation-icon">${icon('drop')}</span><div><h2>${esc(title)}</h2><p>${esc(controlLabel(path))}</p></div></div><span class="future-badge">${icon('info')} ${session ? esc(valueLabel(session.status)) : t('irrigation.manual')}</span></div>${state.page === 'home' ? `<div class="irrigation-future-row"><button class="irrigation-link" data-page="irrigation">${h('irrigation.details')}</button></div>` : ''}</section>`;
}

function metricCard({ title, iconName, value, unit, source, tone = '' }) {
  return `<article class="metric-card"><div class="metric-heading">${icon(iconName)}<span>${esc(title)}</span></div><div class="metric-value ${tone}">${esc(value)}${!['—', '…'].includes(value) ? `<small>${esc(unit)}</small>` : ''}</div><div class="metric-caption">${esc(source)}</div></article>`;
}
function sensorCards() {
  const latest = latestSensor();
  const usable = latest?.sensor_valid === true;
  return `<section class="metric-grid" aria-label="${h('dashboard.fieldSensor')}">
    ${[
      [t('dashboard.soilMoisture'), 'drop', 'soil_moisture_pct', '%', ''],
      [t('dashboard.temperature'), 'temp', 'temperature_c', '°C', 'temperature-tone'],
      [t('dashboard.humidity'), 'humidity', 'humidity_pct', '%', 'humidity-tone'],
      [t('dashboard.flowRate'), 'wind', 'flow_rate_lpm', 'L/min', 'flow-tone'],
    ].map(([title, iconName, key, unit, tone]) => metricCard({
      title, iconName, unit, tone,
      value: state.sensors.status === 'loading' ? '…' : usable ? fmt(latest[key]) : '—',
      source: state.sensors.status === 'loading' ? t('dashboard.loadingSensor') : state.sensors.status === 'error' ? t('dashboard.sensorMissing') : latest && !usable ? t('dashboard.invalidReview') : !latest ? t('dashboard.noSensor') : number(latest[key]) == null ? t('dashboard.measurementUnavailable') : t('dashboard.sensorStamp', { time: stamp(latest.recorded_at) }),
    })).join('')}
  </section>`;
}

function decisionCard() {
  const session = state.irrigationActive.data;
  return `<section class="panel decision-panel"><div class="panel-heading"><span class="panel-icon green-icon">${icon('leaf')}</span><div><h2>${h('irrigation.whyStarted')}</h2></div></div><div class="neutral-explanation"><span class="neutral-symbol">${icon('info')}</span><div><strong>${session?.mode === 'MANUAL' ? session.status === 'started' ? t('irrigation.manualReason') : t('irrigation.manualUnconfirmed') : t('irrigation.noManual')}</strong><p>${h('irrigation.autoDisabled')}</p></div></div></section>`;
}

function weatherCard() {
  const data = state.weather.data;
  const expired = data && Date.parse(data.forecast_time) <= Date.now();
  return `<section class="panel weather-panel"><div class="panel-heading weather-heading"><div class="heading-left"><span class="weather-sun">${icon('cloud')}</span><div><h2>${h('weather.title')}</h2><p>${h('weather.stored')}</p></div></div><button class="icon-button" data-action="refresh-weather" aria-label="${h('weather.refresh')}" ${state.weatherRefreshing || !state.activeFieldId ? 'disabled' : ''} title="${h('weather.fetch')}">${state.weatherRefreshing ? `<span class="spinner"></span>` : icon('refresh')}</button></div>
    ${state.weatherRefreshError ? `<p class="state-note error-note" role="status">${h('weather.refreshFailed')}</p>` : ''}${state.weatherRefreshing ? box(pending(), t('weather.loading')) : box(state.weather, t('weather.loading'))}${sectionError(state.weather, t('weather.unavailable'))}${sectionEmpty(state.weather, t('weather.unavailable'))}
    ${state.weather.status === 'ready' && data ? `<div class="weather-highlight"><div class="weather-temp">${measure(data.temperature_c, '°C')}</div><div class="weather-details"><span>${h('weather.humidity')}: ${measure(data.humidity_pct, '%')}</span><span>${h('weather.wind')}: ${measure(data.wind_speed_mps, ' m/s')}</span><small>${h('weather.forecastFor', { time: stamp(data.forecast_time) })}</small></div><span class="sun-disc">${icon('cloud')}</span></div><div class="rain-row"><span>${h('weather.rainProbability')}: <strong>${measure(data.rain_probability_pct, '%')}</strong></span><span>${h('weather.rainfall')}: <strong>${measure(data.forecast_rainfall_mm, ' mm')}</strong></span></div>${expired ? `<p class="state-note">${h('weather.past')}</p>` : ''}<div class="weather-foot"><span>${esc(data.source || t('common.providerUnavailable'))}</span><span>${h('weather.lastRefresh', { time: stamp(data.fetched_at) })}</span></div>` : ''}
    <div class="attribution">${h('weather.attribution')} <a href="https://open-meteo.com/" target="_blank" rel="noreferrer">Open-Meteo</a></div></section>`;
}

function recentActivity() {
  const sensor = latestSensor();
  const weather = state.weather.data;
  return `<section class="panel activity-panel"><div class="panel-heading"><span class="panel-icon clock-icon">${icon('clock')}</span><div><h2>${h('activity.title')}</h2><p>${h('activity.subtitle')}</p></div></div>${state.sensors.status === 'loading' || state.weather.status === 'loading' ? `<div class="state-note"><span class="spinner"></span>${h('activity.checking')}</div>` : ''}${state.sensors.status === 'error' && state.weather.status === 'error' ? `<div class="state-note">${h('activity.empty')}</div>` : `<div class="activity-list">${sensor ? `<div class="activity-item"><span class="activity-dot sensor-dot"></span><div><strong>${h('activity.sensorReceived')}${sensor.sensor_valid ? '' : t('activity.reviewSuffix')}</strong><small>${esc(ago(sensor.recorded_at) || t('common.timeUnavailable'))}${!sensor.sensor_valid || sensor.soil_moisture_pct == null ? '' : h('activity.moisture', { value: fmt(sensor.soil_moisture_pct) })}</small></div></div>` : ''}${weather ? `<div class="activity-item"><span class="activity-dot weather-dot"></span><div><strong>${h('activity.forecastAvailable')}</strong><small>${h('activity.fetched', { time: ago(weather.fetched_at) || t('common.timeUnavailableLower') })}</small></div></div>` : ''}${!sensor && !weather && state.sensors.status !== 'loading' && state.weather.status !== 'loading' ? `<div class="state-note">${h('activity.empty')}</div>` : ''}</div>`}</section>`;
}
function devicePanel(technical = false) {
  const devices = state.devices.data || [];
  return `<section class="device-panel"><div class="device-status-head">${icon('shield')}<strong>${h('device.title')}</strong><span class="device-count">${state.devices.status === 'ready' ? h('device.count', { count: devices.length }) : ''}</span></div>${state.devices.status === 'loading' ? `<div class="device-item"><span class="spinner"></span>${h('device.loading')}</div>` : sectionError(state.devices, t('device.unavailable'))}${sectionEmpty(state.devices, t('device.empty'))}${state.devices.status === 'ready' && devices.length ? `<div class="device-list">${devices.map((device) => { const status = String(device.status || 'unknown'); return `<div class="device-item"><span class="device-led ${deviceAvailable(status) ? 'led-green' : 'led-neutral'}"></span><span><strong>${esc(device.device_name || device.device_type || t('device.fieldDevice'))}</strong><small>${esc(valueLabel(status))}${device.last_seen_at ? h('device.lastSeen', { time: ago(device.last_seen_at) }) : t('device.noReport')}</small>${technical ? `<small>${h('device.firmware')}: ${esc(device.firmware_version || t('common.notReported'))}</small>` : ''}</span></div>`; }).join('')}</div>` : ''}</section>`;
}
function homePage() {
  return `<main class="dashboard"><div class="page-intro"><div><p class="eyebrow">${h('dashboard.eyebrow')}</p><h1>${h('navigation.home')}</h1></div><span class="today-label">${icon('calendar')} ${new Date().toLocaleDateString(locale(), { weekday: 'long', day: 'numeric', month: 'long' })}</span></div>${statusBanner()}${fieldSummary()}${irrigationCard()}${sensorCards()}<div class="content-grid"><div class="content-primary">${weatherCard()}</div><div class="content-secondary">${recentActivity()}${devicePanel()}</div></div></main>`;
}

function controlPanel() {
  const pendingCommand = commandState();
  const session = state.irrigationActive.data;
  const knownEmpty = state.irrigationActive.status === 'empty';
  const startEnabled = state.irrigationControl.data?.start_available && knownEmpty && !pendingCommand.normal && !pendingCommand.emergency;
  const stopEnabled = !!session && !pendingCommand.normal && !pendingCommand.emergency;
  return `<div class="control-buttons"><button class="stop-control" data-action="stop-irrigation" ${stopEnabled ? '' : 'disabled'}>${icon('alert')} ${pendingCommand.normal === 'stop-irrigation' ? t('irrigation.stopping') : t('irrigation.stop')}</button><button class="start-control" data-action="start-irrigation" ${startEnabled ? '' : 'disabled'}>${icon('drop')} ${pendingCommand.normal === 'start-irrigation' ? t('irrigation.starting') : t('irrigation.start')}</button></div>`;
}

function currentProfile() {
  return state.agronomicProfile.data?.profile || (state.agronomicProfiles.data || []).find(item => item.code === activeCycle()?.agronomic_profile_code);
}
function savedVariety() {
  const cycle = activeCycle();
  const selected = state.agronomicProfile.data?.selected_variety;
  return selected?.display_name || selected?.code || cycle?.variety || null;
}
function agronomicNotice() {
  const notice = state.agronomicNotice;
  if (!notice || notice.field) return '';
  return `<p class="control-notice ${notice.error ? 'error-note' : ''}" role="${notice.error ? 'alert' : 'status'}">${esc(notice.apiMessage ? messageLabel(notice.apiMessage, 'crop.saveFailed') : t(notice.messageKey))}</p>`;
}

function cropPage() {
  const cycle = activeCycle(), soil = activeSoil(), age = cropAge(cycle?.sowing_date);
  const cycleContent = cycle ? details([
    [t('navigation.crop'), cycle.crop?.crop_name], [t('crop.variety'), savedVariety()],
    [t('crop.cycleStatus'), valueLabel(cycle.status)], [t('crop.sowingDate'), dateLabel(cycle.sowing_date)],
    [t('crop.age'), age == null ? null : t('crop.ageDays', { count: age })],
    [t('crop.regionalProfile'), cycle.regional_profile || cycle.agronomic_profile_code],
  ]) : '';
  return `<main class="dashboard subpage"><div class="page-intro"><div><p class="eyebrow">${h('crop.eyebrow')}</p><h1>${h('navigation.crop')}</h1></div></div>
    ${fieldSummary()}
    <section class="summary-card stage-hero"><div class="summary-main"><div class="summary-icon">${icon('crop')}</div><div><p class="eyebrow">${h('crop.growthUpper')}</p><h2>${h('crop.growthNotConfigured')}</h2><p class="support-copy">${h('crop.noValidatedStage')}</p></div></div></section>
    <div class="details-grid">
      ${agronomicSetup()}
      <section class="panel detail-card"><h2>${icon('crop')} ${h('crop.cycle')}</h2>${sectionContent(state.cycles, t('crop.cycle'), cycleContent, t('crop.noCycle'))}</section>
      <section class="panel detail-card"><h2>${icon('history')} ${h('crop.lifecycle')}</h2>${sectionContent(state.cycles, t('crop.cycle'), cycle ? `<div class="lifecycle-neutral" aria-hidden="true"><span class="lifecycle-marker"></span><span class="lifecycle-line"></span><span class="lifecycle-marker"></span></div><p class="support-copy">${h('crop.lifecyclePending')}</p>` : '', t('crop.lifecycleUnavailable'))}</section>
      <section class="panel detail-card"><h2>${icon('leaf')} ${h('crop.recommendations')}</h2><p class="support-copy">${h('crop.recommendationsPending')}</p></section>
      <section class="panel detail-card"><h2>${icon('calendar')} ${h('crop.nextStage')}</h2><p class="support-copy">${h('crop.nextNotConfigured')}</p></section>
    </div>
    <section class="environment-section"><div class="panel-heading"><div><h2>${h('crop.environment')}</h2><p>${h('crop.separateMeasurements')}</p></div></div>${sensorCards()}
      <div class="details-grid">${weatherCard()}<section class="panel detail-card"><h2>${icon('soil')} ${h('crop.soilProfile')}</h2>${sectionContent(state.soil, t('crop.soilProfile'), soil ? details([[t('crop.soilTexture'), valueLabel(soil.soil_texture)], [t('crop.sampleDate'), dateLabel(soil.sampled_at)]]) : '', t('crop.noSoil'))}</section></div>
    </section>
    <details class="panel technical-details"><summary>${h('crop.technical')}</summary><div class="details-grid"><div><h3>${h('crop.soilReference')}</h3>${sectionContent(state.soil, t('crop.soilProfile'), soil ? details([[t('crop.fieldCapacity'), number(soil.field_capacity) == null ? null : fmt(soil.field_capacity, 3)], [t('crop.wiltingPoint'), number(soil.wilting_point) == null ? null : fmt(soil.wilting_point, 3)], [t('crop.source'), soil.source_type], [t('crop.reference'), soil.source_reference], [t('crop.confidence'), soil.confidence_level]]) : '', t('crop.noSoil'))}</div><div><h3>${h('crop.weatherReference')}</h3>${sectionContent(state.weather, t('crop.weatherData'), state.weather.data ? details([[t('crop.forecastET0'), number(state.weather.data.eto_mm) == null ? null : `${fmt(state.weather.data.eto_mm)} mm`], [t('crop.forecastTime'), stamp(state.weather.data.forecast_time)], [t('crop.source'), state.weather.data.source]]) : '', t('weather.unavailable'))}</div></div><p class="support-copy">${h('crop.parametersPending')}</p></details>
  </main>`;
}

function historyPage() {
  const sensors = sensorHistory(state.history.sensors.data || []);
  const weather = upcomingForecasts(state.history.forecast.data || []);
  const sensorRows = sensors.length ? table([t('irrigation.measurementTime'), t('dashboard.soilMoisture'), t('dashboard.temperature'), t('dashboard.humidity'), t('history.flow'), t('history.validity')], sensors.map(r => [
    esc(stamp(r.recorded_at)), measure(r.soil_moisture_pct, '%'), measure(r.temperature_c, '°C'), measure(r.humidity_pct, '%'), measure(r.flow_rate_lpm, ' L/min'),
    `<span class="table-badge ${r.sensor_valid ? 'badge-valid' : 'badge-invalid'}">${r.sensor_valid ? t('history.valid') : t('history.invalid')}</span>`,
  ])) : '';
  const weatherRows = weather.length ? table([t('history.forecastDate'), t('history.weatherTemperature'), t('weather.humidity'), t('weather.rainProbability'), t('weather.rainfall'), 'ET0'], weather.map(w => [
    esc(stamp(w.forecast_time)), measure(w.temperature_c, '°C'), measure(w.humidity_pct, '%'), measure(w.rain_probability_pct, '%'), measure(w.forecast_rainfall_mm, ' mm'), measure(w.eto_mm, ' mm'),
  ])) : '';
  return `<main class="dashboard subpage"><div class="page-intro"><div><p class="eyebrow">${h('history.eyebrow')}</p><h1>${h('navigation.history')}</h1></div></div>
    <section class="panel history-panel"><div class="panel-heading"><div><h2>${h('history.sensorTitle')}</h2><p>${h('history.sensorDescription')}</p></div></div>${sectionContent(state.history.sensors, t('history.sensorSection'), sensorRows, t('dashboard.noSensorSentence'))}</section>
    <section class="panel history-panel"><div class="panel-heading"><div><h2>${h('weather.title')}</h2><p>${h('history.forecastDescription')}</p></div></div>${sectionContent(state.history.forecast, t('history.forecastSection'), weatherRows, t('history.noForecast'))}<p class="support-copy">${h('history.predictionNote')}</p><div class="attribution">${h('history.attribution')}</div></section>
    ${irrigationHistory()}
  </main>`;
}

function irrigationPage() {
  const session = state.irrigationActive.data;
  const measurementTime = session?.measurement_time;
  const sessionContent = session ? details([
    [t('irrigation.status'), session.status === 'failed' ? t('irrigation.commandUnconfirmed') : t('irrigation.manualSession')],
    [t('irrigation.modeLabel'), valueLabel(session.mode)], [t('irrigation.controlPath'), controlLabel(session.control_mode)],
    [t('irrigation.started'), stamp(session.started_at)], [t('irrigation.elapsed'), durationLabel(elapsedSeconds(session))],
    [t('irrigation.currentMoisture'), number(session.current_moisture_pct) == null ? t('common.unavailable') : `${fmt(session.current_moisture_pct)}%`],
    [t('irrigation.currentFlow'), number(session.current_flow_rate_lpm) == null ? t('common.unavailable') : `${fmt(session.current_flow_rate_lpm)} L/min`],
    [t('irrigation.measuredWater'), number(session.current_water_used_litres) == null ? t('common.unavailable') : `${fmt(session.current_water_used_litres)} L`],
    [t('irrigation.measurementTime'), measurementTime ? stamp(measurementTime) : t('common.unavailable')],
    ...(session.volume_measurement_time ? [[t('irrigation.meterBaseline'), stamp(session.volume_baseline_time)], [t('irrigation.latestMeter'), stamp(session.volume_measurement_time)]] : []),
  ]).replace(esc(durationLabel(elapsedSeconds(session))), `<span data-session-elapsed>${esc(durationLabel(elapsedSeconds(session)))}</span>`) : '';
  const control = state.irrigationControl.data;
  const reading = latestSensor();
  const flowValue = session ? session.current_flow_rate_lpm : reading?.sensor_valid ? reading.flow_rate_lpm : null;
  const flowTime = session ? session.measurement_time : reading?.recorded_at;
  return `<main class="dashboard subpage"><div class="page-intro"><div><p class="eyebrow">${h('irrigation.eyebrow')}</p><h1>${h('navigation.irrigation')}</h1></div><button class="icon-button" data-action="refresh-irrigation" aria-label="${h('irrigation.refresh')}" title="${h('irrigation.refresh')}">${icon('refresh')}</button></div>
    ${irrigationCard()}
    <div class="content-grid"><div class="content-primary">
      <section class="panel detail-card"><h2>${icon('drop')} ${h('irrigation.mode')}</h2>${modeSelector()}${sectionContent(state.irrigationControl, t('irrigation.availability'), control ? `<p class="control-notice">${esc(messageLabel(control.message, 'irrigation.notConfigured'))}</p>` : '', t('irrigation.notConfigured'))}</section>
      <section class="panel detail-card"><h2>${icon('clock')} ${h('irrigation.currentSession')}</h2>${sectionContent(state.irrigationActive, t('irrigation.state'), sessionContent, t('irrigation.noActive'))}${controlPanel()}<div class="session-emergency">${emergencyButton()}<small>${control?.control_mode === 'simulated' ? t('irrigation.simulationOnly') : t('irrigation.offRequest')}</small></div></section>
      ${decisionCard()}
    </div><div class="content-secondary">
      <section class="panel detail-card"><h2>${icon('shield')} ${h('irrigation.safetyFlow')}</h2>${devicePanel()}<p class="state-note">${number(flowValue) == null ? t('irrigation.flowUnavailable') : h('irrigation.flowAvailable', { flow: `${fmt(flowValue)} L/min`, time: stamp(flowTime) })}</p><p class="support-copy">${h('irrigation.flowThresholds')}</p></section>
      ${irrigationHistory(true)}
    </div></div></main>`;
}

function morePage() {
  const field = state.field.data;
  const farm = selectedFarm();
  const area = field?.area_value != null && field?.area_unit ? `${fmt(field.area_value)} ${field.area_unit}` : field?.area_m2 != null ? `${fmt(field.area_m2)} m²` : null;
  const weather = state.weather.data;
  return `<main class="dashboard subpage"><div class="page-intro"><div><p class="eyebrow">${h('farm.eyebrow')}</p><h1>${h('navigation.more')}</h1></div></div><div class="details-grid">
    <section class="panel detail-card"><h2>${icon('soil')} ${h('navigation.farmField')}</h2>${sectionContent(state.field, t('farm.fieldDetails'), field ? details([[t('farm.field'), field.field_name], [t('farm.area'), area], [t('farm.irrigationMethod'), valueLabel(field.irrigation_method)], [t('farm.latitude'), number(field.latitude) == null ? null : fmt(field.latitude, 5)], [t('farm.longitude'), number(field.longitude) == null ? null : fmt(field.longitude, 5)]]) : '', t('farm.noField'))}${sectionContent(state.farms, t('farm.farmDetails'), farm ? details([[t('farm.farm'), farm.farm_name], [t('farm.location'), farm.location_name]]) : '', t('farm.unavailable'))}</section>
    <section class="panel detail-card"><h2>${icon('shield')} ${h('farm.device')}</h2>${devicePanel(true)}</section>
    <section class="panel detail-card"><h2>${icon('cloud')} ${h('farm.weather')}</h2>${sectionContent(state.weather, t('crop.weatherData'), weather ? details([[t('farm.provider'), weather.source], [t('farm.lastRefresh'), stamp(weather.fetched_at)], [t('farm.storedForecast'), stamp(weather.forecast_time)]]) : '', t('weather.unavailable'))}</section>
  </div></main>`;
}


// The selected field determines its farm; saved records remain authoritative.


function selectedFarm() {
  return (state.farms.data || []).find(item => item.farm_id === state.field.data?.farm_id);
}

async function refreshWeather() {
  if (!state.activeFieldId || state.weatherRefreshing) return;
  const id = state.activeFieldId, version = fieldVersion;
  state.weatherRefreshing = true; state.weatherRefreshError = null; render();
  try {
    await api.refreshWeather(id);
    const latest = await api.weatherLatest(id);
    if (version !== fieldVersion) return;
    state.weather = resultState(latest);
    if (!latest) state.weatherRefreshError = 'no-forecast';
    if (state.page === 'history') await loadHistory();
  } catch (error) {
    if (version !== fieldVersion) return;
    state.weatherRefreshError = error.status === 404 ? 'no-forecast' : 'service';
  } finally {
    if (version === fieldVersion) { state.weatherRefreshing = false; render(); }
  }
}
function clearField() {
  ++fieldVersion; ++historyVersion; ++irrigationVersion; ++varietyVersion;
  state.agronomicDraft = null; state.agronomicNotice = null; state.agronomicSaving = false;
  state.activeFieldId = null;
  for (const key of ['field', 'cycles', 'soil', 'devices', 'sensors', 'weather', 'irrigationControl', 'irrigationActive', 'irrigationHistory', 'agronomicProfiles', 'agronomicProfile', 'varieties']) state[key] = empty(null);
  state.history = { sensors: empty(null), forecast: empty(null) };
}

function render() {
  const page = state.page === 'crop' ? cropPage() : state.page === 'history' ? historyPage() : state.page === 'irrigation' ? irrigationPage() : state.page === 'more' ? morePage() : homePage();
  root.innerHTML = `${header()}${commandNotice()}${page}<footer class="footer"><span><span class="footer-dot"></span>${h('app.footer')}</span><span>${h('app.measurements')}</span></footer>`;
}

function resultState(value) {
  return value == null || (Array.isArray(value) && value.length === 0) ? empty(null) : ready(value);
}
async function loadSection(key, request, transform, version) {
  try {
    const result = transform(await request());
    if (version !== fieldVersion) return;
    state[key] = resultState(result);
  } catch (error) {
    if (version !== fieldVersion) return;
    state[key] = failed(error);
  }
  render();
}
async function loadHistory() {
  const id = state.activeFieldId;
  const version = fieldVersion;
  const requestVersion = ++historyVersion;
  if (!id) {
    const unavailable = state.fields.status === 'error' ? failed(new Error(t('dashboard.fieldUnavailable'))) : empty(null);
    state.history = { sensors: unavailable, forecast: unavailable };
    render(); return;
  }
  state.history = { sensors: pending(), forecast: pending() }; render();
  async function load(key, request, transform) {
    try {
      const value = transform(await request());
      if (version !== fieldVersion || requestVersion !== historyVersion) return;
      state.history[key] = resultState(value);
    } catch (error) {
      if (version !== fieldVersion || requestVersion !== historyVersion) return;
      state.history[key] = failed(error);
    }
    render();
  }
  await Promise.all([
    load('sensors', () => api.sensorHistory(id, 50), sensorHistory),
    load('forecast', () => api.weatherForecast(id, 168), upcomingForecasts),
  ]);
}

function profileFor(sowing, irrigation) {
  return (state.agronomicProfiles.data || []).find(item => item.sowing_condition === sowing && item.irrigation_condition === irrigation);
}
function isWheatCycle() {
  return activeCycle()?.crop?.crop_name?.toLowerCase() === 'wheat';
}

async function loadVarieties(sowing, irrigation, version = fieldVersion) {
  const request = ++varietyVersion;
  if (!isWheatCycle()) { state.varieties = empty(null); render(); return; }
  state.varieties = pending(); render();
  try {
    const values = await api.wheatVarieties(sowing, irrigation);
    if (version !== fieldVersion || request !== varietyVersion) return;
    state.varieties = resultState(values);
  } catch (error) {
    if (version !== fieldVersion || request !== varietyVersion) return;
    state.varieties = failed(error);
  }
  render();
}
async function loadAgronomic() {
  const cycle = activeCycle(), version = fieldVersion;
  state.agronomicProfiles = cycle ? pending() : empty(null);
  state.agronomicProfile = cycle ? pending() : empty(null);
  state.varieties = cycle ? pending() : empty(null);
  render();
  if (!cycle) return;
  try {
    const profiles = await api.agronomicProfiles(cycle.crop?.crop_name || '');
    if (version !== fieldVersion) return;
    state.agronomicProfiles = resultState(profiles);
  } catch (error) {
    if (version !== fieldVersion) return;
    state.agronomicProfiles = failed(error);
  }
  try {
    const resolved = await api.agronomicProfile(cycle.crop_cycle_id);
    if (version !== fieldVersion) return;
    state.agronomicProfile = ready(resolved);
  } catch (error) {
    if (version !== fieldVersion) return;
    state.agronomicProfile = error.status === 409 ? empty(null) : failed(error);
  }
  const current = currentProfile();
  await loadVarieties(state.agronomicDraft?.sowing || current?.sowing_condition || 'timely', state.agronomicDraft?.irrigation || current?.irrigation_condition || 'irrigated', version);
}
function agronomicSetup() {
  const cycle = activeCycle();
  const heading = `<h2>${icon('crop')} ${h('crop.profile')}</h2><p class="support-copy">${h('crop.foundation')}</p>`;
  if (!cycle) return `<section class="panel detail-card agronomic-setup">${heading}${sectionContent(state.cycles, t('crop.cycle'), '', t('crop.noCycle'))}</section>`;
  if (state.agronomicProfiles.status === 'loading' || state.agronomicProfile.status === 'loading') return `<section class="panel detail-card agronomic-setup">${heading}${box(pending())}</section>`;
  if (state.agronomicProfiles.status === 'error' || state.agronomicProfile.status === 'error') return `<section class="panel detail-card agronomic-setup">${heading}<p class="error-note">${h('common.loadError')}</p><div class="profile-actions"><button data-action="retry-agronomic">${h('common.retry')}</button></div></section>`;
  if (!isWheatCycle() || state.agronomicProfiles.status === 'empty') return `<section class="panel detail-card agronomic-setup">${heading}<p class="support-copy">${h('crop.profileUnavailable')}</p></section>`;
  const current = currentProfile(), resolved = state.agronomicProfile.data;
  const sowing = state.agronomicDraft?.sowing || current?.sowing_condition || 'timely';
  const irrigation = state.agronomicDraft?.irrigation || current?.irrigation_condition || 'irrigated';
  const variety = state.agronomicDraft ? state.agronomicDraft.variety : resolved?.selected_variety?.code || cycle.variety || '';
  const age = cropAge(cycle.sowing_date);
  const source = current ? `<a href="${esc(current.source_url)}" target="_blank" rel="noreferrer">${esc(current.source_organization)}</a> ${esc(valueLabel(current.verification_status))}` : '';
  return `<section class="panel detail-card agronomic-setup">${heading}${agronomicNotice()}
    <form id="agronomic-form"><div class="setup-grid">
      <label>${h('navigation.crop')}<input value="${esc(cycle.crop?.crop_name)}" disabled></label>
      <label>${h('crop.region')}<input value="${h('crop.westernUP')}" disabled><small>${h('crop.zone')}</small></label>
      <label>${h('crop.sowingDate')}<input value="${esc(dateLabel(cycle.sowing_date))}" disabled></label>
      <label>${h('crop.irrigationCondition')}<select id="irrigation-condition" ${state.agronomicSaving ? 'disabled' : ''}><option value="irrigated" ${irrigation === 'irrigated' ? 'selected' : ''}>${h('crop.irrigated')}</option><option value="restricted_irrigation" ${irrigation === 'restricted_irrigation' ? 'selected' : ''}>${h('crop.restricted')}</option></select></label>
      <label>${h('crop.sowingCondition')}<select id="sowing-condition" ${state.agronomicSaving ? 'disabled' : ''}><option value="early" ${sowing === 'early' ? 'selected' : ''}>${h('crop.earlyHigh')}</option><option value="timely" ${sowing === 'timely' ? 'selected' : ''}>${h('crop.timely')}</option></select></label>
      <label>${h('crop.variety')}<input id="variety-code" list="compatible-varieties" value="${esc(variety)}" placeholder="${h('crop.unknownVariety')}" ${state.agronomicSaving || state.varieties.status === 'loading' ? 'disabled' : ''}><datalist id="compatible-varieties">${(state.varieties.data || []).map(item => `<option value="${esc(item.code)}">${esc(item.display_name)}</option>`).join('')}</datalist><small>${h('crop.leaveBlank')}</small></label>
    </div>${state.agronomicNotice?.field ? `<p class="error-note" role="alert">${h(state.agronomicNotice.messageKey)}</p>` : ''}
    ${state.varieties.status === 'loading' ? box(state.varieties) : state.varieties.status === 'error' ? `<p class="error-note">${h('common.loadError')}</p><button type="button" data-action="retry-varieties">${h('common.retry')}</button>` : ''}
    <div class="profile-actions"><button type="submit" ${state.agronomicSaving || ['loading', 'error'].includes(state.varieties.status) ? 'disabled' : ''}>${h(state.agronomicSaving ? 'crop.saving' : 'crop.save')}</button></div></form>
    ${resolved ? `<p class="support-copy">${esc(messageLabel(resolved.variety_message, 'messages.unknownVariety'))}</p>${details([[t('crop.productionProfile'), t('crop.production', { irrigation: valueLabel(current.irrigation_condition), sowing: valueLabel(current.sowing_condition) })], [t('crop.daysAfterSowing'), age == null ? null : fmt(age, 0)], [t('crop.growthStage'), t('common.notConfigured')]])}${resolved.selected_variety?.sowing_window_start ? `<p class="support-copy">${h('crop.sowingWindow')}: ${h('crop.window', { start: resolved.selected_variety.sowing_window_start, end: resolved.selected_variety.sowing_window_end })}${resolved.sowing_window_match === false ? h('crop.outsideWindow') : ''}</p>` : ''}${resolved.selected_variety?.first_irrigation_about_das ? `<p class="support-copy">${h('crop.firstIrrigation', { days: resolved.selected_variety.first_irrigation_about_das })}</p>` : ''}<p class="profile-source">${h('crop.source')}: ${source}</p>` : `<p class="support-copy">${h('crop.selectProfile')}</p>`}
  </section>`;
}

async function saveAgronomic(form) {
  const cycle = activeCycle();
  const version = fieldVersion;
  if (!cycle || state.agronomicSaving || !isWheatCycle() || ['loading', 'error'].includes(state.varieties.status)) return;
  const sowing = form.querySelector('#sowing-condition').value;
  const irrigation = form.querySelector('#irrigation-condition').value;
  const profile = profileFor(sowing, irrigation);
  const rawVariety = form.querySelector('#variety-code').value.trim();
  state.agronomicDraft = { sowing, irrigation, variety: rawVariety };
  const selected = (state.varieties.data || []).find(item => item.code.toLowerCase() === rawVariety.toLowerCase() || item.display_name.toLowerCase() === rawVariety.toLowerCase());
  if (!profile) {
    state.agronomicNotice = { error: true, messageKey: 'crop.profileUnavailable', field: 'production' }; render(); return;
  }
  if (rawVariety && !selected) {
    state.agronomicNotice = { error: true, messageKey: 'crop.chooseCompatible', field: 'variety' }; render(); return;
  }
  state.agronomicSaving = true; state.agronomicNotice = null; render();
  try {
    const resolved = await api.updateAgronomicProfile(cycle.crop_cycle_id, { profile_code: profile.code, variety_code: selected?.code || null });
    if (version !== fieldVersion) return;
    state.agronomicProfile = ready(resolved);
    state.cycles = ready((state.cycles.data || []).map(item => item.crop_cycle_id === cycle.crop_cycle_id ? { ...item, variety: resolved.selected_variety?.code || null, agronomic_profile_code: resolved.profile.code, regional_profile: resolved.profile.code } : item));
    state.agronomicDraft = null; state.page = 'crop';
    state.agronomicNotice = { error: false, messageKey: selected ? 'crop.savedVariety' : 'crop.savedRegional' };
  } catch (error) {
    if (version !== fieldVersion) return;
    state.agronomicNotice = { error: true, messageKey: 'crop.saveFailed', apiMessage: error.message };
  } finally {
    if (version === fieldVersion) { state.agronomicSaving = false; render(); }
  }
}

async function loadFieldData(id) {
  if (!id) return;
  const version = ++fieldVersion;
  state.agronomicDraft = null; state.agronomicNotice = null; state.agronomicSaving = false;
  ++varietyVersion;
  ++historyVersion;
  ++irrigationVersion;
  state.activeFieldId = id;
  for (const key of ['field', 'cycles', 'soil', 'devices', 'sensors', 'weather', 'irrigationControl', 'irrigationActive', 'irrigationHistory', 'agronomicProfiles', 'agronomicProfile', 'varieties']) state[key] = pending();
  state.history = { sensors: pending(), forecast: pending() };
  state.weatherRefreshing = false;
  state.weatherRefreshError = null;
  render();
  const identity = value => value;
  const tasks = [
    loadIrrigation(),
    loadSection('field', () => api.field(id), identity, version),
    loadSection('cycles', () => api.cropCycles(id), items => items.filter(item => item.status === 'active'), version),
    loadSection('soil', () => api.soilProfiles(id), items => items.filter(item => item.active), version),
    loadSection('devices', () => api.devices(id), identity, version),
    loadSection('sensors', () => api.sensorReadings(id, 5), sensorHistory, version),
    loadSection('weather', () => api.weatherLatest(id), identity, version),
  ];
  if (state.page === 'history') tasks.push(loadHistory());
  await Promise.all(tasks);
  if (version === fieldVersion) await loadAgronomic();
}

async function loadIrrigation() {
  const id = state.activeFieldId;
  const fieldRequest = fieldVersion;
  const version = ++irrigationVersion;
  if (!id) return;
  async function read(key, request) {
    try {
      const result = await request(id);
      if (version !== irrigationVersion || fieldRequest !== fieldVersion) return;
      state[key] = resultState(result);
    } catch (error) {
      if (version !== irrigationVersion || fieldRequest !== fieldVersion) return;
      state[key] = failed(error);
    }
    render();
  }
  await Promise.all([
    read('irrigationControl', api.irrigationControl),
    read('irrigationActive', api.irrigationActive),
    read('irrigationHistory', api.irrigationHistory),
  ]);
}
async function executeIrrigation(action) {
  const id = state.activeFieldId;
  if (!id) return;
  const commands = irrigationCommands.get(id) || {};
  irrigationCommands.set(id, commands);
  const emergency = action === 'emergency-stop';
  if (emergency ? commands.emergency : commands.normal || commands.emergency) return;
  if (action === 'start-irrigation' && (!state.irrigationControl.data?.start_available || state.irrigationActive.status !== 'empty')) return;
  if (action === 'stop-irrigation' && !state.irrigationActive.data) return;
  const priorNormal = commands.normalPromise;
  if (emergency) commands.emergency = true;
  else commands.normal = action;
  commands.notice = null;
  ++irrigationVersion; // Invalidate pre-command reads.
  render();
  const operation = (async () => {
    try {
      let result;
      if (emergency) {
        try { result = await api.emergencyStop(id); }
        catch (error) { if (!priorNormal) throw error; }
        // An in-flight START may arrive after the first OFF. Repeat OFF once it settles.
        if (priorNormal) { await priorNormal; result = await api.emergencyStop(id); }
        commands.notice = {
          error: !result.acknowledged,
          kind: 'emergency', controlMode: result.control_mode, apiMessage: result.message,
        };
      } else {
        result = await (action === 'start-irrigation' ? api.startIrrigation(id) : api.stopIrrigation(id));
        if (!commands.emergency) commands.notice = { error: false, kind: 'normal', controlMode: result.control_mode, action };
      }
    } catch (error) {
      commands.notice = { error: true, kind: 'error', conflict: error.status === 409, emergency, apiMessage: error.message };
    } finally {
      if (emergency) commands.emergency = false;
      else { commands.normal = null; commands.normalPromise = null; }
      if (state.activeFieldId === id) {
        await Promise.all([loadIrrigation(), loadSection('sensors', () => api.sensorReadings(id, 5), sensorHistory, fieldVersion)]);
        render();
      }
    }
  })();
  if (!emergency) commands.normalPromise = operation;
  await operation;
}

async function boot() {
  state.fields = pending(); state.farms = pending();
  render();
  const [health, fields, farms] = await Promise.allSettled([api.health(), api.fields(), api.farms()]);
  state.api = health.status === 'fulfilled' ? ready(health.value) : failed(health.reason);
  state.fields = fields.status === 'fulfilled' ? (fields.value.length ? ready(fields.value) : empty(null)) : failed(fields.reason);
  state.farms = farms.status === 'fulfilled' ? ready(farms.value || []) : failed(farms.reason);
  if (state.fields.status === 'ready') {
    const selected = state.fields.data.find(field => field.field_id === state.activeFieldId) || state.fields.data[0];
    await loadFieldData(selected.field_id);
  } else {
    clearField();
    const sectionState = state.fields.status === 'error' ? failed(new Error(t('dashboard.fieldRequired'))) : empty(null);
    for (const key of ['field', 'cycles', 'soil', 'devices', 'sensors', 'weather', 'irrigationControl', 'irrigationActive', 'irrigationHistory', 'agronomicProfiles', 'agronomicProfile', 'varieties']) state[key] = sectionState;
    state.history = { sensors: sectionState, forecast: sectionState };
    render();
  }
}

root.addEventListener('click', async (event) => {
  const target = event.target.closest('[data-page], [data-action]');
  if (!target) return;
  const page = target.dataset.page;
  const action = target.dataset.action;
  if (action === 'language') {
    const language = target.dataset.language;
    await changeLanguage(language);
    root.querySelector?.(`[data-action="language"][data-language="${language}"]`)?.focus();
    return;
  }
  if (action === 'retry-agronomic') { await loadAgronomic(); return; }
  if (action === 'retry-varieties') { const draft = state.agronomicDraft; await loadVarieties(draft?.sowing || currentProfile()?.sowing_condition || 'timely', draft?.irrigation || currentProfile()?.irrigation_condition || 'irrigated'); return; }
  if (page) {
    event.preventDefault(); state.page = page; state.moreOpen = false; render();
    await Promise.all([loadIrrigation(), ...(page === 'history' ? [loadHistory()] : [])]);
  }
  if (['start-irrigation', 'stop-irrigation', 'emergency-stop'].includes(action)) await executeIrrigation(action);
  if (action === 'refresh-irrigation') await loadIrrigation();
  if (action === 'more') { state.moreOpen = !state.moreOpen; render(); }
  if (action === 'refresh-weather') await refreshWeather();

});
root.addEventListener('input', (event) => {
  if (event.target.id === 'variety-code') {
    const form = event.target.form;
    state.agronomicDraft = { sowing: form.querySelector('#sowing-condition').value, irrigation: form.querySelector('#irrigation-condition').value, variety: event.target.value };
  }
});
root.addEventListener('submit', async (event) => {
  if (event.target.id === 'agronomic-form') { event.preventDefault(); await saveAgronomic(event.target); }
});
root.addEventListener('change', async (event) => {
  if (event.target.id === 'field-selector' && event.target.value) await loadFieldData(event.target.value);
  if (event.target.id === 'variety-code' && state.agronomicDraft) { state.agronomicDraft.variety = event.target.value; state.agronomicNotice = null; }
  if (['sowing-condition', 'irrigation-condition'].includes(event.target.id)) {
    const form = event.target.form;
    const sowing = form.querySelector('#sowing-condition').value;
    const irrigation = form.querySelector('#irrigation-condition').value;
    state.agronomicDraft = { sowing, irrigation, variety: form.querySelector('#variety-code').value };
    state.agronomicNotice = null;
    await loadVarieties(sowing, irrigation);
  }
});

// Updates display text only; no background controller commands or decisions.
if (typeof window !== 'undefined') window.setInterval(() => {
  const label = root.querySelector('[data-session-elapsed]');
  if (label && state.irrigationActive.data) label.textContent = durationLabel(elapsedSeconds(state.irrigationActive.data));
}, 1000);

i18n.on('languageChanged', render);
boot();
