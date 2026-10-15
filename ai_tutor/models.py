import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class TutorProblemConfig(models.Model):
    problem = models.OneToOneField("problem.Problem", on_delete=models.CASCADE, related_name="tutor_config")
    enabled = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class TutorProblemConfigVersion(models.Model):
    problem = models.ForeignKey("problem.Problem", on_delete=models.PROTECT, related_name="tutor_config_versions")
    version = models.PositiveIntegerField()
    schema_version = models.CharField(max_length=10)
    concepts = models.JSONField()
    hint_policy = models.JSONField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=[("draft", "Borrador"), ("active", "Activo"), ("retired", "Retirado")], default="draft")
    activated_at = models.DateTimeField(null=True, editable=False)

    class Meta:
        ordering = ["version"]
        constraints = [
            models.UniqueConstraint(fields=["problem", "version"], name="tutor_unique_config_version"),
            models.UniqueConstraint(fields=["problem"], condition=models.Q(status="active"), name="tutor_one_active_config"),
            models.CheckConstraint(check=models.Q(version__gte=1), name="tutor_config_positive_version"),
            models.CheckConstraint(check=models.Q(status="draft", activated_at__isnull=True) |
                                   models.Q(status__in=["active", "retired"], activated_at__isnull=False), name="tutor_config_status_valid"),
        ]

    def clean(self):
        from ai_tutor.serializers import ConfigContentSerializer

        serializer = ConfigContentSerializer(data={key: getattr(self, key) for key in ("schema_version", "concepts", "hint_policy")})
        if not serializer.is_valid():
            raise ValidationError(serializer.errors)

    def save(self, *args, **kwargs):
        if self._state.adding:
            if self.status != "draft" or self.activated_at is not None:
                raise ValidationError("Una versión nueva debe ser un borrador.")
            self.clean()
        else:
            previous = type(self).objects.get(pk=self.pk)
            fields = ("problem_id", "version", "schema_version", "concepts", "hint_policy", "created_by_id", "created_at", "status", "activated_at")
            if any(getattr(self, key) != getattr(previous, key) for key in fields):
                raise ValidationError("Las versiones son inmutables. Cree otro borrador o use el servicio de activación.")
        return super().save(*args, **kwargs)


class TutorSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    problem = models.ForeignKey("problem.Problem", on_delete=models.CASCADE)
    # NULL identifica exclusivamente sesiones anteriores al versionado; no se reconstruye evidencia.
    config_version = models.ForeignKey(TutorProblemConfigVersion, null=True, on_delete=models.PROTECT, related_name="sessions")
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
