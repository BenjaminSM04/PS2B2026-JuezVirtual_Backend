from account.decorators import teacher_role_required, ensure_created_by
from utils.api import APIView, validate_serializer
from utils.audit import audit_log

from announcement.models import Announcement
from announcement.serializers import (AnnouncementSerializer, CreateAnnouncementSerializer,
                                      EditAnnouncementSerializer)


class AnnouncementAdminAPI(APIView):
    @validate_serializer(CreateAnnouncementSerializer)
    @teacher_role_required
    def post(self, request):
        """
        publish announcement
        """
        data = request.data
        announcement = Announcement.objects.create(title=data["title"],
                                                   content=data["content"],
                                                   created_by=request.user,
                                                   visible=data["visible"])
        audit_log(request.user, "announcement.create", "Announcement", announcement.id,
                  {"title": announcement.title})
        return self.success(AnnouncementSerializer(announcement).data)

    @validate_serializer(EditAnnouncementSerializer)
    @teacher_role_required
    def put(self, request):
        """
        edit announcement
        """
        data = request.data
        try:
            announcement = Announcement.objects.get(id=data.pop("id"))
            ensure_created_by(announcement, request.user)
        except Announcement.DoesNotExist:
            return self.error("Announcement does not exist")

        for k, v in data.items():
            setattr(announcement, k, v)
        announcement.save()

        audit_log(request.user, "announcement.edit", "Announcement", announcement.id,
                  {"title": announcement.title})
        return self.success(AnnouncementSerializer(announcement).data)

    @teacher_role_required
    def get(self, request):
        """
        get announcement list / get one announcement
        """
        announcement_id = request.GET.get("id")
        if announcement_id:
            try:
                announcement = Announcement.objects.get(id=announcement_id)
                ensure_created_by(announcement, request.user)
                return self.success(AnnouncementSerializer(announcement).data)
            except Announcement.DoesNotExist:
                return self.error("Announcement does not exist")
        announcement = Announcement.objects.all().order_by("-create_time")
        if not request.user.is_super_admin():
            announcement = announcement.filter(created_by=request.user)
        if request.GET.get("visible") == "true":
            announcement = announcement.filter(visible=True)
        return self.success(self.paginate_data(request, announcement, AnnouncementSerializer))

    @teacher_role_required
    def delete(self, request):
        announcement_id = request.GET.get("id")
        if announcement_id:
            try:
                announcement = Announcement.objects.get(id=announcement_id)
            except Announcement.DoesNotExist:
                return self.success()
            ensure_created_by(announcement, request.user)
            announcement_id = announcement.id
            announcement.delete()
            audit_log(request.user, "announcement.delete", "Announcement", announcement_id)
        return self.success()
