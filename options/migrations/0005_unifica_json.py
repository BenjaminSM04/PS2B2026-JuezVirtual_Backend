"""Une las dos historias de campos JSON sin modificar datos ni ejecutar SQL."""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("options", "0004_campos_json_nativos"),
        ("options", "0004_alter_sysoptions_value"),
    ]
    operations = []
