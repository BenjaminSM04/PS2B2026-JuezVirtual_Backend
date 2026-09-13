# Sincroniza el estado con models.JSONField; PostgreSQL conserva los campos jsonb y sus datos.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("options", "0003_migrate_languages_options")]

    operations = [
        migrations.AlterField(
            model_name="sysoptions",
            name="value",
            field=models.JSONField(),
        ),
    ]
