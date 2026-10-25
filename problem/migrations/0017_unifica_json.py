"""Une las dos historias de campos JSON sin modificar datos ni ejecutar SQL."""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("problem", "0016_campos_json_nativos"),
        ("problem", "0016_alter_problem_io_mode_alter_problem_languages_and_more"),
    ]
    operations = []
