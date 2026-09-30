from collections.abc import Mapping

from rest_framework import serializers

from judge.languages import languages


class StrictSerializer(serializers.Serializer):
    """Rechaza campos ajenos al contrato, incluso en objetos anidados."""

    def to_internal_value(self, data):
        if isinstance(data, Mapping):
            unknown = set(data) - set(self.fields)
            if unknown:
                raise serializers.ValidationError({key: "Campo no permitido." for key in sorted(unknown)})
        return super().to_internal_value(data)


class HintsSerializer(StrictSerializer):
    concept = serializers.CharField(max_length=1200)
    location = serializers.CharField(max_length=1200)
    strategy = serializers.CharField(max_length=1200)

    def validate(self, data):
        if len(set(data.values())) != 3:
            raise serializers.ValidationError("Las tres pistas deben tener contenido distinto y progresivo.")
        return data


class UncertaintySerializer(StrictSerializer):
    confidence = serializers.FloatField(min_value=0, max_value=1)
    alternatives = serializers.ListField(child=serializers.CharField(max_length=200), max_length=6)
    reason = serializers.CharField(max_length=1200)


class ProvenanceSerializer(StrictSerializer):
    kind = serializers.ChoiceField(choices=["synthetic", "historical"])
    reference = serializers.CharField(max_length=300)
    authorization = serializers.CharField(allow_null=True, max_length=300)

    def validate(self, data):
        if data["kind"] == "historical" and not data["authorization"]:
            raise serializers.ValidationError("Los datos históricos requieren referencia de autorización.")
        if data["kind"] == "synthetic" and data["authorization"] is not None:
            raise serializers.ValidationError("Un ejemplo sintético no debe simular autorización histórica.")
        return data


class ReviewSerializer(StrictSerializer):
    author = serializers.CharField(max_length=100)
    authored_at = serializers.DateTimeField()
    reviewer = serializers.CharField(allow_null=True, max_length=100)
    reviewed_at = serializers.DateTimeField(allow_null=True)
    approved_at = serializers.DateTimeField(allow_null=True)
    status = serializers.ChoiceField(choices=["draft", "review", "approved", "rejected"])
    notes = serializers.CharField(max_length=2000)

    def validate(self, data):
        if data["reviewer"] and data["reviewer"].casefold() == data["author"].casefold():
            raise serializers.ValidationError("El revisor debe ser distinto del autor.")
        if bool(data["reviewer"]) != bool(data["reviewed_at"]):
            raise serializers.ValidationError("Revisor y fecha de revisión deben aparecer juntos.")
        if data["reviewed_at"] and data["reviewed_at"] < data["authored_at"]:
            raise serializers.ValidationError("La revisión no puede preceder a la autoría.")
        if data["status"] in ("approved", "rejected") and not data["reviewer"]:
            raise serializers.ValidationError("La decisión requiere revisión humana identificada.")
        if data["status"] == "approved":
            if not data["approved_at"] or data["approved_at"] < data["reviewed_at"]:
                raise serializers.ValidationError("La aprobación requiere fecha posterior o igual a la revisión.")
        elif data["approved_at"]:
            raise serializers.ValidationError("Solo el estado approved admite fecha de aprobación.")
        return data


class TutorExampleSerializer(StrictSerializer):
    schema_version = serializers.ChoiceField(choices=["1.0"])
    example_id = serializers.RegexField(r"^[a-zA-Z0-9_-]{1,100}$")
    problem = serializers.CharField(max_length=2000)
    language = serializers.ChoiceField(choices=[item["name"] for item in languages])
    faulty_code = serializers.CharField(max_length=20000, trim_whitespace=False)
    verdict = serializers.ChoiceField(choices=[-2, -1, 1, 2, 3, 4, 5, 8])
    category = serializers.ChoiceField(choices=["compilation", "runtime", "logic", "complexity", "concept", "unknown"])
    evidence = serializers.ListField(child=serializers.CharField(max_length=2000), min_length=1, max_length=20)
    concept = serializers.CharField(max_length=300)
    explanation = serializers.CharField(max_length=2000)
    uncertainty = UncertaintySerializer()
    hints = HintsSerializer()
    provenance = ProvenanceSerializer()
    review = ReviewSerializer()

    def validate(self, data):
        allowed = {"compilation": {-2}, "runtime": {3, 4}, "logic": {-1, 8},
                   "complexity": {1, 2, 3}, "concept": {-1, 8}, "unknown": {-2, -1, 1, 2, 3, 4, 5, 8}}
        if data["verdict"] not in allowed[data["category"]]:
            raise serializers.ValidationError("El veredicto es incompatible con la categoría.")
        uncertainty = data["uncertainty"]
        if data["category"] == "unknown" and (uncertainty["confidence"] > 0.5 or not uncertainty["alternatives"]):
            raise serializers.ValidationError("unknown requiere alternativas y confianza de como máximo 0.5.")
        return data
