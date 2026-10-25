from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.models.deletion import ProtectedError
from django.test import SimpleTestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from account.models import AdminType, ProblemPermission, User
from ai_tutor.dataset.schema import ReviewSerializer
from ai_tutor.models import TutorProblemConfig, TutorProblemConfigVersion, TutorSession
from ai_tutor.serializers import ConfigContentSerializer
from ai_tutor.services.problem_config import activate_version, create_draft
from ai_tutor.services.sessions import advance_help_level, create_or_recover
from ai_tutor.tests.config_factory import config_content, initial_configs
from contest.models import Contest
from contest.tests import DEFAULT_CONTEST_DATA
from problem.tests import DEFAULT_PROBLEM_DATA, ProblemCreateTestBase
from utils.api import APIError


class ConfigContentTests(SimpleTestCase):
    def test_initial_two_versions_follow_pb04_and_do_not_claim_human_approval(self):
        initial = initial_configs()
        self.assertEqual(initial["problem"], "Sumar dos enteros.")
        for version in initial["versions"]:
            serializer = ConfigContentSerializer(data=version)
            self.assertTrue(serializer.is_valid(), serializer.errors)
        review = ReviewSerializer(data=initial["review"])
        self.assertTrue(review.is_valid(), review.errors)
        self.assertEqual(review.validated_data["status"], "review")
        self.assertIsNone(review.validated_data["reviewer"])

    def test_rejects_incomplete_duplicate_unknown_and_invalid_levels(self):
        variants = []
        for key in config_content():
            data = config_content()
            del data[key]
            variants.append(data)
        for concepts in ([], [""], ["suma", "SUMA"], [" "], ["x"] * 31):
            variants.append({**config_content(), "concepts": concepts})
        for level in (-1, 0, 4, True, 2.5, "3", None):
            data = config_content()
            data["hint_policy"]["max_help_level"] = level
            variants.append(data)
        for path in ((), ("hint_policy",), ("hint_policy", "hints")):
            data = config_content()
            target = data
            for key in path:
                target = target[key]
            target["unexpected"] = True
            variants.append(data)
        for hints in ({"concept": "Una pista", "location": "Otra pista"},
                      {"concept": "igual", "location": "igual", "strategy": "igual"},
                      {"concept": "", "location": "Ubicación", "strategy": "Estrategia"}):
            data = config_content()
            data["hint_policy"]["hints"] = hints
            variants.append(data)
        variants.append({**config_content(), "schema_version": "2.0"})
        for data in variants:
            with self.subTest(data=data):
                self.assertFalse(ConfigContentSerializer(data=data).is_valid())


class ProblemConfigTests(ProblemCreateTestBase):
    def setUp(self):
        self.owner = self.create_admin()
        self.problem = self.add_problem(DEFAULT_PROBLEM_DATA, self.owner)
        self.versions_url = "/api/admin/ai_tutor/config/versions"
        self.active_url = "/api/admin/ai_tutor/config/active"
        self.activate_url = "/api/admin/ai_tutor/config/activate"
        TutorProblemConfig.objects.create(problem=self.problem, enabled=True)

    def draft(self, index=0, **changes):
        return create_draft(self.owner, self.problem.id, **{**config_content(index), **changes})

    def activate(self, version):
        return self.client.post(self.activate_url, {"problem_id": self.problem.id, "version_id": version.id})

    def test_create_read_activate_two_versions_and_keep_original_session(self):
        payload = {"problem_id": self.problem.id, **config_content()}
        response = self.client.post(self.versions_url, payload)
        self.assertSuccess(response)
        first = response.data["data"]
        self.assertEqual((first["version"], first["status"], first["created_by"]), (1, "draft", self.owner.id))
        self.assertIsNone(first["activated_at"])
        self.assertIsNone(self.client.get(self.active_url, {"problem_id": self.problem.id}).data["data"])
        self.assertSuccess(self.activate(TutorProblemConfigVersion.objects.get(pk=first["id"])))
        first_snapshot = self.client.get(self.active_url, {"problem_id": self.problem.id}).data["data"]
        student = self.create_user("alumno-versionado", "clave")
        session = self.client.post("/api/ai_tutor/session", {"problem_id": self.problem.id}).data["data"]
        self.assertEqual(session["config_version_id"], first["id"])
        self.client.login(username="admin", password="admin")
        second = self.draft(1)
        self.assertEqual(second.version, 2)
        self.assertSuccess(self.activate(second))
        self.assertSuccess(self.activate(second))
        first_snapshot["status"] = "retired"
        detail = self.client.get(self.versions_url, {"problem_id": self.problem.id, "version_id": first["id"]})
        self.assertSuccess(detail)
        self.assertEqual(detail.data["data"], first_snapshot)
        versions = self.client.get(self.versions_url, {"problem_id": self.problem.id}).data["data"]
        self.assertEqual([v["status"] for v in versions], ["retired", "active"])
        self.assertEqual(self.client.get(self.active_url, {"problem_id": self.problem.id}).data["data"]["id"], second.id)
        recovered = create_or_recover(student, self.problem.id)
        self.assertEqual(str(recovered.id), str(session["id"]))
        self.assertEqual(recovered.config_version_id, first["id"])
        recovered.state = "closed"
        recovered.save(update_fields=["state"])
        self.assertEqual(create_or_recover(student, self.problem.id).config_version_id, second.id)
        self.assertFailed(self.activate(TutorProblemConfigVersion.objects.get(pk=first["id"])))

    def test_requires_active_version_before_starting_but_enablement_stays_independent(self):
        self.create_user("sin-version", "clave")
        payload = {"problem_id": self.problem.id}
        availability = self.client.get("/api/ai_tutor/availability", payload).data["data"]
        self.assertTrue(availability["enabled"])
        self.assertFalse(availability["can_start"])
        self.assertFailed(self.client.post("/api/ai_tutor/session", payload))
        version = self.draft()
        self.assertFailed(self.client.post("/api/ai_tutor/session", payload))
        activate_version(self.owner, self.problem.id, version.id)
        self.assertTrue(self.client.get("/api/ai_tutor/availability", payload).data["data"]["can_start"])
        self.assertSuccess(self.client.post("/api/ai_tutor/session", payload))
        TutorProblemConfig.objects.filter(problem=self.problem).update(enabled=False)
        self.assertFailed(self.client.post("/api/ai_tutor/session", payload))

    def test_api_rejects_invalid_content_server_owned_fields_and_editing(self):
        for changes in ({"concepts": []}, {"status": "active"}, {"created_by": self.owner.id}, {"version": 9},
                        {"hint_policy": {"max_help_level": 4, "hints": config_content()["hint_policy"]["hints"]}}):
            self.assertFailed(self.client.post(self.versions_url, {"problem_id": self.problem.id, **config_content(), **changes}))
        self.assertFalse(TutorProblemConfigVersion.objects.exists())
        version = self.draft()
        for method in (self.client.put, self.client.patch, self.client.delete):
            self.assertEqual(method(self.versions_url, {"problem_id": self.problem.id, "version_id": version.id}).status_code, 405)
        self.assertSuccess(self.activate(version))
        for method in (self.client.put, self.client.patch, self.client.delete):
            self.assertEqual(method(self.versions_url, {"problem_id": self.problem.id, "version_id": version.id}).status_code, 405)
        self.assertFailed(self.client.post(self.activate_url, {"problem_id": self.problem.id, "version_id": version.id, "status": "draft"}))

    def test_authorization_and_csrf_cover_all_version_endpoints(self):
        version = self.draft()
        other = self.create_user("otro-docente", "clave", admin_type=AdminType.TEACHER, problem_permission=ProblemPermission.OWN)
        operations = [
            lambda: self.client.get(self.versions_url, {"problem_id": self.problem.id}),
            lambda: self.client.get(self.active_url, {"problem_id": self.problem.id}),
            lambda: self.client.post(self.versions_url, {"problem_id": self.problem.id, **config_content()}),
            lambda: self.activate(version),
        ]
        for role, permission, disabled in ((AdminType.TEACHER, ProblemPermission.OWN, False),
                                           (AdminType.REGULAR_USER, ProblemPermission.NONE, False),
                                           (AdminType.ADMIN, ProblemPermission.ALL, True)):
            other.admin_type, other.problem_permission, other.is_disabled = role, permission, disabled
            other.save()
            for operation in operations:
                self.assertFailed(operation())
        self.client.logout()
        for operation in operations:
            self.assertFailed(operation())
        for role, permission in ((AdminType.TEACHER, ProblemPermission.OWN), (AdminType.ADMIN, ProblemPermission.ALL)):
            self.owner.admin_type, self.owner.problem_permission = role, permission
            self.owner.save()
            self.client.login(username="admin", password="admin")
            for operation in operations:
                self.assertSuccess(operation())
        csrf_client = APIClient(enforce_csrf_checks=True)
        csrf_client.login(username="admin", password="admin")
        self.assertEqual(csrf_client.post(self.versions_url, {"problem_id": self.problem.id, **config_content()}).status_code, 403)
        self.assertEqual(csrf_client.post(self.activate_url, {"problem_id": self.problem.id, "version_id": version.id}).status_code, 403)

    def test_other_problem_contest_and_missing_version_are_rejected(self):
        version = self.draft()
        other = self.add_problem({**DEFAULT_PROBLEM_DATA, "_id": "otro"}, self.owner)
        self.assertFailed(self.client.post(self.activate_url, {"problem_id": other.id, "version_id": version.id}))
        self.assertFailed(self.client.get(self.versions_url, {"problem_id": other.id, "version_id": version.id}))
        self.assertFailed(self.client.post(self.activate_url, {"problem_id": self.problem.id, "version_id": version.id + 1000}))
        self.problem.contest = Contest.objects.create(created_by=self.owner, **DEFAULT_CONTEST_DATA)
        self.problem.save()
        self.assertFailed(self.client.post(self.versions_url, {"problem_id": self.problem.id, **config_content()}))
        self.assertFailed(self.activate(version))
        self.assertFailed(self.client.get(self.active_url, {"problem_id": self.problem.id}))

    def test_immutable_content_and_session_binding_even_with_bulk_updates(self):
        first = self.draft()
        with self.assertRaises(ValidationError):
            first.concepts = ["Otro concepto"]
            first.save()
        first.refresh_from_db()
        # La protección de base de datos incluye también los borradores.
        with self.assertRaises(IntegrityError), transaction.atomic():
            TutorProblemConfigVersion.objects.filter(pk=first.id).update(concepts=["Otro concepto"])
        with self.assertRaises(IntegrityError), transaction.atomic():
            TutorProblemConfigVersion.objects.filter(pk=first.id).update(concept_explanations={"Otro": "Texto distinto"})
        with self.assertRaises(IntegrityError), transaction.atomic():
            TutorProblemConfigVersion.objects.filter(pk=first.id).update(id=first.id + 1000)
        activate_version(self.owner, self.problem.id, first.id)
        session = create_or_recover(self.owner, self.problem.id)
        second = self.draft(1)
        activate_version(self.owner, self.problem.id, second.id)
        for changes in ({"hint_policy": config_content(1)["hint_policy"]}, {"status": "draft", "activated_at": None},
                        {"created_by_id": None}, {"version": 7}):
            with self.assertRaises(IntegrityError), transaction.atomic():
                TutorProblemConfigVersion.objects.filter(pk=first.id).update(**changes)
        for changes in ({"config_version_id": second.id}, {"config_version_id": None}):
            with self.assertRaises(IntegrityError), transaction.atomic():
                TutorSession.objects.filter(pk=session.id).update(**changes)
        with self.assertRaises(ProtectedError):
            first.delete()
        with self.assertRaises(IntegrityError), transaction.atomic():
            second.delete()

    def test_database_uniqueness_status_and_new_session_invariants(self):
        first, second = self.draft(), self.draft(1)
        activate_version(self.owner, self.problem.id, first.id)
        for changes in ({"status": "active", "activated_at": timezone.now()}, {"status": "unknown"}, {"version": first.version}):
            with self.assertRaises(IntegrityError), transaction.atomic():
                TutorProblemConfigVersion.objects.filter(pk=second.id).update(**changes)
        for data in ({}, {"config_version": second}):
            with self.assertRaises(IntegrityError), transaction.atomic():
                TutorSession.objects.create(problem=self.problem, user=self.owner, **data)
        other = self.add_problem({**DEFAULT_PROBLEM_DATA, "_id": "foreign"}, self.owner)
        with self.assertRaises(IntegrityError), transaction.atomic():
            TutorSession.objects.create(problem=other, user=self.owner, config_version=first)

    def test_activation_revalidates_content_and_rolls_back_previous_version_on_failure(self):
        first = self.draft()
        activate_version(self.owner, self.problem.id, first.id)
        invalid = TutorProblemConfigVersion(problem=self.problem, created_by=self.owner, version=2,
                                            **{**config_content(), "concepts": []})
        TutorProblemConfigVersion.objects.bulk_create([invalid])
        with self.assertRaises(APIError):
            activate_version(self.owner, self.problem.id, invalid.id)
        second = self.draft(1)
        with patch.object(TutorProblemConfigVersion, "refresh_from_db", side_effect=RuntimeError("rollback")):
            with self.assertRaises(RuntimeError):
                activate_version(self.owner, self.problem.id, second.id)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual((first.status, second.status), ("active", "draft"))
        self.assertEqual(TutorProblemConfigVersion.objects.filter(status="active").count(), 1)

    def test_help_policy_is_read_from_original_version(self):
        first = self.draft(hint_policy={**config_content()["hint_policy"], "max_help_level": 1})
        with self.assertRaises(IntegrityError), transaction.atomic():
            TutorProblemConfigVersion.objects.filter(pk=first.id).update(id=first.id + 1000)
        activate_version(self.owner, self.problem.id, first.id)
        session = create_or_recover(self.owner, self.problem.id)
        second = self.draft(1)
        activate_version(self.owner, self.problem.id, second.id)
        advance_help_level(session.id, 1)
        with self.assertRaises(ValueError):
            advance_help_level(session.id, 2)
        session.state = "closed"
        session.save(update_fields=["state"])
        new_session = create_or_recover(self.owner, self.problem.id)
        self.assertEqual(advance_help_level(new_session.id, 2).highest_help_level, 2)

    def test_audit_records_effective_activation_once_after_commit(self):
        with patch("ai_tutor.services.problem_config.audit_log") as audit:
            with self.captureOnCommitCallbacks(execute=True):
                version = self.draft()
            self.assertEqual(audit.call_count, 1)
            with self.captureOnCommitCallbacks(execute=True):
                activate_version(self.owner, self.problem.id, version.id)
            self.assertEqual(audit.call_count, 2)
            with self.captureOnCommitCallbacks(execute=True):
                activate_version(self.owner, self.problem.id, version.id)
            self.assertEqual(audit.call_count, 2)


class ProblemConfigConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.assertEqual(connection.vendor, "postgresql")
        self.owner = User.objects.create(username="concurrente-config", admin_type=AdminType.ADMIN, problem_permission=ProblemPermission.OWN)
        self.problem = ProblemCreateTestBase.add_problem(DEFAULT_PROBLEM_DATA, self.owner)
        TutorProblemConfig.objects.create(problem=self.problem, enabled=True)

    def parallel(self, functions):
        barrier = Barrier(len(functions))

        def run(function):
            close_old_connections()
            try:
                user = User.objects.get(pk=self.owner.id)
                barrier.wait(timeout=10)
                return function(user)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=len(functions)) as pool:
            return list(pool.map(run, functions))

    def test_concurrent_drafts_get_distinct_sequential_numbers(self):
        def function(user):
            return create_draft(user, self.problem.id, **config_content()).version

        self.assertEqual(sorted(self.parallel([function, function])), [1, 2])

    def test_concurrent_activations_preserve_both_and_leave_one_active(self):
        versions = [create_draft(self.owner, self.problem.id, **config_content(i)) for i in range(2)]
        self.parallel([lambda user: activate_version(user, self.problem.id, versions[0].id).id,
                       lambda user: activate_version(user, self.problem.id, versions[1].id).id])
        self.assertEqual(sorted(TutorProblemConfigVersion.objects.values_list("status", flat=True)), ["active", "retired"])

    def test_concurrent_identical_activation_is_idempotent(self):
        version = create_draft(self.owner, self.problem.id, **config_content())

        def function(user):
            return activate_version(user, self.problem.id, version.id).id

        self.assertEqual(self.parallel([function, function]), [version.id, version.id])
        self.assertEqual(TutorProblemConfigVersion.objects.filter(status="active").count(), 1)

    def test_activation_racing_session_start_pins_a_complete_version(self):
        first = create_draft(self.owner, self.problem.id, **config_content())
        activate_version(self.owner, self.problem.id, first.id)
        second = create_draft(self.owner, self.problem.id, **config_content(1))
        results = self.parallel([lambda user: create_or_recover(user, self.problem.id).config_version_id,
                                 lambda user: activate_version(user, self.problem.id, second.id).id])
        self.assertIn(results[0], [first.id, second.id])
        session = TutorSession.objects.get()
        self.assertEqual(create_or_recover(self.owner, self.problem.id).config_version_id, session.config_version_id)
        self.assertEqual(TutorProblemConfigVersion.objects.get(status="active").id, second.id)


class ProblemConfigMigrationTests(TransactionTestCase):
    migrate_from = ("ai_tutor", "0002_sesiones_e_intentos")
    migrate_to = ("ai_tutor", "0003_versiones_configuracion")

    def test_migration_preserves_legacy_sessions_and_is_reversible(self):
        executor = MigrationExecutor(connection)
        try:
            executor.migrate([self.migrate_from])
            old_apps = executor.loader.project_state([self.migrate_from]).apps
            user = User.objects.create(username="legado")
            problem = ProblemCreateTestBase.add_problem(DEFAULT_PROBLEM_DATA, user)
            old_apps.get_model("ai_tutor", "TutorProblemConfig").objects.create(problem_id=problem.id, enabled=True)
            old_session = old_apps.get_model("ai_tutor", "TutorSession").objects.create(problem_id=problem.id, user_id=user.id)
            executor = MigrationExecutor(connection)
            executor.migrate([self.migrate_to])
            session = TutorSession.objects.get(pk=old_session.pk)
            self.assertIsNone(session.config_version_id)
            # Los servicios actuales requieren el esquema actual; la transición
            # histórica se comprueba antes de restaurar las migraciones siguientes.
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())
            self.assertEqual(create_or_recover(user, problem.id).id, session.id)
            self.assertFalse(TutorProblemConfigVersion.objects.exists())
            with self.assertRaises(APIError):
                create_or_recover(User.objects.create(username="nuevo-sin-config"), problem.id)
            version = TutorProblemConfigVersion.objects.create(problem_id=problem.id, created_by_id=user.id, version=1, **config_content())
            TutorProblemConfigVersion.objects.filter(pk=version.id).update(status="active", activated_at=timezone.now())
            self.assertIsNone(create_or_recover(user, problem.id).config_version_id)
            with self.assertRaises(IntegrityError), transaction.atomic():
                TutorSession.objects.filter(pk=session.id).update(config_version_id=version.id)
            executor = MigrationExecutor(connection)
            executor.migrate([self.migrate_from])
            old_apps = executor.loader.project_state([self.migrate_from]).apps
            self.assertTrue(old_apps.get_model("ai_tutor", "TutorSession").objects.filter(pk=session.id).exists())
            executor = MigrationExecutor(connection)
            executor.migrate([self.migrate_to])
            self.assertIsNone(TutorSession.objects.get(pk=session.id).config_version_id)
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())
