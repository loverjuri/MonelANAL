"""Small dependency-free smoke tests for the Flask application."""
import os
import unittest
from unittest.mock import Mock

os.environ.setdefault("DEV_MODE", "0")

from app import app
from db.repositories import add_finance_entry, add_account_transfer


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

    def test_bad_page_is_not_server_error_in_dev_mode(self):
        previous = app.config.get("DEV_MODE")
        app.config["DEV_MODE"] = True
        try:
            response = self.client.get("/web/history?page=not-a-number")
            self.assertNotEqual(response.status_code, 500)
        finally:
            app.config["DEV_MODE"] = previous

    def test_finance_rejects_non_finite_amount(self):
        with self.assertRaises(ValueError):
            add_finance_entry(Mock(), "2026-01-01", "Expense", float("nan"))

    def test_transfer_rejects_non_finite_amount(self):
        self.assertFalse(add_account_transfer(Mock(), "2026-01-01", "a", "b", float("inf")))


if __name__ == "__main__":
    unittest.main()
