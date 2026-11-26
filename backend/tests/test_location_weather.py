"""Mock provider calls; persist and query weather only in disposable PostgreSQL schemas."""
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
from sqlalchemy import select

import test_agronomic_profiles as fixtures
from app.models import CropCycle, Farm, Field, WeatherRecord
from app.db import seed as demo_seed


def response(payload, status=200):
    return httpx.Response(status, json=payload, request=httpx.Request('GET', 'https://provider.test/'))


def forecast_payload():
    times = [(datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) + timedelta(hours=i)).strftime('%Y-%m-%dT%H:%M') for i in range(3)]
    hourly = {name: [value] * 3 for name, value in {
        'temperature_2m': 25, 'relative_humidity_2m': 60, 'precipitation': 0,
        'precipitation_probability': 10, 'wind_speed_10m': 2, 'shortwave_radiation': 100,
        'et0_fao_evapotranspiration': .1, 'weather_code': 0,
    }.items()}
    hourly['time'] = times
    days = list(dict.fromkeys(value[:10] for value in times))
    return {'timezone': 'UTC', 'hourly': hourly, 'daily': {'time': days, 'temperature_2m_max': [30] * len(days), 'temperature_2m_min': [18] * len(days)}}


class LocationWeatherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.AgronomicProfileTests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        fixtures.AgronomicProfileTests.tearDownClass.__func__(cls)

    def setUp(self):
        fixtures.AgronomicProfileTests.setUp(self)
        with self.Session() as db:
            cycle = db.get(CropCycle, self.cycle_id)
            self.field_id = cycle.field_id
            self.farm_id = db.get(Field, cycle.field_id).farm_id

    def tearDown(self):
        self.client.close()

    def configure(self, lat=28.367, lon=79.430):
        return self.client.put(f'/farms/{self.farm_id}', json={'farm_name': 'Farm', 'location_name': 'Bareilly, Uttar Pradesh, India', 'latitude': lat, 'longitude': lon})

    def refresh(self, payload=None):
        with patch('httpx.AsyncClient.get', new_callable=AsyncMock, return_value=response(payload or forecast_payload())) as request:
            result = self.client.post(f'/fields/{self.field_id}/weather/refresh')
        return result, request

    def test_search_multiple_matches_and_provider_filters(self):
        rows = [{'name': 'Bareilly', 'admin1': 'Uttar Pradesh', 'admin2': 'Bareilly', 'country': 'India', 'country_code': 'IN', 'latitude': 28.367, 'longitude': 79.430},
                {'name': 'Bareilly', 'admin1': 'Other State', 'country': 'India', 'country_code': 'IN', 'latitude': 27, 'longitude': 78}]
        with patch('httpx.AsyncClient.get', new_callable=AsyncMock, return_value=response({'results': rows})) as request:
            data = self.client.get('/locations/search', params={'q': 'Bareilly, Uttar Pradesh', 'language': 'hi'}).json()
        self.assertEqual(len(data), 2)
        self.assertIn('Uttar Pradesh', data[0]['label'])
        self.assertEqual(request.call_args.kwargs['params']['countryCode'], 'IN')
        self.assertEqual(request.call_args.kwargs['params']['language'], 'hi')
        self.assertEqual(request.call_args.kwargs['params']['name'], 'Bareilly, Uttar Pradesh')

    def test_search_empty_failure_and_invalid_coordinates(self):
        for payload in [{}, {'results': []}, {'results': [{'name': 'Invalid', 'latitude': 100, 'longitude': 50, 'country_code': 'IN'}]}]:
            with patch('httpx.AsyncClient.get', new_callable=AsyncMock, return_value=response(payload)):
                self.assertEqual(self.client.get('/locations/search?q=Village').json(), [])
        with patch('httpx.AsyncClient.get', new_callable=AsyncMock, side_effect=httpx.ConnectError('offline')):
            self.assertEqual(self.client.get('/locations/search?q=Village').status_code, 503)
        with patch('httpx.AsyncClient.get', new_callable=AsyncMock, return_value=response({}, 500)):
            self.assertEqual(self.client.get('/locations/search?q=Village').status_code, 503)
        self.assertEqual(self.client.get('/locations/search?q=A').status_code, 422)

    def test_coordinates_persist_without_changing_owner_or_field(self):
        before = self.client.get(f'/farms/{self.farm_id}').json()
        self.assertEqual(self.configure().status_code, 200)
        saved = self.client.get(f'/farms/{self.farm_id}').json()
        self.assertAlmostEqual(float(saved['latitude']), 28.367)
        self.assertEqual(saved['user_id'], before['user_id'])
        self.assertIsNone(self.client.get(f'/fields/{self.field_id}').json()['latitude'])
        self.client.put(f'/farms/{self.farm_id}', json={'farm_name': 'Renamed', 'location_name': saved['location_name']})
        self.assertAlmostEqual(float(self.client.get(f'/farms/{self.farm_id}').json()['latitude']), 28.367)

    def test_coordinate_range_and_pair_validation(self):
        for extra in [{'latitude': 91, 'longitude': 79}, {'latitude': 28, 'longitude': 181}, {'latitude': 28}, {'latitude': None, 'longitude': 79}]:
            result = self.client.put(f'/farms/{self.farm_id}', json={'farm_name': 'Invalid', **extra})
            self.assertEqual(result.status_code, 422, result.text)
        self.assertIsNone(self.client.get(f'/farms/{self.farm_id}').json()['latitude'])

    def test_missing_location_does_not_call_provider(self):
        with patch('httpx.AsyncClient.get', new_callable=AsyncMock) as request:
            self.assertEqual(self.client.get(f'/fields/{self.field_id}/weather/location').json()['status'], 'missing')
            self.assertEqual(self.client.post(f'/fields/{self.field_id}/weather/refresh').status_code, 422)
            self.assertIsNone(self.client.get(f'/fields/{self.field_id}/weather/latest').json())
            self.assertEqual(self.client.get(f'/fields/{self.field_id}/weather/forecast').json(), [])
            request.assert_not_called()

    def test_field_coordinates_override_farm_without_mixing_pairs(self):
        self.configure()
        with self.Session.begin() as db:
            field = db.get(Field, self.field_id)
            field.latitude, field.longitude = 29, 77
        location = self.client.get(f'/fields/{self.field_id}/weather/location').json()
        self.assertEqual(location['source'], 'field')
        result, request = self.refresh()
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(request.call_args.kwargs['params']['latitude'], 29)
        self.assertEqual(request.call_args.kwargs['params']['longitude'], 77)

    def test_farm_fallback_and_cached_read_have_correct_field_and_coordinates(self):
        self.configure()
        location = self.client.get(f'/fields/{self.field_id}/weather/location').json()
        self.assertEqual(location['source'], 'farm')
        self.assertTrue(location['approximate'])
        result, request = self.refresh()
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(request.call_args.kwargs['params']['latitude'], 28.367)
        with patch('httpx.AsyncClient.get', new_callable=AsyncMock) as cached_request:
            row = self.client.get(f'/fields/{self.field_id}/weather/latest').json()
            self.assertEqual(row['field_id'], str(self.field_id))
            self.assertEqual(float(row['request_longitude']), 79.430)
            self.assertEqual(float(row['temperature_c']), 25)
            self.assertIsNone(row['actual_rainfall_mm'])
            self.assertEqual(float(row['solar_radiation_mj_m2']), .36)
            cached_request.assert_not_called()

    def test_partial_field_coordinates_use_complete_farm_pair(self):
        self.configure()
        with self.Session.begin() as db:
            db.get(Field, self.field_id).latitude = 29
        location = self.client.get(f'/fields/{self.field_id}/weather/location').json()
        self.assertEqual(location['source'], 'farm')
        self.assertEqual(float(location['latitude']), 28.367)
        self.assertEqual(float(location['longitude']), 79.430)

    def test_location_edit_hides_old_forecast_without_deleting_history(self):
        self.configure(); self.refresh()
        self.configure(27, 78)
        self.assertIsNone(self.client.get(f'/fields/{self.field_id}/weather/latest').json())
        self.assertEqual(self.client.get(f'/fields/{self.field_id}/weather/forecast').json(), [])
        self.assertEqual(len(self.client.get(f'/fields/{self.field_id}/weather/history').json()), 3)
        self.refresh()
        self.assertEqual(float(self.client.get(f'/fields/{self.field_id}/weather/latest').json()['request_latitude']), 27)

    def test_unknown_legacy_provenance_is_retained_but_not_used_for_current_weather(self):
        self.configure()
        with self.Session.begin() as db:
            db.add(WeatherRecord(field_id=self.field_id, forecast_time=datetime.now(timezone.utc), source='open-meteo', temperature_c=99))
        self.assertIsNone(self.client.get(f'/fields/{self.field_id}/weather/latest').json())
        self.assertEqual(len(self.client.get(f'/fields/{self.field_id}/weather/history').json()), 1)

    def test_switching_fields_never_shares_cached_forecasts(self):
        self.configure(); self.refresh()
        with self.Session.begin() as db:
            other = Field(farm_id=self.farm_id, field_name='Other Field'); db.add(other); db.flush(); other_id = other.field_id
        self.assertIsNone(self.client.get(f'/fields/{other_id}/weather/latest').json())
        self.assertEqual(self.client.get(f'/fields/{other_id}/weather/forecast').json(), [])

    def test_provider_failure_preserves_cached_forecast(self):
        self.configure(); self.refresh()
        for error in [httpx.ConnectError('offline'), httpx.ReadTimeout('timeout')]:
            with patch('httpx.AsyncClient.get', new_callable=AsyncMock, side_effect=error):
                self.assertIn(self.client.post(f'/fields/{self.field_id}/weather/refresh').status_code, [502, 503])
        self.assertIsNotNone(self.client.get(f'/fields/{self.field_id}/weather/latest').json())
        with patch('httpx.AsyncClient.get', new_callable=AsyncMock, return_value=response({}, 500)):
            self.assertEqual(self.client.post(f'/fields/{self.field_id}/weather/refresh').status_code, 502)

    def test_no_forecast_is_distinct_from_service_failure(self):
        self.configure()
        result, _ = self.refresh({'hourly': {'time': []}})
        self.assertEqual(result.status_code, 404)
        self.assertIn('selected location', result.json()['detail'])
        payload = forecast_payload()
        for name in payload['hourly']:
            if name != 'time':
                payload['hourly'][name] = [None] * 3
        result, _ = self.refresh(payload)
        self.assertEqual(result.status_code, 404)

    def test_existing_seed_is_not_changed_by_reads(self):
        email = f'{uuid4()}@example.test'
        with patch.object(demo_seed, 'SessionLocal', self.Session), patch.dict(os.environ, {'DEMO_USER_EMAIL': email, 'DEMO_USER_PASSWORD': 'test-only'}):
            demo_seed.seed()
        with self.Session() as db:
            farm = db.scalar(select(Farm).where(Farm.farm_name == 'Demo Farm', Farm.user_id != self.client.get(f'/farms/{self.farm_id}').json()['user_id']))
            field = db.scalar(select(Field).where(Field.farm_id == farm.farm_id))
            farm_id, field_id = farm.farm_id, field.field_id
            before = self.client.get(f'/farms/{farm_id}').json()
        self.assertEqual(self.client.get(f'/fields/{field_id}/weather/location').json()['status'], 'missing')
        self.client.get(f'/fields/{field_id}/weather/latest')
        self.assertEqual(self.client.get(f'/farms/{farm_id}').json(), before)
