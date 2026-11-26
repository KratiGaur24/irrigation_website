"""Real PostgreSQL integration tests in a disposable, uniquely named schema.

Never inserts test data into public tables or operates hardware.
Run from backend: .venv\Scripts\python.exe -m unittest discover -s tests -v
"""
import importlib.util
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.dependencies import get_db
from app.main import app
from app.models import User, Farm, Field, Device, SensorReading, IrrigationEvent
from app.services.device_control_service import DeviceControl, Acknowledgement, get_control
from app.services import irrigation_control_service as service


class TestControl(DeviceControl):
    def __init__(self):
        super().__init__('simulated')
        self.commands = []
        self.reject_start = False
        self.unknown_start = False
        self.reject_off = False

    def _command(self, action, device, event_id=None):
        self.commands.append(action)
        if action == 'start' and self.unknown_start:
            raise TimeoutError('test missing acknowledgement')
        if (action == 'start' and self.reject_start) or (action != 'start' and self.reject_off):
            return Acknowledgement(False, self.mode, 'Test command rejection', action == 'start')
        return Acknowledgement(True, self.mode, 'Simulated acknowledgement only; no physical pump was operated.')


class ManualIrrigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = 'test_irrigation_' + uuid4().hex
        cls.admin = create_engine(settings.database_url)
        with cls.admin.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA "{cls.schema}"'))
        cls.engine = create_engine(settings.database_url, connect_args={'options': f'-csearch_path={cls.schema},public'})
        cls.Session = sessionmaker(cls.engine, expire_on_commit=False, autoflush=False)
        # Execute all real migrations in the isolated schema, not metadata.create_all.
        with cls.engine.begin() as conn:
            with Operations.context(MigrationContext.configure(conn)):
                for path in sorted(Path('alembic/versions').glob('*.py')):
                    spec = importlib.util.spec_from_file_location(path.stem, path)
                    migration = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(migration)
                    migration.upgrade()

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()
        cls.engine.dispose()
        assert cls.schema.startswith('test_irrigation_') and len(cls.schema) == 48
        with cls.admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{cls.schema}" CASCADE'))
        cls.admin.dispose()

    def setUp(self):
        self.control = TestControl()
        def test_db():
            with self.Session() as db:
                yield db
        app.dependency_overrides[get_db] = test_db
        app.dependency_overrides[get_control] = lambda: self.control
        self.client = TestClient(app)
        with self.Session.begin() as db:
            user = User(name='Isolated test', email=f'{uuid4()}@example.test', password_hash='test-only')
            db.add(user); db.flush()
            farm = Farm(user_id=user.user_id, farm_name='Isolated test farm')
            db.add(farm); db.flush()
            field = Field(farm_id=farm.farm_id, field_name='Isolated test field')
            db.add(field); db.flush()
            device = Device(field_id=field.field_id, device_code=str(uuid4()), device_type='irrigation_controller', status='offline')
            db.add(device); db.flush()
            self.field_id, self.device_id = field.field_id, device.device_id
        self.url = f'/fields/{self.field_id}/irrigation'

    def tearDown(self):
        self.client.close()

    def reading(self, moisture=None, volume=None, flow=None, at=None, valid=True, device_id=None):
        with self.Session.begin() as db:
            reading = SensorReading(field_id=self.field_id, device_id=device_id or self.device_id, sensor_valid=valid,
                                    recorded_at=at or datetime.now(timezone.utc), soil_moisture_pct=moisture,
                                    cumulative_water_litres=volume, flow_rate_lpm=flow)
            db.add(reading); db.flush()
            return reading.reading_id

    def test_lifecycle_moisture_duration_and_null_volume(self):
        now = datetime.now(timezone.utc)
        self.reading(moisture=31, at=now - timedelta(seconds=1))
        with patch.object(service, 'utcnow', return_value=now):
            response = self.client.post(self.url + '/start')
        self.assertEqual(response.status_code, 201, response.text)
        event = response.json()
        self.assertEqual((event['mode'], event['status'], event['control_mode']), ('MANUAL', 'started', 'simulated'))
        self.assertEqual(Decimal(event['moisture_before_pct']), 31)
        self.assertIsNone(event['duration_seconds'])
        self.assertIsNone(event['water_used_litres'])
        self.assertEqual(self.client.get(self.url + '/active').json()['event_id'], event['event_id'])
        self.assertEqual(self.client.post(self.url + '/start').status_code, 409)
        self.reading(moisture=35, at=now + timedelta(seconds=40))
        with patch.object(service, 'utcnow', return_value=now + timedelta(seconds=60)):
            stopped = self.client.post(self.url + '/stop')
        self.assertEqual(stopped.status_code, 200, stopped.text)
        self.assertEqual(stopped.json()['status'], 'completed')
        self.assertEqual(stopped.json()['duration_seconds'], 60)
        self.assertEqual(Decimal(stopped.json()['moisture_after_pct']), 35)
        self.assertIsNone(stopped.json()['water_used_litres'])
        self.assertIsNone(self.client.get(self.url + '/active').json())
        self.assertEqual(self.client.post(self.url + '/stop').status_code, 409)
        history = self.client.get(self.url + '/history').json()
        self.assertEqual(history[0]['event_id'], event['event_id'])

    def test_volume_is_real_same_device_counter_difference(self):
        now = datetime.now(timezone.utc)
        self.reading(volume=100, at=now - timedelta(seconds=1))
        with patch.object(service, 'utcnow', return_value=now):
            self.assertEqual(self.client.post(self.url + '/start').status_code, 201)
        self.reading(volume='113.75', flow='2.5', at=now + timedelta(seconds=20))
        with patch.object(service, 'utcnow', return_value=now + timedelta(seconds=30)):
            active = self.client.get(self.url + '/active').json()
            stopped = self.client.post(self.url + '/stop').json()
        self.assertEqual(Decimal(active['current_water_used_litres']), Decimal('13.75'))
        self.assertEqual(Decimal(active['current_flow_rate_lpm']), Decimal('2.5'))
        self.assertEqual(Decimal(stopped['water_used_litres']), Decimal('13.75'))

    def test_counter_reset_invalidates_volume_even_if_counter_recovers(self):
        now = datetime.now(timezone.utc)
        self.reading(volume=100, at=now - timedelta(seconds=1))
        with patch.object(service, 'utcnow', return_value=now):
            self.client.post(self.url + '/start')
        self.reading(volume=0, at=now + timedelta(seconds=10))
        self.reading(volume=150, at=now + timedelta(seconds=20))
        with patch.object(service, 'utcnow', return_value=now + timedelta(seconds=30)):
            result = self.client.post(self.url + '/stop').json()
        self.assertIsNone(result['water_used_litres'])

    def test_no_new_counter_reading_means_unknown_volume(self):
        self.reading(volume=100)
        self.client.post(self.url + '/start')
        self.assertIsNone(self.client.post(self.url + '/stop').json()['water_used_litres'])

    def test_emergency_is_repeatable_and_does_not_start(self):
        self.client.post(self.url + '/start')
        stopped = self.client.post(self.url + '/emergency-stop').json()
        self.assertTrue(stopped['acknowledged'])
        self.assertEqual(stopped['session']['status'], 'stopped')
        self.assertEqual(stopped['session']['trigger_reason'], 'manual emergency stop')
        again = self.client.post(self.url + '/emergency-stop').json()
        self.assertTrue(again['acknowledged'])
        self.assertIsNone(again['session'])
        self.assertEqual(self.control.commands, ['start', 'emergency-stop', 'emergency-stop'])
        self.assertEqual(len(self.client.get(self.url + '/history').json()), 1)

    def test_missing_sensors_dont_block_stop(self):
        result = self.client.post(self.url + '/start').json()
        self.assertIsNone(result['moisture_before_pct'])
        self.assertEqual(self.client.post(self.url + '/stop').status_code, 200)

    def test_rejected_start_is_failed_and_closed(self):
        self.control.reject_start = True
        self.assertEqual(self.client.post(self.url + '/start').status_code, 502)
        self.assertIsNone(self.client.get(self.url + '/active').json())
        event = self.client.get(self.url + '/history').json()[0]
        self.assertEqual(event['status'], 'failed')
        self.assertEqual(event['fault_code'], 'START_REJECTED')

    def test_uncertain_start_blocks_duplicate_until_off_acknowledged(self):
        self.control.unknown_start = True
        self.assertEqual(self.client.post(self.url + '/start').status_code, 502)
        event = self.client.get(self.url + '/active').json()
        self.assertEqual(event['status'], 'failed')
        self.assertIsNone(event['ended_at'])
        self.assertEqual(self.client.post(self.url + '/start').status_code, 409)
        self.assertTrue(self.client.post(self.url + '/emergency-stop').json()['acknowledged'])

    def test_off_failure_stays_open_for_retry(self):
        self.client.post(self.url + '/start')
        self.control.reject_off = True
        self.assertEqual(self.client.post(self.url + '/stop').status_code, 502)
        result = self.client.post(self.url + '/emergency-stop').json()
        self.assertFalse(result['acknowledged'])
        self.assertIsNone(result['session']['ended_at'])
        self.assertEqual(self.client.get(self.url + '/history').json(), [])
        self.control.reject_off = False
        self.assertTrue(self.client.post(self.url + '/emergency-stop').json()['acknowledged'])

    def test_hardware_is_unavailable_and_simulation_never_closes_hardware_event(self):
        self.control = DeviceControl('hardware')
        self.assertFalse(self.client.get(self.url + '/control').json()['available'])
        self.assertEqual(self.client.post(self.url + '/start').status_code, 503)
        self.control = TestControl()
        self.client.post(self.url + '/start')
        with self.Session.begin() as db:
            event = service.open_event(db, self.field_id)
            event.control_mode = 'hardware'
        result = self.client.post(self.url + '/emergency-stop').json()
        self.assertFalse(result['acknowledged'])
        self.assertIsNone(result['session']['ended_at'])
        self.assertEqual(self.control.commands, ['start'])

    def test_history_limit_sorting_and_date_validation(self):
        for _ in range(3):
            self.client.post(self.url + '/start'); self.client.post(self.url + '/stop')
        rows = self.client.get(self.url + '/history?limit=2').json()
        self.assertEqual(len(rows), 2)
        self.assertGreaterEqual(rows[0]['started_at'], rows[1]['started_at'])
        self.assertEqual(self.client.get(self.url + '/history?limit=999').status_code, 422)
        self.assertEqual(self.client.get(self.url + '/history?from=2030-01-01T00:00:00Z&to=2020-01-01T00:00:00Z').status_code, 422)
        self.assertEqual(self.client.get(self.url + '/history?from=2020-01-01T00:00:00').status_code, 422)
        self.assertEqual(self.client.get(self.url + '/history?from=2030-01-01T00:00:00Z').json(), [])

    def test_concurrent_start_and_database_unique_guard(self):
        def create():
            with self.Session() as db:
                try:
                    service.start(db, self.field_id, self.control)
                    return 201
                except Exception as error:
                    return getattr(error, 'status_code', 500)
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(lambda _: create(), range(2)))
        self.assertEqual(sorted(statuses), [201, 409])
        self.assertEqual(self.control.commands.count('start'), 1)
        with self.Session() as db:
            db.add(IrrigationEvent(field_id=self.field_id, mode='MANUAL', status='started', started_at=datetime.now(timezone.utc)))
            with self.assertRaises(IntegrityError):
                db.commit()
            db.rollback()

    def test_commit_failure_after_start_attempts_emergency_off(self):
        with self.Session() as db:
            with patch.object(db, 'commit', side_effect=OperationalError('test', {}, Exception('test commit failure'))):
                with self.assertRaises(Exception) as error:
                    service.start(db, self.field_id, self.control)
                self.assertEqual(error.exception.status_code, 503)
        self.assertEqual(self.control.commands, ['start', 'emergency-stop'])
        self.assertIsNone(self.client.get(self.url + '/active').json())

    def test_missing_field_and_ambiguous_controller_are_rejected(self):
        self.assertEqual(self.client.post(f'/fields/{uuid4()}/irrigation/start').status_code, 404)
        with self.Session.begin() as db:
            db.add(Device(field_id=self.field_id, device_code=str(uuid4()), device_type='pump_controller', status='online'))
        self.assertEqual(self.client.post(self.url + '/start').status_code, 409)

    def test_invalid_and_future_sensor_values_not_used(self):
        now = datetime.now(timezone.utc)
        self.reading(moisture=20, at=now - timedelta(seconds=20))
        self.reading(moisture=90, valid=False, at=now - timedelta(seconds=10))
        self.reading(moisture=99, at=now + timedelta(days=1))
        event = self.client.post(self.url + '/start').json()
        self.assertEqual(Decimal(event['moisture_before_pct']), 20)


if __name__ == '__main__':
    unittest.main()
