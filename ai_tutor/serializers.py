from rest_framework import serializers

from ai_tutor.dataset.schema import StrictSerializer


class ProblemIdSerializer(StrictSerializer):
    problem_id = serializers.IntegerField(min_value=1)


class ConfigSerializer(ProblemIdSerializer):
    enabled = serializers.BooleanField()


class AttemptRequestSerializer(StrictSerializer):
    session_id = serializers.UUIDField()
    submission_id = serializers.CharField(max_length=128)


class AttemptSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    submission_id = serializers.CharField()
    language = serializers.CharField()
    result = serializers.IntegerField()
    help_level = serializers.IntegerField()
    created_at = serializers.DateTimeField()


class SessionSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    problem_id = serializers.IntegerField()
    state = serializers.CharField()
    highest_help_level = serializers.IntegerField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
    attempts = AttemptSerializer(many=True)
    attempt_count = serializers.SerializerMethodField()

    def get_attempt_count(self, obj):
        return obj.attempts.count()
