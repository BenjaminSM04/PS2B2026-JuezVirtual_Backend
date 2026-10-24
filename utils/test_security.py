from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from threading import Barrier
from types import SimpleNamespace
from zipfile import ZipFile
from django.test import SimpleTestCase
from account.decorators import BasePermissionDecorator
from account.serializers import ImageUploadForm
from django.core.files.uploadedfile import SimpleUploadedFile
from utils.api import APIError
from utils.archive import validate_archive
from utils.sanitize import clean_html


class SecurityTests(SimpleTestCase):
    def test_permissions_are_isolated_between_threads(self):
        barrier = Barrier(2)

        class Permission(BasePermissionDecorator):
            def check_permission(self):
                barrier.wait(timeout=10)
                return self.request.user.allowed

        permission = Permission(lambda view, request: request.user.name)
        users = [SimpleNamespace(allowed=True, is_disabled=False, name="permitido"), SimpleNamespace(allowed=False, is_disabled=False, name="denegado")]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda user: permission(None, SimpleNamespace(user=user)), users))
        self.assertEqual(results[0], "permitido")
        self.assertNotEqual(results[1], "denegado")

    def test_html_keeps_format_and_formula_but_removes_active_content(self):
        html = '<p style="color:red;text-align:center;background-image:url(javascript:bad)">$a + b$</p><table><tr><td>uno</td></tr></table><script>evil()</script><img src="javascript:evil()" onerror="evil()">'
        safe = clean_html(html)
        self.assertIn("$a + b$", safe)
        self.assertIn("color:red", safe.replace(" ", ""))
        self.assertIn("<table>", safe)
        self.assertNotIn("javascript", safe)
        self.assertNotIn("evil", safe)
        self.assertNotIn("background-image", safe)

    def test_fake_image_and_unsafe_archive_rejected(self):
        form = ImageUploadForm(files={"image": SimpleUploadedFile("fake.png", b"<script>bad</script>")})
        self.assertFalse(form.is_valid())
        for name in ("../1.in", "/1.in", "C:/1.in", "..\\1.in"):
            data = BytesIO()
            with ZipFile(data, "w") as archive:
                archive.writestr(name, "x")
            data.seek(0)
            with ZipFile(data) as archive, self.assertRaises(APIError):
                validate_archive(archive)
