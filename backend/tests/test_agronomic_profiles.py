"""Phase 2 integration tests use a disposable PostgreSQL schema."""
import importlib.util
import unittest
from datetime import date
from pathlib import Path
from uuid import uuid4
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.dependencies import get_db
from app.main import app
from app.db.seed_agronomic import seed_catalogue, TIMELY, EARLY, RESTRICTED
from app.models import User, Farm, Field, Crop, CropCycle, CropStageParameter
from app.services import agronomic_profile_service as service


class AgronomicProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = 'test_agronomic_' + uuid4().hex
        cls.admin = create_engine(settings.database_url)
        with cls.admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{cls.schema}"'))
        cls.engine = create_engine(settings.database_url, connect_args={'options': f'-csearch_path={cls.schema},public'})
        cls.Session = sessionmaker(cls.engine, expire_on_commit=False, autoflush=False)
        with cls.engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                for path in sorted(Path('alembic/versions').glob('*.py')):
                    spec = importlib.util.spec_from_file_location(path.stem, path)
                    migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration); migration.upgrade()
        with cls.Session.begin() as db:
            seed_catalogue(db)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear(); cls.engine.dispose()
        assert cls.schema.startswith('test_agronomic_') and len(cls.schema) == len('test_agronomic_') + 32
        with cls.admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{cls.schema}" CASCADE'))
        cls.admin.dispose()

    def setUp(self):
        def test_db():
            with self.Session() as db: yield db
        app.dependency_overrides[get_db] = test_db
        self.client = TestClient(app)
        with self.Session.begin() as db:
            crop = db.scalar(select(Crop).where(Crop.crop_name == 'Wheat'))
            user = User(name='Profile test', email=f'{uuid4()}@example.test', password_hash='test')
            db.add(user); db.flush()
            farm = Farm(user_id=user.user_id, farm_name='Test farm'); db.add(farm); db.flush()
            field = Field(farm_id=farm.farm_id, field_name='Test field'); db.add(field); db.flush()
            cycle = CropCycle(field_id=field.field_id, crop_id=crop.crop_id, sowing_date=date(2025, 11, 10), status='active')
            db.add(cycle); db.flush(); self.cycle_id = cycle.crop_cycle_id

    def tearDown(self):
        self.client.close()

    def select(self, profile=TIMELY, variety=None):
        return self.client.put(f'/crop-cycles/{self.cycle_id}/agronomic-profile', json={'profile_code': profile, 'variety_code': variety})

    def test_case_a_hd3226_is_compatible_and_source_backed(self):
        response = self.select(variety='HD 3226')
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data['profile_specificity'], 'variety')
        self.assertEqual(data['profile']['region'], 'Western Uttar Pradesh')
        self.assertEqual(data['profile']['zone_code'], 'NWPZ')
        self.assertEqual(data['selected_variety']['sowing_window_start'], '11-05')
        self.assertEqual(data['selected_variety']['sowing_window_end'], '11-25')
        self.assertEqual(data['selected_variety']['first_irrigation_about_das'], 21)
        self.assertTrue(data['sowing_window_match'])

    def test_case_b_unknown_variety_resolves_regionally_and_persists_null(self):
        data = self.select(variety=None).json()
        self.assertEqual(data['profile_specificity'], 'regional')
        self.assertIsNone(data['selected_variety'])
        with self.Session() as db:
            self.assertIsNone(db.get(CropCycle, self.cycle_id).variety)

    def test_case_c_incompatible_variety_is_rejected_without_overwrite(self):
        self.assertEqual(self.select(variety='DBW 296').status_code, 409)
        with self.Session() as db:
            cycle = db.get(CropCycle, self.cycle_id)
            self.assertIsNone(cycle.variety)
            self.assertIsNone(cycle.agronomic_profile_code)

    def test_case_d_das_uses_supplied_agricultural_date(self):
        self.select(variety=None)
        with self.Session() as db:
            data = service.resolve(db, self.cycle_id, today=date(2025, 11, 25))
        self.assertEqual(data.days_after_sowing, 15)
        self.assertEqual(data.agricultural_date, date(2025, 11, 25))

    def test_case_e_stage_remains_unconfigured_without_verified_timing(self):
        data = self.select(variety='HD 3226').json()
        self.assertIsNone(data['current_stage'])
        self.assertEqual(data['stage_status'], 'not_configured')
        with self.Session() as db:
            self.assertEqual(len(list(db.scalars(select(CropStageParameter)))), 0)

    def test_filtered_catalogue_and_official_seed_scope(self):
        timely = self.client.get('/wheat-varieties?zone=NWPZ&sowing_condition=timely&irrigation_condition=irrigated').json()
        self.assertEqual({item['code'] for item in timely}, {'DBW 222', 'DBW 187', 'HD 3226'})
        restricted = self.client.get('/wheat-varieties?zone=NWPZ&sowing_condition=timely&irrigation_condition=restricted_irrigation').json()
        self.assertEqual([item['code'] for item in restricted], ['DBW 296'])
        profiles = self.client.get('/agronomic-profiles?zone=NWPZ').json()
        self.assertEqual({p['code'] for p in profiles}, {TIMELY, EARLY, RESTRICTED})
        self.assertTrue(all('excluding Jhansi' in p['scope_note'] for p in profiles))

    def test_unknown_profile_crop_and_future_sowing_are_controlled(self):
        self.assertEqual(self.select(profile='missing').status_code, 404)
        with self.Session.begin() as db:
            db.get(CropCycle, self.cycle_id).sowing_date = date(2100, 1, 1)
        self.assertEqual(self.select(variety=None).status_code, 409)

    def test_create_cycle_rejects_unknown_profile_foreign_key(self):
        with self.Session() as db:
            crop = db.scalar(select(Crop).where(Crop.crop_name == 'Wheat'))
            field = db.scalar(select(Field).limit(1))
            db.add(CropCycle(field_id=field.field_id, crop_id=crop.crop_id, sowing_date=date.today(), status='planned', agronomic_profile_code='invented'))
            with self.assertRaises(Exception): db.commit()
            db.rollback()

    def test_selected_variety_is_returned_by_cycle_and_field_reads(self):
        self.assertEqual(self.select(variety='HD 3226').status_code, 200)
        data = self.client.get(f'/crop-cycles/{self.cycle_id}').json()
        self.assertEqual(data['variety'], 'HD 3226')
        self.assertEqual(data['agronomic_profile_code'], TIMELY)
        rows = self.client.get(f"/fields/{data['field_id']}/crop-cycles").json()
        self.assertEqual(next(row for row in rows if row['crop_cycle_id'] == str(self.cycle_id))['variety'], 'HD 3226')

    def test_date_and_profile_edits_preserve_unrelated_saved_fields(self):
        self.select(variety='HD 3226')
        with self.Session.begin() as db:
            cycle = db.get(CropCycle, self.cycle_id)
            cycle.current_stage, cycle.stage_override = 'retained-stage', 'retained-override'
            field_id = str(cycle.field_id)
        response = self.client.put(f'/crop-cycles/{self.cycle_id}', json={'sowing_date': '2025-11-12', 'expected_harvest_date': '2026-04-10'})
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data['variety'], 'HD 3226')
        self.assertEqual(data['agronomic_profile_code'], TIMELY)
        self.assertEqual(self.select(variety='HD 3226').status_code, 200)
        saved = self.client.get(f'/crop-cycles/{self.cycle_id}').json()
        self.assertEqual(saved['sowing_date'], '2025-11-12')
        self.assertEqual(saved['expected_harvest_date'], '2026-04-10')
        self.assertEqual(saved['field_id'], field_id)
        self.assertEqual(saved['current_stage'], 'retained-stage')
        self.assertEqual(saved['stage_override'], 'retained-override')

    def test_omitted_variety_is_preserved_and_explicit_null_clears_it(self):
        self.select(variety='HD 3226')
        response = self.client.put(f'/crop-cycles/{self.cycle_id}/agronomic-profile', json={'profile_code': TIMELY})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['selected_variety']['code'], 'HD 3226')
        self.assertEqual(self.select(variety=None).status_code, 200)
        self.assertIsNone(self.client.get(f'/crop-cycles/{self.cycle_id}').json()['variety'])

    def test_incompatible_conditions_do_not_silently_clear_saved_variety(self):
        self.select(variety='HD 3226')
        response = self.client.put(f'/crop-cycles/{self.cycle_id}/agronomic-profile', json={'profile_code': RESTRICTED})
        self.assertEqual(response.status_code, 409)
        saved = self.client.get(f'/crop-cycles/{self.cycle_id}').json()
        self.assertEqual(saved['variety'], 'HD 3226')
        self.assertEqual(saved['agronomic_profile_code'], TIMELY)

    def test_wheat_catalogue_cannot_be_assigned_to_another_crop(self):
        # Test-only alternate crop, inside the disposable schema.
        with self.Session.begin() as db:
            other = Crop(crop_name='Other test crop'); db.add(other); db.flush()
            db.get(CropCycle, self.cycle_id).crop_id = other.crop_id
        self.assertEqual(self.client.get('/agronomic-profiles', params={'crop': 'Other test crop', 'zone': 'NWPZ'}).json(), [])
        self.assertEqual(self.select(variety='HD 3226').status_code, 409)
        saved = self.client.get(f'/crop-cycles/{self.cycle_id}').json()
        self.assertIsNone(saved['variety'])
        self.assertIsNone(saved['agronomic_profile_code'])


if __name__ == '__main__': unittest.main()
