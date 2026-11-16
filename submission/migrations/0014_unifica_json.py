"""Une las dos historias de campos JSON sin modificar datos ni ejecutar SQL."""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("submission", "0013_campos_json_nativos"),
        ("submission", "0013_alter_submission_info_and_more"),
    ]
    operations = []
