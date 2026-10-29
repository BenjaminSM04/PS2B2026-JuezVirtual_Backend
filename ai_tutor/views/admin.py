from account.decorators import ensure_created_by, problem_permission_required
from ai_tutor.models import TutorProblemConfigVersion
from ai_tutor.serializers import (
    ConfigSerializer, ConfigVersionActivateSerializer, ConfigVersionCreateSerializer,
    ConfigVersionQuerySerializer, ConfigVersionSerializer, ProblemIdSerializer,
)
from ai_tutor.services.access import config_data, get_problem, set_config
from ai_tutor.services.problem_config import activate_version, create_draft, get_version
from utils.api import APIView, validate_serializer


class TutorConfigAPI(APIView):
    @problem_permission_required
    @validate_serializer(ProblemIdSerializer)
    def get(self, request):
        problem = get_problem(request.data["problem_id"])
        ensure_created_by(problem, request.user)
        return self.success(config_data(problem))

    @problem_permission_required
    @validate_serializer(ConfigSerializer)
    def put(self, request):
        return self.success(set_config(request.user, **request.data))


class TutorConfigVersionAPI(APIView):
    @problem_permission_required
    @validate_serializer(ConfigVersionQuerySerializer)
    def get(self, request):
        problem = get_problem(request.data["problem_id"])
        ensure_created_by(problem, request.user)
        if "version_id" in request.data:
            return self.success(ConfigVersionSerializer(get_version(problem, request.data["version_id"])).data)
        versions = TutorProblemConfigVersion.objects.filter(problem=problem)
        return self.success(ConfigVersionSerializer(versions, many=True).data)

    @problem_permission_required
    @validate_serializer(ConfigVersionCreateSerializer)
    def post(self, request):
        version = create_draft(request.user, **request.serializer.validated_data)
        return self.success(ConfigVersionSerializer(version).data)


class TutorActiveConfigAPI(APIView):
    @problem_permission_required
    @validate_serializer(ProblemIdSerializer)
    def get(self, request):
        problem = get_problem(request.data["problem_id"])
        ensure_created_by(problem, request.user)
        version = TutorProblemConfigVersion.objects.filter(problem=problem, status="active").first()
        return self.success(ConfigVersionSerializer(version).data if version else None)


class TutorConfigVersionActivateAPI(APIView):
    @problem_permission_required
    @validate_serializer(ConfigVersionActivateSerializer)
    def post(self, request):
        version = activate_version(request.user, **request.serializer.validated_data)
        return self.success(ConfigVersionSerializer(version).data)
