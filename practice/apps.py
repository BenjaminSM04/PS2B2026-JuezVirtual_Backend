from django.apps import AppConfig


class PracticeConfig(AppConfig):
    name = "practice"

    def ready(self):
        from django.db.models.signals import post_save
        from practice.services import on_submission_saved
        post_save.connect(on_submission_saved, sender="submission.Submission", dispatch_uid="practice_accepted_achievement")
