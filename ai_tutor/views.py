from account.decorators import ensure_created_by, problem_permission_required
from ai_tutor.models import TutorProblemConfig
from ai_tutor.serializers import ConfigSerializer, ProblemIdSerializer
from ai_tutor.services.access import can_use_tutor, config_data, get_problem, set_config
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


class TutorAvailabilityAPI(APIView):
    @validate_serializer(ProblemIdSerializer)
    def get(self, request):
        problem = get_problem(request.data["problem_id"], visible=True)
        enabled = TutorProblemConfig.objects.filter(problem=problem, enabled=True).exists()
        return self.success({"problem_id": problem.id, "enabled": enabled, "can_start": can_use_tutor(request.user, problem)})
