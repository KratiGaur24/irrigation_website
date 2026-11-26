"""Verify browser preflights for existing frontend write operations without a DB."""
import unittest

from fastapi.testclient import TestClient

from app.main import app


class FrontendConnectionTests(unittest.TestCase):
    def test_crop_profile_put_preflight_is_allowed(self):
        with TestClient(app) as client:
            response = client.options('/crop-cycles/test/agronomic-profile', headers={
                'Origin': 'http://127.0.0.1:5173',
                'Access-Control-Request-Method': 'PUT',
                'Access-Control-Request-Headers': 'content-type',
            })
        self.assertEqual(response.status_code, 200)
        self.assertIn('PUT', response.headers['access-control-allow-methods'])

    def test_unconfigured_origin_is_rejected(self):
        with TestClient(app) as client:
            response = client.options('/crop-cycles/test/agronomic-profile', headers={
                'Origin': 'https://unconfigured.invalid',
                'Access-Control-Request-Method': 'PUT',
            })
        self.assertEqual(response.status_code, 400)
        self.assertNotIn('access-control-allow-origin', response.headers)
