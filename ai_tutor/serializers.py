from rest_framework import serializers

from ai_tutor.dataset.schema import StrictSerializer


class ProblemIdSerializer(StrictSerializer):
    problem_id = serializers.IntegerField(min_value=1)


class ConfigSerializer(ProblemIdSerializer):
    enabled = serializers.BooleanField()
