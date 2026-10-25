from django.conf import settings
from django.db import models


class Achievement(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    # Identidad estable sin FK: ni eliminar el problema ni reevaluarlo borra el logro.
    original_problem_id = models.PositiveIntegerField()
    first_submission_id = models.CharField(max_length=128)
    earned_at = models.DateTimeField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "original_problem_id"], name="practice_unique_achievement")]


class MascotPreference(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    color = models.CharField(max_length=10, default="green")
    accessory = models.CharField(max_length=12, default="none")
    visible = models.BooleanField(default=True)
    animations_enabled = models.BooleanField(default=True)
