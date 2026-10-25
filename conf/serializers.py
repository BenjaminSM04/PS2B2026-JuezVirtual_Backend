from utils.api import serializers

from .models import JudgeServer


class EditSMTPConfigSerializer(serializers.Serializer):
    server = serializers.CharField(max_length=128)
    port = serializers.IntegerField(default=25, min_value=1, max_value=65535)
    email = serializers.EmailField(max_length=256)
    username = serializers.CharField(max_length=256, required=False, allow_blank=True)
    password = serializers.CharField(max_length=512, required=False, allow_null=True, allow_blank=True, trim_whitespace=False)
    tls = serializers.BooleanField()
    ssl = serializers.BooleanField(required=False)

    def validate(self, data):
        if data.get("ssl") and data.get("tls"):
            raise serializers.ValidationError("Seleccione SSL o STARTTLS, no ambos.")
        return data


class CreateSMTPConfigSerializer(EditSMTPConfigSerializer):
    password = serializers.CharField(max_length=512, trim_whitespace=False)


class TestSMTPConfigSerializer(serializers.Serializer):
    email = serializers.EmailField()


class CreateEditWebsiteConfigSerializer(serializers.Serializer):
    website_base_url = serializers.CharField(max_length=128)
    website_name = serializers.CharField(max_length=64)
    website_name_shortcut = serializers.CharField(max_length=64)
    website_footer = serializers.CharField(max_length=1024 * 1024)
    allow_register = serializers.BooleanField()
    submission_list_show_all = serializers.BooleanField()


class JudgeServerSerializer(serializers.ModelSerializer):
    status = serializers.CharField()

    class Meta:
        model = JudgeServer
        fields = "__all__"


class JudgeServerHeartbeatSerializer(serializers.Serializer):
    hostname = serializers.CharField(max_length=128)
    judger_version = serializers.CharField(max_length=32)
    cpu_core = serializers.IntegerField(min_value=1)
    memory = serializers.FloatField(min_value=0, max_value=100)
    cpu = serializers.FloatField(min_value=0, max_value=100)
    action = serializers.ChoiceField(choices=("heartbeat", ))
    service_url = serializers.CharField(max_length=256)


class EditJudgeServerSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    is_disabled = serializers.BooleanField()
