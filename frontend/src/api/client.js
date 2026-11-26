/** @typedef {import('./types.js').Farm} Farm */
/** @typedef {import('./types.js').Field} Field */
/** @typedef {import('./types.js').CropCycle} CropCycle */
/** @typedef {import('./types.js').SoilProfile} SoilProfile */
/** @typedef {import('./types.js').Device} Device */
/** @typedef {import('./types.js').SensorReading} SensorReading */
/** @typedef {import('./types.js').WeatherRecord} WeatherRecord */
const API_BASE_URL = (import.meta.env?.VITE_API_BASE_URL || window.APP_CONFIG?.apiBaseUrl || `http://${window.location.hostname || '127.0.0.1'}:8000`).replace(/\/$/, '');

/** @template T @param {string} path @returns {Promise<T>} */
export async function apiGet(path) {
  const response = await fetch(`${API_BASE_URL}${path}`, { headers: { Accept: 'application/json' } });
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    const error = new Error(typeof detail?.detail === 'string' ? detail.detail : `Request failed (${response.status})`);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

export async function apiPut(path, body) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'PUT', headers: { Accept: 'application/json', 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    const error = new Error(typeof detail?.detail === 'string' ? detail.detail : `Request failed (${response.status})`);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

/** @template T @param {string} path @returns {Promise<T>} */
export async function apiPost(path, body) {
  const response = await fetch(`${API_BASE_URL}${path}`, { method: 'POST', headers: { Accept: 'application/json', ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) }, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    const error = new Error(typeof detail?.detail === 'string' ? detail.detail : `Request failed (${response.status})`);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

export const api = {
  agronomicProfiles: (crop = 'Wheat') => apiGet(`/agronomic-profiles?crop=${encodeURIComponent(crop)}&region=Western%20Uttar%20Pradesh&zone=NWPZ`),
  wheatVarieties: (sowing, irrigation) => apiGet(`/wheat-varieties?zone=NWPZ&sowing_condition=${encodeURIComponent(sowing)}&irrigation_condition=${encodeURIComponent(irrigation)}`),
  agronomicProfile: id => apiGet(`/crop-cycles/${encodeURIComponent(id)}/agronomic-profile`),
  updateAgronomicProfile: (id, body) => apiPut(`/crop-cycles/${encodeURIComponent(id)}/agronomic-profile`, body),
  /** @returns {Promise<import('./types.js').IrrigationControl>} */ irrigationControl: id => apiGet(`/fields/${encodeURIComponent(id)}/irrigation/control`),
  /** @returns {Promise<import('./types.js').IrrigationEvent|null>} */ irrigationActive: id => apiGet(`/fields/${encodeURIComponent(id)}/irrigation/active`),
  /** @returns {Promise<import('./types.js').IrrigationEvent[]>} */ irrigationHistory: (id, limit = 50) => apiGet(`/fields/${encodeURIComponent(id)}/irrigation/history?limit=${limit}`),
  /** @returns {Promise<import('./types.js').IrrigationEvent>} */ startIrrigation: id => apiPost(`/fields/${encodeURIComponent(id)}/irrigation/start`),
  /** @returns {Promise<import('./types.js').IrrigationEvent>} */ stopIrrigation: id => apiPost(`/fields/${encodeURIComponent(id)}/irrigation/stop`),
  /** @returns {Promise<import('./types.js').EmergencyResult>} */ emergencyStop: id => apiPost(`/fields/${encodeURIComponent(id)}/irrigation/emergency-stop`),
  /** @returns {Promise<{status:string}>} */ health: () => apiGet('/health'),
  /** @returns {Promise<Field[]>} */ fields: () => apiGet('/fields'),
  /** @returns {Promise<Farm[]>} */ farms: () => apiGet('/farms'),
  /** @param {string} id @returns {Promise<Field>} */ field: (id) => apiGet(`/fields/${encodeURIComponent(id)}`),
  /** @param {string} id @returns {Promise<CropCycle[]>} */ cropCycles: (id) => apiGet(`/fields/${encodeURIComponent(id)}/crop-cycles`),
  /** @param {string} id @returns {Promise<SoilProfile[]>} */ soilProfiles: (id) => apiGet(`/fields/${encodeURIComponent(id)}/soil-profiles`),
  /** @param {string} id @returns {Promise<Device[]>} */ devices: (id) => apiGet(`/fields/${encodeURIComponent(id)}/devices`),
  /** @param {string} id @param {number} [limit] @returns {Promise<SensorReading[]>} */ sensorReadings: (id, limit = 5) => apiGet(`/fields/${encodeURIComponent(id)}/sensor-readings?limit=${limit}&to=${encodeURIComponent(new Date().toISOString())}`),
  /** @param {string} id @returns {Promise<WeatherRecord|null>} */ weatherLatest: (id) => apiGet(`/fields/${encodeURIComponent(id)}/weather/latest`),
  /** Stored future forecasts, not observed weather history.
   * @param {string} id @param {number} [limit] @returns {Promise<WeatherRecord[]>} */ weatherForecast: (id, limit = 168) => apiGet(`/fields/${encodeURIComponent(id)}/weather/forecast?limit=${limit}`),
  /** @param {string} id @param {number} [limit] @returns {Promise<SensorReading[]>} */ sensorHistory: (id, limit = 50) => apiGet(`/fields/${encodeURIComponent(id)}/sensor-readings?limit=${limit}&to=${encodeURIComponent(new Date().toISOString())}`),
  /** @param {string} id @returns {Promise<object>} */ refreshWeather: (id) => apiPost(`/fields/${encodeURIComponent(id)}/weather/refresh`),
};
