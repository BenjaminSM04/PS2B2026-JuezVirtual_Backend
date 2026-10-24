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
    concept_explanations = serializers.DictField(child=serializers.CharField(max_length=2000), required=False, default=dict)

    def validate(self, data):
        if set(data.get("concept_explanations", {})) - set(data["concepts"]):
            raise serializers.ValidationError("Las explicaciones deben corresponder a conceptos configurados.")
        return data

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
    concept_explanations = serializers.JSONField()
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
    concepts = serializers.SerializerMethodField()
    feedback = serializers.SerializerMethodField()
    allowed_help_level = serializers.SerializerMethodField()

    def get_allowed_help_level(self, obj):
        from submission.models import Submission
        from ai_tutor.services.sessions import FINAL_RESULTS
        maximum = obj.config_version.hint_policy["max_help_level"] if obj.config_version_id else 0
        if obj.highest_help_level >= maximum:
            return maximum
        last = obj.feedback.filter(action="hint").order_by("-created_at").first()
        eligible = Submission.objects.filter(user_id=obj.user_id, problem_id=obj.problem_id,
            contest__isnull=True, result__in=FINAL_RESULTS, create_time__gte=obj.created_at)
        if last:
            eligible = eligible.filter(create_time__gt=last.created_at)
        return min(maximum, obj.highest_help_level + 1) if eligible.exists() else obj.highest_help_level

    def get_concepts(self, obj):
        return obj.config_version.concepts if obj.config_version_id else []

    def get_feedback(self, obj):
        # El historial no devuelve el contenido de pistas superiores no solicitadas.
        return FeedbackSerializer(obj.feedback.order_by("-created_at")[:20], many=True).data

    def get_attempt_count(self, obj):
        return obj.attempts.count()


class FeedbackRequestSerializer(StrictSerializer):
    session_id = serializers.UUIDField()
    request_id = serializers.UUIDField()
    action = serializers.ChoiceField(choices=["explain", "hint", "concept"])
    level = HelpLevelField(min_value=1, max_value=3, required=False)
    concept = serializers.CharField(max_length=300, required=False)

    def validate(self, data):
        if (data["action"] == "hint") != ("level" in data):
            raise serializers.ValidationError("Solo las pistas requieren nivel.")
        if (data["action"] == "concept") != ("concept" in data):
            raise serializers.ValidationError("Solo las explicaciones conceptuales requieren un concepto.")
        return data


class RatingRequestSerializer(StrictSerializer):
    feedback_id = serializers.UUIDField()
    value = serializers.ChoiceField(choices=["useful", "incorrect"])


class FeedbackSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    submission_id = serializers.CharField(allow_null=True)
    action = serializers.CharField()
    level = serializers.IntegerField()
    concept = serializers.CharField()
    content = serializers.CharField()
    source = serializers.CharField()
    category = serializers.CharField()
    uncertainty = serializers.CharField()
    model_version = serializers.CharField()
    config_version_id = serializers.IntegerField(source="session.config_version_id", allow_null=True)
    latency_ms = serializers.IntegerField()
    created_at = serializers.DateTimeField()
    rating = serializers.SerializerMethodField()

    def get_rating(self, obj):
        from ai_tutor.models import TutorRating
        return TutorRating.objects.filter(feedback=obj).values_list("value", flat=True).first()
