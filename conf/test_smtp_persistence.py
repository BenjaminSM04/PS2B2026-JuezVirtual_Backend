"""Persistencia de la configuracion SMTP con datos sinteticos."""
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
        from options.options import SysOptions
        self.test_create_smtp_config()
        config = dict(SysOptions.smtp_config, ssl=True, tls=True)
        self.assertIsNotNone(self.client.post(self.url, data=config).data["error"])


