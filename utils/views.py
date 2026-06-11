import os
from django.conf import settings
from account.serializers import ImageUploadForm, FileUploadForm
from utils.shortcuts import rand_str
from utils.api import SameOriginCSRFExemptAPIView
import logging

logger = logging.getLogger(__name__)

# Sin extensiones ejecutables/renderizables por el navegador (.html, .svg, .xml...):
# se sirven same-origin desde UPLOAD_PREFIX y permitirian XSS almacenado.
ALLOWED_FILE_SUFFIXES = [
    ".pdf", ".zip", ".rar", ".7z", ".gz", ".tar",
    ".txt", ".md", ".csv", ".in", ".out",
    ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".c", ".cpp", ".h", ".hpp", ".py", ".java",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp"
]


class SimditorImageUploadAPIView(SameOriginCSRFExemptAPIView):
    request_parsers = ()

    def post(self, request):
        form = ImageUploadForm(request.POST, request.FILES)
        if form.is_valid():
            img = form.cleaned_data["image"]
        else:
            return self.response({
                "success": False,
                "msg": "Upload failed",
                "file_path": ""})

        suffix = os.path.splitext(img.name)[-1].lower()
        if suffix not in [".gif", ".jpg", ".jpeg", ".bmp", ".png"]:
            return self.response({
                "success": False,
                "msg": "Unsupported file format",
                "file_path": ""})
        img_name = rand_str(10) + suffix
        try:
            with open(os.path.join(settings.UPLOAD_DIR, img_name), "wb") as imgFile:
                for chunk in img:
                    imgFile.write(chunk)
        except IOError as e:
            logger.error(e)
            return self.response({
                "success": False,
                "msg": "Upload Error",
                "file_path": ""})
        return self.response({
            "success": True,
            "msg": "Success",
            "file_path": f"{settings.UPLOAD_PREFIX}/{img_name}"})


class SimditorFileUploadAPIView(SameOriginCSRFExemptAPIView):
    request_parsers = ()

    def post(self, request):
        form = FileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            file = form.cleaned_data["file"]
        else:
            return self.response({
                "success": False,
                "msg": "Upload failed"
            })

        suffix = os.path.splitext(file.name)[-1].lower()
        if suffix not in ALLOWED_FILE_SUFFIXES:
            return self.response({
                "success": False,
                "msg": "Unsupported file format"
            })
        file_name = rand_str(10) + suffix
        try:
            with open(os.path.join(settings.UPLOAD_DIR, file_name), "wb") as f:
                for chunk in file:
                    f.write(chunk)
        except IOError as e:
            logger.error(e)
            return self.response({
                "success": False,
                "msg": "Upload Error"})
        return self.response({
            "success": True,
            "msg": "Success",
            "file_path": f"{settings.UPLOAD_PREFIX}/{file_name}",
            "file_name": file.name})
