from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


# Las garantías históricas también cubren QuerySet.update(), delete() y SQL directo.
FORWARD_SQL = """
CREATE FUNCTION tutor_guard_config_version() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.status <> 'draft' THEN
            RAISE EXCEPTION 'An activated tutor config cannot be deleted' USING ERRCODE = '23514';
        END IF;
        RETURN OLD;
    END IF;
    IF ROW(NEW.id, NEW.problem_id, NEW.version, NEW.schema_version, NEW.concepts, NEW.hint_policy,
           NEW.created_by_id, NEW.created_at)
       IS DISTINCT FROM
       ROW(OLD.id, OLD.problem_id, OLD.version, OLD.schema_version, OLD.concepts, OLD.hint_policy,
           OLD.created_by_id, OLD.created_at) THEN
        RAISE EXCEPTION 'Tutor config content is immutable; create another draft' USING ERRCODE = '23514';
    END IF;
    IF NEW.status = OLD.status AND NEW.activated_at IS NOT DISTINCT FROM OLD.activated_at THEN
        RETURN NEW;
    END IF;
    IF OLD.status = 'draft' AND NEW.status = 'active' AND NEW.activated_at IS NOT NULL THEN
        RETURN NEW;
    END IF;
    IF OLD.status = 'active' AND NEW.status = 'retired'
       AND NEW.activated_at IS NOT DISTINCT FROM OLD.activated_at THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Invalid tutor config transition' USING ERRCODE = '23514';
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER tutor_config_version_immutable
BEFORE UPDATE OR DELETE ON ai_tutor_tutorproblemconfigversion
FOR EACH ROW EXECUTE PROCEDURE tutor_guard_config_version();

CREATE FUNCTION tutor_guard_session_version() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF ROW(NEW.config_version_id, NEW.problem_id) IS DISTINCT FROM ROW(OLD.config_version_id, OLD.problem_id) THEN
            RAISE EXCEPTION 'A tutor session cannot change its original config or problem' USING ERRCODE = '23514';
        END IF;
    ELSE
        IF NEW.config_version_id IS NULL OR NOT EXISTS (
            SELECT 1 FROM ai_tutor_tutorproblemconfigversion
            WHERE id = NEW.config_version_id AND problem_id = NEW.problem_id AND status = 'active'
        ) THEN
            RAISE EXCEPTION 'A new tutor session requires an active config of the same problem' USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER tutor_session_version_immutable
BEFORE INSERT OR UPDATE ON ai_tutor_tutorsession
FOR EACH ROW EXECUTE PROCEDURE tutor_guard_session_version();
"""

REVERSE_SQL = """
DROP TRIGGER tutor_session_version_immutable ON ai_tutor_tutorsession;
DROP FUNCTION tutor_guard_session_version();
DROP TRIGGER tutor_config_version_immutable ON ai_tutor_tutorproblemconfigversion;
DROP FUNCTION tutor_guard_config_version();
"""


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("ai_tutor", "0002_sesiones_e_intentos"),
    ]

    operations = [
        migrations.CreateModel(
            name="TutorProblemConfigVersion",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("version", models.PositiveIntegerField()),
                ("schema_version", models.CharField(max_length=10)),
                ("concepts", models.JSONField()),
                ("hint_policy", models.JSONField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("status", models.CharField(choices=[("draft", "Borrador"), ("active", "Activo"), ("retired", "Retirado")], default="draft", max_length=10)),
                ("activated_at", models.DateTimeField(editable=False, null=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("problem", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="tutor_config_versions", to="problem.problem")),
            ],
            options={"ordering": ["version"]},
        ),
        migrations.AddConstraint(
            model_name="tutorproblemconfigversion",
            constraint=models.UniqueConstraint(fields=("problem", "version"), name="tutor_unique_config_version"),
        ),
        migrations.AddConstraint(
            model_name="tutorproblemconfigversion",
            constraint=models.UniqueConstraint(condition=models.Q(status="active"), fields=("problem",), name="tutor_one_active_config"),
        ),
        migrations.AddConstraint(
            model_name="tutorproblemconfigversion",
            constraint=models.CheckConstraint(check=models.Q(version__gte=1), name="tutor_config_positive_version"),
        ),
        migrations.AddConstraint(
            model_name="tutorproblemconfigversion",
            constraint=models.CheckConstraint(check=models.Q(status="draft", activated_at__isnull=True) |
                                              models.Q(status__in=["active", "retired"], activated_at__isnull=False), name="tutor_config_status_valid"),
        ),
        migrations.AddField(
            model_name="tutorsession",
            name="config_version",
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name="sessions", to="ai_tutor.tutorproblemconfigversion"),
        ),
        migrations.RunSQL(FORWARD_SQL, REVERSE_SQL),
    ]
