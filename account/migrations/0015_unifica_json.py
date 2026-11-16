"""Une las dos historias de campos JSON sin modificar datos ni ejecutar SQL."""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0014_campos_json_nativos"),
        ("account", "0014_alter_user_session_keys_and_more"),
    ]
    operations = []
