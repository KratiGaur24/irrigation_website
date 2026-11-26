"""Journey persistence tests run only inside the existing disposable schema fixture."""
import os
import unittest
from unittest.mock import patch
from uuid import uuid4

import test_agronomic_profiles as fixtures
from app.models import CropCycle, Farm, Field, User


class FarmerJourneyTests(unittest.TestCase):
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
            field = db.get(Field, cycle.field_id)
            farm = db.get(Farm, field.farm_id)
            self.farm_id, self.user_id = farm.farm_id, farm.user_id

    def tearDown(self):
        self.client.close()

    def test_create_farm_field_crop_and_read_back(self):
        farm = self.client.post('/farms', json={'user_id': str(self.user_id), 'farm_name': 'New Farm'})
        self.assertEqual(farm.status_code, 201, farm.text)
        field = self.client.post('/fields', json={'farm_id': farm.json()['farm_id'], 'field_name': 'New Field'})
        self.assertEqual(field.status_code, 201, field.text)
        crop_id = self.client.get('/crops').json()[0]['crop_id']
        cycle = self.client.post('/crop-cycles', json={'field_id': field.json()['field_id'], 'crop_id': crop_id, 'sowing_date': '2026-10-01', 'status': 'active'})
        self.assertEqual(cycle.status_code, 201, cycle.text)
        persisted = self.client.get(f"/fields/{field.json()['field_id']}/crop-cycles").json()
        self.assertEqual(persisted[0]['crop_cycle_id'], cycle.json()['crop_cycle_id'])

    def test_farm_edit_preserves_owner_coordinates_and_field(self):
        with self.Session.begin() as db:
            farm = db.get(Farm, self.farm_id)
            farm.latitude, farm.longitude = 29, 77
        response = self.client.put(f'/farms/{self.farm_id}', json={'farm_name': 'Updated Farm', 'location_name': 'Village'})
        self.assertEqual(response.status_code, 200, response.text)
        data = self.client.get(f'/farms/{self.farm_id}').json()
        self.assertEqual(data['user_id'], str(self.user_id))
        self.assertEqual(float(data['latitude']), 29)
        self.assertEqual(len(self.client.get(f'/farms/{self.farm_id}/fields').json()), 1)
        self.assertEqual(self.client.put(f'/farms/{self.farm_id}', json={'farm_name': ' ', 'user_id': str(uuid4())}).status_code, 422)

    def test_crop_edit_preserves_profile_variety_and_stage(self):
        with self.Session.begin() as db:
            cycle = db.get(CropCycle, self.cycle_id)
            cycle.variety, cycle.regional_profile, cycle.stage_override = 'HD 3226', 'Western UP', 'retained'
        response = self.client.put(f'/crop-cycles/{self.cycle_id}', json={'sowing_date': '2025-11-12', 'expected_harvest_date': '2026-04-01'})
        self.assertEqual(response.status_code, 200, response.text)
        data = self.client.get(f'/crop-cycles/{self.cycle_id}').json()
        self.assertEqual(data['variety'], 'HD 3226')
        self.assertEqual(data['regional_profile'], 'Western UP')
        self.assertEqual(data['stage_override'], 'retained')
        self.assertEqual(data['status'], 'active')

    def test_invalid_dates_do_not_change_saved_crop(self):
        with self.Session.begin() as db:
            db.get(CropCycle, self.cycle_id).actual_harvest_date = fixtures.date(2026, 4, 1)
        for payload in [
            {'sowing_date': '2026-10-01', 'expected_harvest_date': '2026-09-01'},
            {'sowing_date': '2026-10-01'},
            {'sowing_date': '2025-11-12', 'stage_override': 'changed'},
        ]:
            self.assertEqual(self.client.put(f'/crop-cycles/{self.cycle_id}', json=payload).status_code, 422)
        self.assertEqual(self.client.get(f'/crop-cycles/{self.cycle_id}').json()['sowing_date'], '2025-11-10')

    def test_demo_context_exposes_only_existing_demo_identity(self):
        email = f'{uuid4()}@example.test'
        with self.Session.begin() as db:
            db.get(User, self.user_id).email = email
        with patch.dict(os.environ, {'DEMO_USER_EMAIL': email}):
            response = self.client.get('/demo-context')
            self.assertEqual(response.json(), {'mode': 'demo', 'user_id': str(self.user_id)})
        with patch.dict(os.environ, {'DEMO_USER_EMAIL': 'missing@example.test'}):
            self.assertEqual(self.client.get('/demo-context').status_code, 409)

    def test_missing_edit_targets_return_404(self):
        self.assertEqual(self.client.put(f'/farms/{uuid4()}', json={'farm_name': 'Missing'}).status_code, 404)
        self.assertEqual(self.client.put(f'/crop-cycles/{uuid4()}', json={'sowing_date': '2026-10-01'}).status_code, 404)
