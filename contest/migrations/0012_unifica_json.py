"""Une las dos historias de campos JSON sin modificar datos ni ejecutar SQL."""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("contest", "0011_campos_json_nativos"),
        ("contest", "0011_alter_acmcontestrank_submission_info_and_more"),
    ]
    operations = []
