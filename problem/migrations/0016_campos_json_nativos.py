# Sincroniza el estado con models.JSONField; PostgreSQL conserva los campos jsonb y sus datos.
from django.db import migrations, models
import problem.models


class Migration(migrations.Migration):
    dependencies = [("problem", "0015_problem_share_mode")]

    operations = [
        migrations.AlterField(
            model_name="problem",
            name="io_mode",
            field=models.JSONField(default=problem.models._default_io_mode),
        ),
        migrations.AlterField(
            model_name="problem",
            name="languages",
            field=models.JSONField(),
        ),
        migrations.AlterField(
            model_name="problem",
            name="samples",
            field=models.JSONField(),
        ),
        migrations.AlterField(
            model_name="problem",
            name="statistic_info",
            field=models.JSONField(default=dict),
        ),
        migrations.AlterField(
            model_name="problem",
            name="template",
            field=models.JSONField(),
        ),
        migrations.AlterField(
            model_name="problem",
            name="test_case_score",
            field=models.JSONField(),
        ),
    ]
