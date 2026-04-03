# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0012_userprofile_language"),
    ]

    operations = [
        migrations.AlterField(
            model_name="userprofile",
            name="language",
            field=models.CharField(
                blank=True,
                choices=[
                    ("en-US", "English (US)"),
                    ("zh-CN", "\u7b80\u4f53\u4e2d\u6587"),
                    ("es-LA", "Espanol Latino"),
                ],
                max_length=32,
                null=True,
            ),
        ),
    ]
