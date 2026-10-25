from django.urls import re_path as url

from ..views.admin import AnnouncementAdminAPI

urlpatterns = [
    url(r"^announcement/?$", AnnouncementAdminAPI.as_view(), name="announcement_admin_api"),
]
