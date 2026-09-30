from django.urls import path

from ai_tutor.views import TutorAttemptAPI, TutorAvailabilityAPI, TutorConfigAPI, TutorSessionAPI

urlpatterns = [
    path("admin/ai_tutor/config", TutorConfigAPI.as_view(), name="tutor_config_api"),
    path("ai_tutor/availability", TutorAvailabilityAPI.as_view(), name="tutor_availability_api"),
    path("ai_tutor/session", TutorSessionAPI.as_view(), name="tutor_session_api"),
    path("ai_tutor/attempt", TutorAttemptAPI.as_view(), name="tutor_attempt_api"),
]
