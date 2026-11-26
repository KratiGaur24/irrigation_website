// Presentation only: these helpers do not infer agronomic or pump decisions.
export function sensorHistory(rows = [], now = Date.now()) {
  return rows.filter(row => Date.parse(row.recorded_at) <= now)
    .sort((a, b) => Date.parse(b.recorded_at) - Date.parse(a.recorded_at));
}

export function upcomingForecasts(rows = [], now = Date.now()) {
  const snapshots = new Map();
  for (const row of rows) {
    const time = Date.parse(row.forecast_time);
    if (!(time > now)) continue;
    const previous = snapshots.get(time);
    if (!previous || Date.parse(row.fetched_at) > Date.parse(previous.fetched_at)) snapshots.set(time, row);
  }
  return [...snapshots.values()].sort((a, b) => Date.parse(a.forecast_time) - Date.parse(b.forecast_time));
}

export function cropAge(sowingDate, today = new Date()) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(sowingDate || '')) return null;
  const sowing = Date.parse(`${sowingDate}T00:00:00Z`);
  const current = Date.UTC(today.getFullYear(), today.getMonth(), today.getDate());
  const days = Math.floor((current - sowing) / 86400000);
  return Number.isFinite(days) && days >= 0 ? days : null;
}

export function deviceAvailable(status) {
  return ['online', 'active', 'connected'].includes(String(status || '').toLowerCase().trim());
}
