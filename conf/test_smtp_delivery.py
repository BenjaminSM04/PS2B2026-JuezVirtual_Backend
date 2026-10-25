"""SMTP genérico y Resend comparten transporte sin exponer la clave."""
from unittest import mock
import secrets

from django.test import SimpleTestCase
from utils.shortcuts import send_email
from .tests import SMTPConfigTest


class SMTPPersistenceTest(SMTPConfigTest):
    def test_blank_and_null_preserve_secret(self):
        from options.options import SysOptions
        self.test_create_smtp_config()
        for blank in ("", None):
            self.assertSuccess(self.client.put(self.url, data=dict(SysOptions.smtp_config, password=blank)))
            self.assertEqual(SysOptions.smtp_config["password"], self.password)
        self.assertNotIn("password", self.client.get(self.url).data["data"])

    def test_rejects_conflicting_encryption(self):
        config = {"server": "smtp.resend.com", "port": 465, "email": "avisos@example.com",
                  "username": "resend", "ssl": True, "tls": True, "password": secrets.token_urlsafe(24)}
        self.assertIsNotNone(self.client.post(self.url, data=config).data["error"])


class SMTPTransportTest(SimpleTestCase):
    config = {"server": "smtp.resend.com", "port": 465, "email": "avisos@example.com",
              "username": "resend", "password": secrets.token_urlsafe(24), "ssl": True, "tls": False}

    def deliver(self, config):
        return send_email(config, "LizardJudge", "destino@example.com", "Estudiante", "Prueba", "<p>Hola</p>")

    @mock.patch("utils.shortcuts.smtplib.SMTP_SSL")
    @mock.patch("utils.shortcuts.smtplib.SMTP")
    def test_resend_ssl_authentication_and_sender_are_independent(self, plain, secure):
        client = secure.return_value.__enter__.return_value
        client.send_message.return_value = {}
        self.deliver(self.config)
        plain.assert_not_called()
        client.login.assert_called_once_with("resend", self.config["password"])
        client.starttls.assert_not_called()
        message = client.send_message.call_args.args[0]
        self.assertEqual(message["From"], "LizardJudge <avisos@example.com>")
        self.assertEqual(secure.call_args.kwargs["timeout"], 15)
        self.assertTrue(secure.call_args.kwargs["context"].check_hostname)

    @mock.patch("utils.shortcuts.smtplib.SMTP")
    def test_starttls_and_legacy_login(self, smtp):
        config = dict(self.config, port=587, ssl=False, tls=True)
        config.pop("username")
        client = smtp.return_value.__enter__.return_value
        client.send_message.return_value = {}
        self.deliver(config)
        client.starttls.assert_called_once()
        client.login.assert_called_once_with(config["email"], config["password"])

    @mock.patch("utils.shortcuts.smtplib.SMTP_SSL")
    def test_refused_recipient_does_not_report_success(self, smtp):
        smtp.return_value.__enter__.return_value.send_message.return_value = {"destino@example.com": (550, b"rejected")}
        with self.assertRaises(RuntimeError):
            self.deliver(self.config)
