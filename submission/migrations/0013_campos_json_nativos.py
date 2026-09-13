# Sincroniza el estado con models.JSONField; PostgreSQL conserva los campos jsonb y sus datos.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("submission", "0012_auto_20180501_0436")]

    operations = [
        migrations.AlterField(
            model_name="submission",
            name="info",
            field=models.JSONField(default=dict),
        ),
        migrations.AlterField(
            model_name="submission",
            name="statistic_info",
            field=models.JSONField(default=dict),
        ),
    ]
