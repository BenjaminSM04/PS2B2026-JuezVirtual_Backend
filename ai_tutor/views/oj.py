from account.decorators import session_required as login_required
from ai_tutor.models import TutorProblemConfig, TutorProblemConfigVersion, TutorSession
from ai_tutor.serializers import AttemptRequestSerializer, AttemptSerializer, ProblemIdSerializer, SessionSerializer
from ai_tutor.services.access import can_use_tutor, get_problem
from ai_tutor.services.sessions import create_or_recover, read_session, register_attempt
from utils.api import APIView, validate_serializer


class TutorAvailabilityAPI(APIView):
    @validate_serializer(ProblemIdSerializer)
    def get(self, request):
        problem = get_problem(request.data["problem_id"], visible=True)
        enabled = TutorProblemConfig.objects.filter(problem=problem, enabled=True).exists()
        configured = TutorProblemConfigVersion.objects.filter(problem=problem, status="active").exists()
        existing = request.user.is_authenticated and TutorSession.objects.filter(user=request.user, problem=problem, state="active").exists()
        return self.success({"problem_id": problem.id, "enabled": enabled,
                             "can_start": can_use_tutor(request.user, problem) and bool(configured or existing)})


class TutorSessionAPI(APIView):
    @login_required
    @validate_serializer(ProblemIdSerializer)
    def get(self, request):
        session = read_session(request.user, request.data["problem_id"])
        return self.success(SessionSerializer(session).data if session else None)

    @login_required
    @validate_serializer(ProblemIdSerializer)
    def post(self, request):
        session = create_or_recover(request.user, request.data["problem_id"])
        return self.success(SessionSerializer(session).data)


class TutorAttemptAPI(APIView):
    @login_required
    @validate_serializer(AttemptRequestSerializer)
    def post(self, request):
        attempt = register_attempt(request.user, **request.serializer.validated_data)
        return self.success(AttemptSerializer(attempt).data)


class TutorFeedbackAPI(APIView):
    @login_required
    def post(self, request):
        from ai_tutor.serializers import FeedbackRequestSerializer, FeedbackSerializer
        from ai_tutor.services.feedback import feedback
        serializer = FeedbackRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return self.invalid_serializer(serializer)
        from utils.api import APIError
        from django.core.cache import cache
        from ai_tutor.models import TutorMetric
        import time
        started = time.monotonic()
        try:
            result = feedback(request.user, **serializer.validated_data)
        except APIError as error:
            # Acotar también las métricas de fallos: no crear una fila por cada abuso.
            if cache.add("tutor:failure:" + str(request.user.id) + ":" + str(error.err), True, timeout=60):
                TutorMetric.objects.create(category="unknown", level=0, source="unavailable", latency_ms=int((time.monotonic() - started) * 1000),
                    model_version="", config_version_id=None, outcome="denied")
            raise
        return self.success(FeedbackSerializer(result).data)


class TutorRatingAPI(APIView):
    @login_required
    def post(self, request):
        from ai_tutor.serializers import RatingRequestSerializer
        from ai_tutor.services.feedback import rate
        serializer = RatingRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return self.invalid_serializer(serializer)
        return self.success(rate(request.user, **serializer.validated_data))
