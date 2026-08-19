"""Small dependency-free smoke tests for the Flask application."""
import os
import unittest

os.environ.setdefault("DEV_MODE", "0")

from app import app


class AppSmokeTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_health(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_data(as_text=True), "OK")

    def test_protected_pages_redirect(self):
        for path in ("/web/dashboard", "/web/debts", "/web/ip", "/web/settings"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/web/login", response.headers["Location"])

    def test_cron_requires_token(self):
        response = self.client.get("/cron/backup")
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
