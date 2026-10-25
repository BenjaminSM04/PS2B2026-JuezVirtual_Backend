from rest_framework import serializers
from account.decorators import session_required as login_required
from ai_tutor.dataset.schema import StrictSerializer
from practice.services import mascot, overview, update_mascot
from utils.api import APIView


class StrictBool(serializers.BooleanField):
    def to_internal_value(self, value):
        if type(value) is not bool:
            raise serializers.ValidationError("Se requiere un booleano.")
        return value


class PreferenceSerializer(StrictSerializer):
    color = serializers.ChoiceField(choices=["green", "blue", "amber", "violet"], required=False)
    accessory = serializers.ChoiceField(choices=["none", "scarf", "glasses", "backpack"], required=False)
    visible = StrictBool(required=False)
    animations_enabled = StrictBool(required=False)


class MascotAPI(APIView):
    @login_required
    def get(self, request):
        return self.success(mascot(request.user))

    @login_required
    def patch(self, request):
        serializer = PreferenceSerializer(data=request.data)
        if not serializer.is_valid():
            return self.invalid_serializer(serializer)
        return self.success(update_mascot(request.user, serializer.validated_data))


class OverviewAPI(APIView):
    @login_required
    def get(self, request):
        from django.core.serializers.json import DjangoJSONEncoder
        import json
        return self.success(json.loads(json.dumps(overview(request.user), cls=DjangoJSONEncoder)))
