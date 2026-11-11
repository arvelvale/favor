"""Security regressions. External API calls and database access are blocked."""
import contextlib
import importlib
import importlib.util
import io
import os
from pathlib import Path
import secrets
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

from werkzeug.security import generate_password_hash

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "aifood/aifood3/aifood"
sys.path.insert(0, str(APP))
sys.path.insert(0, str(APP.parent))


def core_environment():
    return {"DEEPSEEK_API_KEY": secrets.token_urlsafe(24),
            "SECRET_KEY": secrets.token_urlsafe(48),
            "DB_USER": "test_user", "DB_PASSWORD": secrets.token_urlsafe(24)}


def load_config(path, environment):
    spec = importlib.util.spec_from_file_location("isolated_config", path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(os.environ, environment, clear=True):
        spec.loader.exec_module(module)
    return module


class ConfigurationTests(unittest.TestCase):
    def test_core_credentials_have_no_fallback(self):
        for name in core_environment():
            with self.subTest(name=name):
                environment = core_environment()
                environment.pop(name)
                with self.assertRaisesRegex(RuntimeError, name):
                    load_config(APP / "config.py", environment)

    def test_short_session_key_is_rejected(self):
        environment = core_environment()
        environment["SECRET_KEY"] = "short"
        with self.assertRaisesRegex(RuntimeError, "at least 32"):
            load_config(APP / "config.py", environment)

    def test_dotenv_is_relative_to_config_and_environment_wins(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / "config.py"
            shutil.copyfile(APP / "config.py", config)
            environment = core_environment()
            (Path(folder) / ".env").write_text(
                "\n".join(f"{key}={value}" for key, value in environment.items()),
                encoding="utf-8")
            module = load_config(config, {"DB_USER": "override_user"})
            self.assertEqual(module.db_config["user"], "override_user")
            self.assertEqual(module.DEEPSEEK_API_KEY, environment["DEEPSEEK_API_KEY"])
            self.assertFalse(module.DEBUG)
            self.assertFalse(module.PAYPAL_ENABLED)
            self.assertIsNone(module.get_proxies())

    def test_admin_hash_utility_never_prints_plaintext(self):
        spec = importlib.util.spec_from_file_location("configure_admin", APP / "scripts/configure_admin.py")
        utility = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(utility)
        password = secrets.token_urlsafe(24)
        output = io.StringIO()
        with patch.object(utility, "getpass", side_effect=[password, password]), contextlib.redirect_stdout(output):
            utility.main()
        self.assertNotIn(password, output.getvalue())
        self.assertIn("ADMIN_PASSWORD_HASH=", output.getvalue())

    def test_admin_hash_utility_rejects_mismatch(self):
        spec = importlib.util.spec_from_file_location("configure_admin", APP / "scripts/configure_admin.py")
        utility = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(utility)
        with patch.object(utility, "getpass", side_effect=[secrets.token_urlsafe(24), "mismatch"]):
            with self.assertRaises(SystemExit):
                utility.main()


class ApplicationSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password = secrets.token_urlsafe(24)
        cls.environment = core_environment()
        cls.environment.update(ADMIN_USERNAME="test-admin",
                               ADMIN_PASSWORD_HASH=generate_password_hash(cls.password))
        with patch.dict(os.environ, cls.environment, clear=True):
            database = importlib.import_module("database")
            with patch.object(database, "init_database"), \
                 patch("mysql.connector.connect", side_effect=AssertionError("Unexpected database call")):
                cls.module = importlib.import_module("app")
        cls.admin = importlib.import_module("admin_routes")
        cls.api = importlib.import_module("api_clients")
        cls.email = importlib.import_module("verification_email")
        cls.module.app.config.update(TESTING=True)

    def setUp(self):
        self.client = self.module.app.test_client()
        self.database_guard = patch("mysql.connector.connect", side_effect=AssertionError("Unexpected database call"))
        self.database_guard.start()
        self.addCleanup(self.database_guard.stop)

    def test_admin_accepts_hash_and_clears_previous_session(self):
        with self.client.session_transaction() as session:
            session["old_session_marker"] = True
        response = self.client.post("/admin/login", data={"username": "test-admin", "password": self.password})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/admin/dashboard"))
        with self.client.session_transaction() as session:
            self.assertEqual(session["admin_name"], "test-admin")
            self.assertEqual(session["admin_id"], 1)
            self.assertNotIn("old_session_marker", session)

    def test_wrong_and_missing_admin_credentials_are_rejected(self):
        for data in ({}, {"username": "test-admin", "password": "incorrect"},
                     {"username": "wrong-admin", "password": self.password}):
            with self.subTest(fields=list(data)):
                self.client.post("/admin/login", data=data)
                with self.client.session_transaction() as session:
                    self.assertNotIn("admin_id", session)

    def test_admin_without_configuration_is_disabled(self):
        with patch.object(self.admin, "ADMIN_PASSWORD_HASH", ""):
            response = self.client.post("/admin/login", data={"username": "test-admin", "password": self.password})
        self.assertEqual(response.status_code, 503)
        with self.client.session_transaction() as session:
            self.assertNotIn("admin_id", session)

    def test_plaintext_and_malformed_admin_hashes_do_not_authenticate(self):
        for invalid in (self.password, "scrypt:invalid"):
            with self.subTest(hash_type=invalid.split(":")[0]), patch.object(self.admin, "ADMIN_PASSWORD_HASH", invalid):
                response = self.client.post("/admin/login", data={"username": "test-admin", "password": self.password})
                self.assertEqual(response.status_code, 200)
                with self.client.session_transaction() as session:
                    self.assertNotIn("admin_id", session)

    def test_payment_without_credentials_never_calls_provider(self):
        with patch.object(self.module, "Payment") as payment, patch.object(self.module, "require_login", return_value=None):
            create = self.client.post("/api/create-paypal-order", json={"plan_type": "monthly"})
            capture = self.client.get("/api/capture-paypal-order")
        self.assertEqual(create.status_code, 503)
        self.assertEqual(capture.status_code, 503)
        payment.assert_not_called()
        payment.find.assert_not_called()

    def test_gemini_uses_header_and_never_places_key_in_url(self):
        key = secrets.token_urlsafe(24)
        with patch.object(self.api.config, "GEMINI_API_KEY", key), patch.object(self.api.requests, "post") as post:
            post.return_value.status_code = 200
            post.return_value.json.return_value = {"candidates": []}
            self.api.generate_recipe_images("test recipe")
        kwargs = post.call_args.kwargs
        self.assertEqual(kwargs["headers"]["x-goog-api-key"], key)
        self.assertNotIn("params", kwargs)
        self.assertNotIn(key, kwargs["url"])

    def test_gemini_exception_does_not_leak_provider_message(self):
        marker = secrets.token_urlsafe(24)
        with patch.object(self.api.config, "GEMINI_API_KEY", marker), \
             patch.object(self.api.requests, "post", side_effect=RuntimeError(marker)), \
             self.assertLogs(self.api.logger, level="ERROR") as logs:
            result = self.api.generate_recipe_images("test recipe")
        self.assertNotIn(marker, str(result))
        self.assertNotIn(marker, "\n".join(logs.output))

    def test_deepseek_stream_exception_does_not_leak_provider_message(self):
        recipe = importlib.import_module("test")
        marker = secrets.token_urlsafe(24)
        with patch.object(recipe.client.chat.completions, "create", side_effect=RuntimeError(marker)), \
             self.assertLogs(recipe.logger, level="ERROR") as logs:
            result = b"".join(recipe.generate_recipe_stream(["ingredient"], 0.7, 100))
        self.assertNotIn(marker.encode(), result)
        self.assertNotIn(marker, "\n".join(logs.output))

    def test_missing_gemini_and_smtp_configuration_make_no_network_call(self):
        with patch.object(self.api.config, "GEMINI_API_KEY", ""), patch.object(self.api.requests, "post") as post:
            self.assertFalse(self.api.generate_recipe_images("test recipe")["success"])
            post.assert_not_called()
        with patch.object(self.email, "sender_password", ""), patch.object(self.email.smtplib, "SMTP_SSL") as smtp:
            self.assertFalse(self.email.send_verification_email("user@example.com", "123456")[0])
            smtp.assert_not_called()

    def test_smtp_protocol_logging_is_disabled(self):
        with patch.object(self.email, "sender_email", "sender@example.com"), \
             patch.object(self.email, "sender_password", secrets.token_urlsafe(24)), \
             patch.object(self.email.smtplib, "SMTP_SSL") as smtp:
            smtp.return_value.sendmail.return_value = {}
            self.assertTrue(self.email.send_verification_email("user@example.com", "123456")[0])
            smtp.return_value.set_debuglevel.assert_called_once_with(0)


if __name__ == "__main__":
    unittest.main()
