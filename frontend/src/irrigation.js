import { t } from './i18n.js';

// All state transitions come from the API; elapsed time is presentation only.
export function elapsedSeconds(session, now = Date.now()) {
  if (!session) return null;
  if (session.ended_at) return session.duration_seconds;
  const start = Date.parse(session.started_at);
  return Number.isFinite(start) ? Math.max(0, Math.floor((now - start) / 1000)) : null;
}

export function durationLabel(seconds) {
  if (seconds == null || !Number.isFinite(Number(seconds))) return t('common.unavailable');
  const total = Math.max(0, Math.floor(Number(seconds)));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor(total % 3600 / 60);
  return t(hours ? 'common.durationHours' : 'common.duration', { hours, minutes, seconds: total % 60 });
}

export function controlLabel(mode) {
  return t(mode === 'simulated' ? 'irrigation.simulation' : mode === 'hardware' ? 'irrigation.hardware' : 'irrigation.controlUnknown');
}
