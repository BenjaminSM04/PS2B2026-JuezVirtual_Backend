from rest_framework import serializers

from ai_tutor.dataset.schema import HintsSerializer, StrictSerializer


class ProblemIdSerializer(StrictSerializer):
    problem_id = serializers.IntegerField(min_value=1)


class ConfigSerializer(ProblemIdSerializer):
    enabled = serializers.BooleanField()


class HelpLevelField(serializers.IntegerField):
    def to_internal_value(self, data):
        if type(data) is not int:
            raise serializers.ValidationError("El nivel debe ser un entero entre uno y tres.")
        return super().to_internal_value(data)


class HintPolicySerializer(StrictSerializer):
    max_help_level = HelpLevelField(min_value=1, max_value=3)
    hints = HintsSerializer()


class ConfigContentSerializer(StrictSerializer):
    schema_version = serializers.ChoiceField(choices=["1.0"])
    concepts = serializers.ListField(child=serializers.CharField(max_length=300), min_length=1, max_length=30)
    hint_policy = HintPolicySerializer()

    def validate_concepts(self, value):
        if len({item.casefold() for item in value}) != len(value):
            raise serializers.ValidationError("Los conceptos no deben repetirse.")
        return value


class ConfigVersionCreateSerializer(ConfigContentSerializer):
    problem_id = serializers.IntegerField(min_value=1)


class ConfigVersionQuerySerializer(ProblemIdSerializer):
    version_id = serializers.IntegerField(min_value=1, required=False)


class ConfigVersionActivateSerializer(ProblemIdSerializer):
    version_id = serializers.IntegerField(min_value=1)


class ConfigVersionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    problem_id = serializers.IntegerField()
    version = serializers.IntegerField()
    schema_version = serializers.CharField()
    concepts = serializers.JSONField()
    hint_policy = serializers.JSONField()
    status = serializers.CharField()
    created_by = serializers.IntegerField(source="created_by_id")
    created_at = serializers.DateTimeField()
    activated_at = serializers.DateTimeField(allow_null=True)


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
    config_version_id = serializers.IntegerField(allow_null=True)
    state = serializers.CharField()
    highest_help_level = serializers.IntegerField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
    attempts = AttemptSerializer(many=True)
    attempt_count = serializers.SerializerMethodField()

    def get_attempt_count(self, obj):
        return obj.attempts.count()
