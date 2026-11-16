from types import SimpleNamespace
from unittest import TestCase

from ai_tutor.services.explainers import diagnostic
from ai_tutor.services.output_guard import validate_output

SUMA = SimpleNamespace(description="Lee dos enteros A y B con |A|, |B| <= 10^18.", input_description="A y B.",
                       output_description="La suma.")
PRIMOS = SimpleNamespace(description="Cuenta los primos menores o iguales a N (N <= 10^7).", input_description="N.",
                         output_description="La cantidad.")
TEMP = SimpleNamespace(description="Convierte grados.", input_description="Un real.",
                       output_description="El resultado con exactamente dos decimales.")


def submission(result, language="C++", code="", err="", info=None):
    return SimpleNamespace(result=result, language=language, code=code, statistic_info={"err_info": err}, info=info or {})


class ExplainerTests(TestCase):
    def explain(self, *args, **kwargs):
        diag = diagnostic(*args, **kwargs)
        # Toda variante debe ser texto aceptado por el guard y sin citar código ni rutas.
        validate_output({"content": diag["content"] + " " + diag["evidence"], "uncertainty": diag["uncertainty"], "model_version": "x"})
        return diag

    def test_compiler_messages_are_classified_without_quoting(self):
        cases = (
            ("C++", "/app/main.cpp:3:24: error: expected ';' before 'std'", "punto y coma"),
            ("C", "main.c:4:5: error: 'x' undeclared (first use in this function)", "no reconoce"),
            ("Java", "Main.java:1: error: class Solucion is public, should be declared in a file named Solucion.java", "Main"),
            ("Java", "Main.java:5: error: cannot find symbol", "no reconoce"),
            ("Python3", '  File "/app/solution.py", line 2\n    print(a+b)\nIndentationError: unexpected indent', "sangría"),
            ("Python3", '  File "/app/solution.py", line 1\nSyntaxError: invalid syntax', "sintaxis"),
            ("C++", "main.cpp:9:1: error: expected '}' at end of input", "sin cerrar"),
            ("C++", "main.cpp:2:10: fatal error: conio.h: No such file or directory", "biblioteca"),
            ("C++", "error: invalid conversion from 'const char*' to 'int'", "tipos"),
        )
        for language, err, expected in cases:
            with self.subTest(err=err):
                diag = self.explain(submission(-2, language, err=err))
                self.assertEqual(diag["category"], "compilation")
                self.assertIn(expected, diag["content"])
                self.assertNotIn("/app", diag["content"] + diag["evidence"])
                self.assertNotIn("std", diag["content"])

    def test_compiler_line_evidence_is_kept(self):
        diag = self.explain(submission(-2, "C", err="/app/private/main.c:7: error: expected ';'"))
        self.assertEqual(diag["evidence"], "El diagnóstico del compilador menciona la línea 7.")

    def test_runtime_signals_and_language_fallbacks(self):
        fpe = {"data": [{"result": 0, "signal": 0}, {"result": 4, "signal": 8, "exit_code": 0}]}
        self.assertIn("entre cero", self.explain(submission(4, info=fpe))["content"])
        segv = {"data": [{"result": 4, "signal": 11, "exit_code": 0}]}
        self.assertIn("fuera de rango", self.explain(submission(4, info=segv))["content"])
        py = {"data": [{"result": 4, "signal": 0, "exit_code": 1}]}
        self.assertIn("excepción", self.explain(submission(4, "Python3", info=py))["content"])
        self.assertIn("excepción", self.explain(submission(4, "Java", info={"hidden": "x"}))["content"])

    def test_wrong_answer_detects_overflow_risk_and_decimal_format(self):
        overflow = self.explain(submission(-1, "C++", code="int main(){int a,b;std::cin>>a>>b;std::cout<<a+b;}"), SUMA)
        self.assertIn("desbordarse", overflow["content"])
        safe = self.explain(submission(-1, "C++", code="int main(){long long a,b;}"), SUMA)
        self.assertNotIn("desbordarse", safe["content"])
        decimals = self.explain(submission(-1, "Python3", code="c=float(input())\nprint(c*9/5+32)"), TEMP)
        self.assertIn("decimales", decimals["content"])
        generic = self.explain(submission(-1, "Python3", code="print(1)"))
        self.assertIn("carácter por carácter", generic["content"])

    def test_time_limit_detects_nested_loops_against_large_inputs(self):
        python = "n=int(input())\nfor i in range(n):\n    for d in range(2,i):\n        pass\n"
        self.assertIn("bucles anidados", self.explain(submission(1, "Python3", code=python), PRIMOS)["content"])
        cpp = "int main(){for(int i=0;i<n;i++){for(int d=2;d<i;d++) if(i%d==0) k++;}}"
        self.assertIn("bucles anidados", self.explain(submission(1, "C++", code=cpp), PRIMOS)["content"])
        single = "int main(){for(int i=0;i<n;i++) k++; for(int j=0;j<n;j++) k++;}"
        self.assertNotIn("bucles anidados", self.explain(submission(1, "C++", code=single), PRIMOS)["content"])
        self.assertIn("terminen", self.explain(submission(2, "C++", code="int main(){while(1);}"))["content"])

    def test_repeated_verdict_suggests_own_cases(self):
        history = [{"result": -1}, {"result": -1}, {"result": -1}]
        self.assertIn("propios casos", self.explain(submission(-1, "C"), None, history)["content"])
        self.assertNotIn("propios casos", self.explain(submission(-1, "C"), None, history[:2])["content"])
        self.assertNotIn("propios casos", self.explain(submission(0, "C"), None, [{"result": 0}] * 3)["content"])

    def test_every_verdict_produces_guarded_text(self):
        for result in (-2, -1, 0, 1, 2, 3, 4, 5, 8, 99):
            with self.subTest(result=result):
                diag = self.explain(submission(result))
                self.assertTrue(diag["content"])
                self.assertEqual(diag["verdict"], result)
