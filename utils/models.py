from django.db.models import JSONField  # NOQA
from django.db import models

from utils.xss_filter import XSSHtml


class RichTextField(models.TextField):
    def from_db_value(self, value, expression, connection):
        with XSSHtml() as parser:
            return parser.clean(value or "")

    def get_prep_value(self, value):
        with XSSHtml() as parser:
            return parser.clean(value or "")
