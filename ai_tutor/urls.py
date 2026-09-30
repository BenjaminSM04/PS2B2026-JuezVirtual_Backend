from django.urls import path

from ai_tutor.views import TutorAvailabilityAPI, TutorConfigAPI

urlpatterns = [
    path("admin/ai_tutor/config", TutorConfigAPI.as_view(), name="tutor_config_api"),
    path("ai_tutor/availability", TutorAvailabilityAPI.as_view(), name="tutor_availability_api"),
]
