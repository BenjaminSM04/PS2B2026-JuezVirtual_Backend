"""Datos ficticios para una demostración aislada; nunca se ejecuta en producción."""
import hashlib
import json
import os
from pathlib import Path
import sys

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from account.models import User, UserProfile, AdminType, ProblemPermission
from ai_tutor.models import TutorProblemConfig
from ai_tutor.services.problem_config import create_draft, activate_version
from judge.language_names import LanguageName
from options.options import SysOptions
from problem.models import Problem, ProblemRuleType


class Command(BaseCommand):
    help = "Crea dos cuentas y seis problemas ficticios solo con OJ_VERIFICATION_ONLY=1; contraseñas por stdin privado."

    @transaction.atomic
    def handle(self, *args, **options):
        if os.environ.get("OJ_VERIFICATION_ONLY") != "1":
            raise CommandError("Este comando requiere el entorno de demostración aislado.")
        names = ("docente-demo", "estudiante-demo")
        if User.objects.exclude(username__in=names).exists():
            raise CommandError("La base contiene usuarios ajenos; no se modificará.")
        try:
            credentials = json.loads(sys.stdin.read(4096))
        except ValueError:
            raise CommandError("Se requiere JSON privado de credenciales por stdin.") from None
        if set(credentials) != {"teacher_password", "student_password"} or any(not isinstance(p, str) or not 12 <= len(p) <= 128 for p in credentials.values()):
            raise CommandError("Credenciales incompletas o longitud no válida.")
        for name, key in zip(names, ("teacher_password", "student_password")):
            user = User.objects.filter(username=name).first()
            if user and not user.check_password(credentials[key]):
                raise CommandError("La contraseña existente cambió; se conserva sin reiniciarla.")
        users = []
        for index, (name, key) in enumerate(zip(names, ("teacher_password", "student_password"))):
            user, created = User.objects.get_or_create(username=name, defaults={"admin_type": AdminType.SUPER_ADMIN if index == 0 else AdminType.REGULAR_USER,
                                                                                "problem_permission": ProblemPermission.ALL if index == 0 else ProblemPermission.NONE})
            if created:
                user.set_password(credentials[key])
                user.save()
            UserProfile.objects.get_or_create(user=user, defaults={"language": "es-LA"})
            users.append(user)
        cases = [(2, 3), (0, 7), (-4, 2)]
        specs = [("SUMA", "Suma de dos enteros", lambda a,b:a+b), ("PRODUCTO", "Producto de dos enteros", lambda a,b:a*b),
                 ("DIFERENCIA", "Diferencia de dos enteros", lambda a,b:a-b), ("MAYOR", "Mayor de dos enteros", max),
                 ("MENOR", "Menor de dos enteros", min), ("CUADRADOS", "Suma de cuadrados", lambda a,b:a*a+b*b)]
        base = Path(settings.DATA_DIR) / "test_case"
        base.mkdir(parents=True, exist_ok=True)
        for code, title, operation in specs:
            case_id = "defensa-" + code.lower()
            directory = base / case_id
            if not directory.resolve().is_relative_to(base.resolve()):
                raise CommandError("El directorio de casos sale del almacenamiento de demostración.")
            directory.mkdir(exist_ok=True)
            info = {"spj": False, "test_case_number": len(cases), "test_cases": {}}
            scores = []
            for number, (a,b) in enumerate(cases, 1):
                source, expected = f"{a} {b}\n", str(operation(a,b)) + "\n"
                for name, content in ((f"{number}.in", source), (f"{number}.out", expected)):
                    path = directory / name
                    if path.exists() and path.read_text(encoding="utf-8") != content:
                        raise CommandError("Un caso existente cambió; se conserva sin sobrescribir.")
                    if not path.exists():
                        path.write_text(content, encoding="utf-8")
                record = {"input_name": f"{number}.in", "output_name": f"{number}.out", "input_size": len(source.encode()),
                          "output_size": len(expected.encode()), "output_md5": hashlib.md5(expected.encode()).hexdigest(),
                          "stripped_output_md5": hashlib.md5(expected.strip().encode()).hexdigest()}
                info["test_cases"][str(number)] = record
                scores.append({**record, "score": 0})
            path = directory / "info"
            serialized = json.dumps(info, sort_keys=True)
            if path.exists() and path.read_text(encoding="utf-8") != serialized:
                raise CommandError("Los metadatos existentes cambiaron; se conservan.")
            if not path.exists():
                path.write_text(serialized, encoding="utf-8")
            problem, _ = Problem.objects.get_or_create(_id="DEF-"+code, contest=None, defaults={"title": title,
                "description": "<p>Ejercicio sintético para la defensa: " + title + ". No utiliza datos de estudiantes.</p>",
                "input_description": "Dos enteros separados por espacios.", "output_description": title + ", seguido de salto de línea.",
                "samples": [{"input": f"{a} {b}", "output": str(operation(a,b))} for a,b in cases], "test_case_id": case_id,
                "test_case_score": scores, "languages": list(LanguageName.choices()), "template": {}, "time_limit": 1000, "memory_limit": 256,
                "rule_type": ProblemRuleType.ACM, "difficulty": "Low", "visible": True, "created_by": users[0], "hint": "", "source": "Demostración sintética"})
            if not problem.tutor_config_versions.exists():
                version = create_draft(users[0], problem.id, schema_version="1.0", concepts=["Operaciones aritméticas", "Control de flujo"],
                    concept_explanations={"Operaciones aritméticas": "Una expresión combina valores según la operación pedida. Contrasta su significado con ejemplos públicos.",
                                          "Control de flujo": "Una condición determina qué instrucciones se ejecutan; una repetición debe avanzar hacia su finalización."},
                    hint_policy={"max_help_level": 3, "hints": {"concept": "Relaciona la operación pedida con los valores de entrada.",
                        "location": "Inspecciona la expresión que produce el resultado y el control de flujo.",
                        "strategy": "Traza los casos públicos y localiza la primera diferencia entre lo esperado y lo observado."}})
                activate_version(users[0], problem.id, version.id)
            TutorProblemConfig.objects.get_or_create(problem=problem, defaults={"enabled": True, "updated_by": users[0]})
        SysOptions.website_name = "LizardJudge — demostración sintética"
        SysOptions.website_name_shortcut = "LizardJudge"
        self.stdout.write("Demostración preparada: dos cuentas ficticias, seis problemas, sin entregas ni resultados sembrados.")
