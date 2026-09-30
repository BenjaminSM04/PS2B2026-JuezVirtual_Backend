from django.conf import settings
from django.db import models


class TutorProblemConfig(models.Model):
    problem = models.OneToOneField("problem.Problem", on_delete=models.CASCADE, related_name="tutor_config")
    enabled = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
