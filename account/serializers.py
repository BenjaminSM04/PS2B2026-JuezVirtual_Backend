import re

from django import forms

from utils.api import serializers, UsernameSerializer

from .models import AdminType, ProblemPermission, User, UserProfile, UserProfileLanguage


def validate_password_strength(value):
    # Política de contraseña fuerte: >= 8 caracteres, al menos una mayúscula y un dígito.
    # Se ignora el valor vacío para no romper el password opcional en la edición admin.
    if not value:
        return value
    if len(value) < 8:
        raise serializers.ValidationError("La contraseña debe tener al menos 8 caracteres.")
    if not re.search(r"[A-Z]", value):
        raise serializers.ValidationError("La contraseña debe incluir al menos una letra mayúscula.")
    if not re.search(r"\d", value):
        raise serializers.ValidationError("La contraseña debe incluir al menos un dígito.")
    return value


class UserLoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()
    tfa_code = serializers.CharField(required=False, allow_blank=True)


class UsernameOrEmailCheckSerializer(serializers.Serializer):
    username = serializers.CharField(required=False)
    email = serializers.EmailField(required=False)


class UserRegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=32)
    password = serializers.CharField(min_length=8, validators=[validate_password_strength])
    email = serializers.EmailField(max_length=64)
    real_name = serializers.CharField(max_length=32, allow_blank=True, required=False)
    captcha = serializers.CharField()


class UserChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField()
    new_password = serializers.CharField(min_length=8, validators=[validate_password_strength])
    tfa_code = serializers.CharField(required=False, allow_blank=True)


class UserChangeEmailSerializer(serializers.Serializer):
    password = serializers.CharField()
    new_email = serializers.EmailField(max_length=64)
    tfa_code = serializers.CharField(required=False, allow_blank=True)


class GenerateUserSerializer(serializers.Serializer):
    prefix = serializers.CharField(max_length=16, allow_blank=True)
    suffix = serializers.CharField(max_length=16, allow_blank=True)
    number_from = serializers.IntegerField()
    number_to = serializers.IntegerField()
    password_length = serializers.IntegerField(max_value=16, default=8)


class ImportUserSeralizer(serializers.Serializer):
    users = serializers.ListField(
        child=serializers.ListField(child=serializers.CharField(max_length=64)))


class UserAdminSerializer(serializers.ModelSerializer):
    real_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "email", "admin_type", "problem_permission", "real_name",
                  "create_time", "last_login", "two_factor_auth", "open_api", "is_disabled"]

    def get_real_name(self, obj):
        return obj.userprofile.real_name


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "admin_type", "problem_permission",
                  "create_time", "last_login", "two_factor_auth", "open_api", "is_disabled"]


class UserProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    real_name = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        self.show_real_name = kwargs.pop("show_real_name", False)
        super(UserProfileSerializer, self).__init__(*args, **kwargs)

    def get_real_name(self, obj):
        return obj.real_name if self.show_real_name else None


class EditUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField(max_length=32)
    real_name = serializers.CharField(max_length=32, allow_blank=True, allow_null=True)
    password = serializers.CharField(min_length=8, allow_blank=True, required=False, default=None,
                                     validators=[validate_password_strength])
    email = serializers.EmailField(max_length=64)
    admin_type = serializers.ChoiceField(choices=(AdminType.REGULAR_USER, AdminType.TEACHER,
                                                  AdminType.ADMIN, AdminType.SUPER_ADMIN))
    problem_permission = serializers.ChoiceField(choices=(ProblemPermission.NONE, ProblemPermission.OWN,
                                                          ProblemPermission.ALL))
    open_api = serializers.BooleanField()
    two_factor_auth = serializers.BooleanField()
    is_disabled = serializers.BooleanField()


class EditUserProfileSerializer(serializers.Serializer):
    real_name = serializers.CharField(max_length=32, allow_null=True, required=False)
    avatar = serializers.CharField(max_length=256, allow_blank=True, required=False)
    blog = serializers.URLField(max_length=256, allow_blank=True, required=False)
    mood = serializers.CharField(max_length=256, allow_blank=True, required=False)
    github = serializers.URLField(max_length=256, allow_blank=True, required=False)
    school = serializers.CharField(max_length=64, allow_blank=True, required=False)
    major = serializers.CharField(max_length=64, allow_blank=True, required=False)
    language = serializers.ChoiceField(
        choices=[item[0] for item in UserProfileLanguage.choices()],
        allow_blank=True,
        required=False,
    )


class ApplyResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    captcha = serializers.CharField()


class ResetPasswordSerializer(serializers.Serializer):
    token = serializers.CharField()
    password = serializers.CharField(min_length=8, validators=[validate_password_strength])
    captcha = serializers.CharField()


class SSOSerializer(serializers.Serializer):
    token = serializers.CharField()


class TwoFactorAuthCodeSerializer(serializers.Serializer):
    code = serializers.IntegerField()


class ImageUploadForm(forms.Form):
    image = forms.ImageField()

    def clean_image(self):
        image = self.cleaned_data["image"]
        if image.size > 5 * 1024 * 1024 or image.image.width * image.image.height > 16000000:
            raise forms.ValidationError("La imagen supera el tamaño permitido.")
        import os
        formats = {"PNG": {".png"}, "JPEG": {".jpg", ".jpeg"}, "GIF": {".gif"}, "BMP": {".bmp"}}
        if os.path.splitext(image.name)[1].lower() not in formats.get(image.image.format, set()):
            raise forms.ValidationError("La firma de la imagen no coincide con su extensión.")
        return image


class FileUploadForm(forms.Form):
    file = forms.FileField()

    def clean_file(self):
        import os
        file = self.cleaned_data["file"]
        if file.size > 20 * 1024 * 1024:
            raise forms.ValidationError("El archivo supera 20 MiB.")
        signature = file.read(16)
        file.seek(0)
        suffix = os.path.splitext(file.name)[1].lower()
        signatures = {".pdf": b"%PDF-", ".zip": b"PK", ".docx": b"PK", ".xlsx": b"PK", ".pptx": b"PK", ".gz": b"\x1f\x8b", ".rar": b"Rar!", ".7z": b"7z\xbc\xaf\x27\x1c"}
        if suffix in signatures and not signature.startswith(signatures[suffix]):
            raise forms.ValidationError("La firma del archivo no coincide con su extensión.")
        if suffix in {".png", ".jpg", ".jpeg", ".gif", ".bmp"}:
            image_form = ImageUploadForm(files={"image": file})
            if not image_form.is_valid():
                raise forms.ValidationError("La imagen no es válida.")
            file.seek(0)
        return file


class RankInfoSerializer(serializers.ModelSerializer):
    user = UsernameSerializer()

    class Meta:
        model = UserProfile
        fields = "__all__"
