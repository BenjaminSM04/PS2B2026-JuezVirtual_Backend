import uuid

from django.conf import settings
from django.db import models


class TutorProblemConfig(models.Model):
    problem = models.OneToOneField("problem.Problem", on_delete=models.CASCADE, related_name="tutor_config")
    enabled = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class TutorSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    problem = models.ForeignKey("problem.Problem", on_delete=models.CASCADE)
    state = models.CharField(max_length=10, choices=[("active", "Activa"), ("closed", "Cerrada")], default="active")
    highest_help_level = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "problem"], condition=models.Q(state="active"), name="tutor_one_active_session"),
            models.CheckConstraint(check=models.Q(highest_help_level__gte=0, highest_help_level__lte=3), name="tutor_session_level_range"),
            models.CheckConstraint(check=models.Q(state__in=["active", "closed"]), name="tutor_session_state_valid"),
        ]


class TutorAttempt(models.Model):
    session = models.ForeignKey(TutorSession, on_delete=models.CASCADE, related_name="attempts")
    submission = models.ForeignKey("submission.Submission", on_delete=models.PROTECT)
    language = models.CharField(max_length=30)
    result = models.IntegerField()
    help_level = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.UniqueConstraint(fields=["session", "submission"], name="tutor_one_attempt_per_submission"),
            models.CheckConstraint(check=models.Q(help_level__gte=0, help_level__lte=3), name="tutor_attempt_level_range"),
        ]
