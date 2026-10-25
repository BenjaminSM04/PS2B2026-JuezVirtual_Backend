from django.urls import path
from ai_tutor.views.oj import TutorFeedbackAPI, TutorRatingAPI

from ai_tutor.views import (
    TutorActiveConfigAPI, TutorAttemptAPI, TutorAvailabilityAPI, TutorConfigAPI,
    TutorConfigVersionActivateAPI, TutorConfigVersionAPI, TutorSessionAPI,
)

urlpatterns = [
    path("ai_tutor/feedback", TutorFeedbackAPI.as_view(), name="tutor_feedback_api"),
    path("ai_tutor/rating", TutorRatingAPI.as_view(), name="tutor_rating_api"),
    path("admin/ai_tutor/config", TutorConfigAPI.as_view(), name="tutor_config_api"),
    path("admin/ai_tutor/config/versions", TutorConfigVersionAPI.as_view(), name="tutor_config_versions_api"),
    path("admin/ai_tutor/config/active", TutorActiveConfigAPI.as_view(), name="tutor_config_active_api"),
    path("admin/ai_tutor/config/activate", TutorConfigVersionActivateAPI.as_view(), name="tutor_config_activate_api"),
    path("ai_tutor/availability", TutorAvailabilityAPI.as_view(), name="tutor_availability_api"),
    path("ai_tutor/session", TutorSessionAPI.as_view(), name="tutor_session_api"),
    path("ai_tutor/attempt", TutorAttemptAPI.as_view(), name="tutor_attempt_api"),
]
