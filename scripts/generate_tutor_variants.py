"""Ejecuta exclusivamente variantes sintéticas incluidas aquí, sin acceso a red o datos del juez."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time
import uuid

TEMPLATES = {
    "C": ("main.c", '#include <stdio.h>\nint main(void){int a=3,b=2;printf("%d\\n",EXPR);return 0;}\n', "gcc /src/main.c -o /work/main", "/work/main"),
    "C++": ("main.cpp", '#include <iostream>\nint main(){int a=3,b=2;std::cout<<EXPR<<"\\n";}\n', "g++ /src/main.cpp -o /work/main", "/work/main"),
    "Java": ("Main.java", 'class Main {public static void main(String[] args){int a=3,b=2;System.out.println(EXPR);}}\n', "/usr/lib/jvm/java-21-openjdk-amd64/bin/javac -d /work /src/Main.java", "/usr/lib/jvm/java-21-openjdk-amd64/bin/java -Xmx64m -Xss256k -cp /work Main"),
    "Python3": ("main.py", 'a,b=3,2\nprint(EXPR)\n', "python3 -c \"import ast;ast.parse(open('/src/main.py').read())\"", "python3 /src/main.py"),
    "Golang": ("main.go", 'package main\nimport "fmt"\nfunc main(){a,b:=3,2;fmt.Println(EXPR)}\n', "GOCACHE=/work/cache /usr/local/go/bin/go build -o /work/main /src/main.go", "/work/main"),
    "JavaScript": ("main.js", 'let a=3,b=2;console.log(EXPR);\n', "node --check /src/main.js", "node /src/main.js")
}
PROBLEMS = {"sum": ("Sumar los enteros públicos 3 y 2.", "a+b", "a-b", "5"),
            "difference": ("Restar 2 de 3, ambos enteros públicos.", "a-b", "a+b", "1"),
            "product": ("Multiplicar los enteros públicos 3 y 2.", "a*b", "a+b", "6")}


def observe(image, source, compiler, runtime, name):
    started = time.monotonic()
    container = "tutor-variant-" + uuid.uuid4().hex
    with tempfile.TemporaryDirectory() as directory:
        (Path(directory) / name).write_text(source, encoding="utf-8")
        command = 'timeout 45s ' + compiler + ' >/work/compile.log 2>&1; status=$?; if [ "$status" -ne 0 ]; then printf "COMPILE:%s\\n" "$status"; head -c 1500 /work/compile.log; exit 0; fi; timeout 1s ' + runtime + '; status=$?; printf "\\nRUN:%s\\n" "$status"'
        try:
            result = subprocess.run(["docker", "run", "--rm", "--name", container, "--network", "none", "--read-only",
                "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--pids-limit", "64", "--memory", "512m", "--cpus", "1",
                "--user", "65534:65534", "--mount", "type=bind,source=" + str(Path(directory).resolve()) + ",target=/src,readonly",
                "--tmpfs", "/work:rw,exec,nosuid,mode=1777,size=256m", "--tmpfs", "/tmp:rw,nosuid,mode=1777,size=64m",
                "--entrypoint", "sh", image, "-c", command], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
            output = result.stdout.decode(errors="replace")[:4000]
        finally:
            subprocess.run(["docker", "rm", "-f", container], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return output, round((time.monotonic() - started) * 1000)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--problems", nargs="+", choices=list(PROBLEMS), default=list(PROBLEMS))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    image_id = subprocess.check_output(["docker", "image", "inspect", args.image, "--format", "{{.Id}}"], text=True).strip()
    tasks = [(problem, language, mutation) for problem in args.problems for language in TEMPLATES for mutation in ("syntax", "operator", "zero")]

    def execute(task):
        problem, language, mutation = task
        title, expression, wrong, expected = PROBLEMS[problem]
        name, template, compiler, runtime = TEMPLATES[language]
        code = template.replace("EXPR", wrong if mutation == "operator" else ("a/b" if mutation == "zero" else expression))
        if mutation == "syntax":
            code += "\n(\n"
        if mutation == "zero":
            code = code.replace("b=2", "b=0").replace("3,2", "3,0")
        output, latency = observe(image_id, code, compiler, runtime, name)
        if "COMPILE:0" in output:
            raise ValueError("Marcador de compilación inesperado.")
        if output.startswith("COMPILE:"):
            status = int(output.splitlines()[0].split(":")[1])
            verdict, category = (-2, "compilation") if status not in (124, 137) else (5, "unknown")
        elif "RUN:0" in output:
            actual = output.rsplit("RUN:", 1)[0].strip()
            verdict, category = (-1, "unknown") if actual != expected else (0, "unknown")
        elif "RUN:" in output:
            verdict, category = 4, "runtime"
        else:
            verdict, category = 5, "unknown"
        identifier = problem + "-" + language.replace("+", "p") + "-" + mutation
        record = {"schema_version": "1.0", "example_id": identifier, "problem": title, "language": language, "faulty_code": code,
            "verdict": verdict, "category": category, "evidence": ["Ejecución sintética local observada; verificación contra el juez real pendiente."],
            "concept": "Operaciones y sintaxis", "explanation": "Revisa el diagnóstico observado y contrasta la operación con el objetivo público.",
            "uncertainty": {"confidence": 0.4, "alternatives": ["Sintaxis", "Lógica", "Entorno"], "reason": "Ejemplo sintético sin revisión humana ni validación contra el juez desplegado."},
            "hints": {"concept": "Identifica la operación que solicita el enunciado.", "location": "Inspecciona la expresión y las declaraciones.", "strategy": "Traza los valores públicos y contrasta el resultado con el objetivo."},
            "provenance": {"kind": "synthetic", "reference": problem + "#" + mutation, "authorization": None},
            "review": {"author": "generacion-sintetica", "authored_at": datetime.now(timezone.utc).isoformat(), "reviewer": None, "reviewed_at": None, "approved_at": None, "status": "draft", "notes": "Revisión pedagógica y contraste con juez pendientes."}}
        observation = {"example_id": identifier, "original_problem": problem, "mutation": mutation, "image": image_id,
            "source_sha256": hashlib.sha256(code.encode()).hexdigest(), "compiler": compiler, "runtime": runtime,
            "output": output, "elapsed_ms": latency, "observed_result": verdict, "expected_public": expected}
        return record, observation

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(execute, tasks))
    # Los aceptados o fallos del entorno quedan como observaciones, fuera del dataset de errores.
    records = [record for record, _ in results if record["verdict"] not in (0, 5)]
    (args.output / "examples-draft.json").write_text(json.dumps(records, indent=2, ensure_ascii=True), encoding="utf-8")
    (args.output / "observations.json").write_text(json.dumps([item for _, item in results], indent=2, ensure_ascii=True), encoding="utf-8")
    print("Observaciones:", len(results), "Ejemplos en borrador:", len(records), "Aprobaciones humanas: 0")


if __name__ == "__main__":
    main()
