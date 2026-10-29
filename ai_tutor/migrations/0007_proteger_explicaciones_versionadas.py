from importlib import import_module
from django.db import migrations


# Amplía la protección histórica sin reescribir la migración ya publicada.
BASE = import_module("ai_tutor.migrations.0003_versiones_configuracion").FORWARD_SQL
ORIGINAL = BASE.split("CREATE TRIGGER tutor_config_version_immutable")[0]
UPDATED = ORIGINAL.replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION").replace(
    "NEW.created_by_id, NEW.created_at)", "NEW.created_by_id, NEW.created_at, NEW.concept_explanations)"
).replace("OLD.created_by_id, OLD.created_at)", "OLD.created_by_id, OLD.created_at, OLD.concept_explanations)")


class Migration(migrations.Migration):
    dependencies = [("ai_tutor", "0006_alter_tutorfeedback_session")]
    operations = [migrations.RunSQL(UPDATED, ORIGINAL.replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION"))]
