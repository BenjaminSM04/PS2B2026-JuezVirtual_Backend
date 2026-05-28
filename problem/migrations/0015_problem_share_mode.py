from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('problem', '0014_problem_share_submission'),
    ]

    operations = [
        migrations.AddField(
            model_name='problem',
            name='share_mode',
            field=models.TextField(default='Shared'),
        ),
    ]
