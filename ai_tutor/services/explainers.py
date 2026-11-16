"""Diagnóstico conservador a partir del veredicto y evidencia mínima.

Solo se usan el veredicto, el mensaje del compilador, señales/códigos de salida del
juez y el texto público del enunciado. Nunca se citan código, rutas ni casos privados.
"""
import re

UNCERTAINTY = "Diagnóstico basado en el veredicto; no determina una causa exacta sin más evidencia."

MESSAGES = {
    -2: ("compilation", "El compilador rechazó el programa, así que todavía no se ejecutó ningún caso."),
    0: ("unknown", "El juez aceptó este intento. ¡Buen trabajo! No hay un error de ejecución que explicar."),
    1: ("complexity", "Se superó el tiempo de CPU permitido."),
    2: ("complexity", "Se superó el tiempo real permitido; puede haber espera de datos o un ciclo que no termina."),
    3: ("runtime", "Se superó el límite de memoria."),
    4: ("runtime", "El programa terminó con un error de ejecución."),
    5: ("unknown", "El juez informó un error de sistema. No demuestra un error en tu algoritmo; vuelve a intentarlo o consulta al docente."),
    -1: ("unknown", "La salida no coincide con la esperada en al menos un caso."),
    8: ("unknown", "Solo se aceptó parte de la entrega: tu idea funciona en algunos casos, pero no en todos."),
}

# (patrón sobre el mensaje del compilador, consejo). El primero que coincide gana.
COMPILER_HINTS = [
    (r"IndentationError|unexpected indent|expected an indented block|unindent does not match",
     "El error es de sangría: revisa que los bloques usen la misma cantidad de espacios y que no haya sangrías inesperadas."),
    (r"unterminated string|EOL while scanning|unclosed string|unclosed character literal|missing terminating",
     "Hay una cadena o carácter sin cerrar: revisa que cada comilla tenga su pareja."),
    (r"is public, should be declared in a file named",
     "En Java la clase pública debe llamarse Main para que el juez pueda compilarla."),
    (r"expected ';'|';' expected|expected ‘;’",
     "Parece faltar un punto y coma al final de una instrucción, cerca de la línea indicada o justo antes."),
    (r"was not declared|undeclared|cannot find symbol|is not defined|unknown type name",
     "Se usa un nombre que el compilador no reconoce: revisa que esté declarado antes de usarlo y escrito exactamente igual."),
    (r"No such file or directory|fatal error: .*\.h|package .* does not exist",
     "Se intenta incluir una biblioteca que no existe en el juez: revisa el nombre de la cabecera o del paquete."),
    (r"expected '\}'|expected ‘\}’|expected declaration|at end of input|reached end of file while parsing|'\(' was never closed|never closed|unmatched",
     "Hay llaves, paréntesis o corchetes sin cerrar: revisa que cada apertura tenga su cierre."),
    (r"incompatible types|invalid conversion|cannot convert|no matching function|possible lossy conversion|invalid operands",
     "Hay un problema de tipos: un valor no coincide con el tipo que se espera en esa operación o llamada."),
    (r"missing return statement|control reaches end of non-void",
     "Una función que debe devolver un valor puede terminar sin devolverlo."),
    (r"undefined reference to .?main|WinMain",
     "El programa no tiene una función principal reconocible para el lenguaje elegido."),
    (r"SyntaxError|invalid syntax",
     "Hay un error de sintaxis: revisa símbolos como dos puntos, paréntesis y comillas en la línea indicada y la anterior."),
    (r"redefinition|already defined|redeclared",
     "Un mismo nombre se declara dos veces en el mismo ámbito."),
]

# Señales POSIX que informa el juez para errores de ejecución.
SIGNAL_HINTS = {
    11: "El programa intentó acceder a memoria no válida: revisa índices fuera de rango, punteros y recursión muy profunda.",
    8: "Hubo una operación aritmética inválida, típicamente una división o un módulo entre cero.",
    6: "El programa abortó, por ejemplo por una excepción no capturada o una reserva de memoria fallida.",
    7: "Hubo un acceso a memoria mal alineado o fuera de un área válida.",
}
LANGUAGE_RUNTIME = {
    "python": "En Python suele deberse a una excepción: conversión de la entrada a número, índices fuera de rango, divisiones entre cero o recursión demasiado profunda.",
    "java": "En Java suele deberse a una excepción no capturada: índices fuera de rango, objetos nulos, divisiones entre cero o lectura de datos con un formato distinto.",
}

BIG_LIMIT = re.compile(r"10\s*\^\s*(?:1[0-9]|9)|10\*\*(?:1[0-9]|9)|1e(?:1[0-9]|9)\b|\b\d{10,}\b|2\s*\^\s*(?:3[1-9]|[4-6]\d)")
LARGE_N = re.compile(r"10\s*\^\s*[5-9]|10\*\*[5-9]|1e[5-9]\b|\b[1-9]\d{5,}\b|\b\d{1,3}(?:[.,]\d{3}){2,}\b")


def _language(submission):
    language = str(getattr(submission, "language", "") or "").lower()
    if "python" in language:
        return "python"
    if "java" in language and "script" not in language:
        return "java"
    if language in ("c", "c++", "cpp") or language.startswith("c"):
        return "c"
    return language


def _problem_text(problem):
    if problem is None:
        return ""
    parts = [getattr(problem, key, "") or "" for key in ("description", "input_description", "output_description")]
    return re.sub(r"<[^>]*>", " ", " ".join(str(part) for part in parts))[:20000]


def _code(submission):
    return str(getattr(submission, "code", "") or "")[:20000]


def _first_signal(submission):
    info = getattr(submission, "info", None)
    data = info.get("data") if isinstance(info, dict) else None
    if not isinstance(data, list):
        return None, None
    for case in data:
        if isinstance(case, dict) and case.get("result") == 4:
            signal, exit_code = case.get("signal"), case.get("exit_code")
            return (signal if isinstance(signal, int) else None), (exit_code if isinstance(exit_code, int) else None)
    return None, None


def _loop_depth(code, language):
    # Aproximación textual: cuenta bucles anidados por sangría (Python) o llaves.
    loop = re.compile(r"^\s*(?:for|while)\b")
    if language == "python":
        stack, deepest = [], 0
        for line in code.splitlines():
            if not line.strip() or line.strip().startswith("#"):
                continue
            indent = len(line) - len(line.lstrip())
            while stack and stack[-1] >= indent:
                stack.pop()
            if loop.match(line):
                stack.append(indent)
                deepest = max(deepest, len(stack))
        return deepest
    # Lenguajes con llaves: un bucle abre su cuerpo en la siguiente llave o termina
    # en el siguiente ';' fuera de paréntesis (cuerpo de una sola instrucción).
    stack, depth, paren, pending, deepest = [], 0, 0, 0, 0
    for token in re.finditer(r"\b(?:for|while)\b|[{}();]", code):
        text = token.group(0)
        if text in ("for", "while"):
            pending += 1
            deepest = max(deepest, len(stack) + pending)
        elif text == "(":
            paren += 1
        elif text == ")":
            paren = max(0, paren - 1)
        elif text == ";" and paren == 0:
            pending = 0
        elif text == "{":
            depth += 1
            stack.extend([depth] * pending)
            pending = 0
        else:
            while stack and stack[-1] == depth:
                stack.pop()
            depth = max(0, depth - 1)
    return deepest


def _repeated(history, verdict):
    results = [item.get("result") for item in (history or []) if isinstance(item, dict)]
    return len(results) >= 3 and all(result == verdict for result in results[:3])


def _advice(submission, problem, history):
    result = submission.result
    language = _language(submission)
    code = _code(submission)
    text = _problem_text(problem)
    tips = []
    if result == -2:
        raw = str((submission.statistic_info or {}).get("err_info", ""))[:4000]
        for pattern, hint in COMPILER_HINTS:
            if re.search(pattern, raw, re.IGNORECASE):
                tips.append(hint)
                break
        if not tips:
            tips.append("Lee el primer mensaje del compilador: los siguientes suelen ser consecuencia del primero.")
    elif result == 4:
        signal, exit_code = _first_signal(submission)
        if signal in SIGNAL_HINTS:
            tips.append(SIGNAL_HINTS[signal])
        elif language in LANGUAGE_RUNTIME:
            tips.append(LANGUAGE_RUNTIME[language])
        elif exit_code not in (None, 0):
            tips.append("El programa terminó con un código de salida distinto de cero; en C y C++ asegúrate de que la función principal devuelva 0.")
        else:
            tips.append("Revisa índices de arreglos, divisiones y la lectura de datos con el formato exacto del enunciado.")
    elif result == 3:
        tips.append("Revisa el tamaño de los arreglos o listas que reservas y si guardas datos que podrías procesar sobre la marcha.")
    elif result in (1, 2):
        depth = _loop_depth(code, language)
        if LARGE_N.search(text) and depth >= 2:
            tips.append("El enunciado admite entradas grandes y tu programa tiene bucles anidados: "
                        "estima cuántas operaciones hace en el peor caso y busca un enfoque más eficiente.")
        elif LARGE_N.search(text):
            tips.append("El enunciado admite entradas grandes: estima el número de operaciones en el peor caso y compáralo con el límite de tiempo.")
        else:
            tips.append("Comprueba que todos los ciclos terminen y que la lectura de datos no espere más valores de los que existen.")
        if language == "python":
            tips.append("En Python, leer toda la entrada de una vez suele ser más rápido que leer línea por línea en ciclos grandes.")
    elif result in (-1, 8):
        small_types = language in ("c", "java") and re.search(r"\bint\b", code) and not re.search(r"\blong\b|\bint64|\bBigInteger\b", code)
        if BIG_LIMIT.search(text) and small_types:
            tips.append("El enunciado admite valores muy grandes: verifica que el tipo de dato elegido pueda representar los datos y los resultados intermedios sin desbordarse.")
        if re.search(r"decimal", text, re.IGNORECASE) and not re.search(r"%\.\d|\.\d+f|format|round|setprecision|toFixed|printf", code):
            tips.append("La salida pide una cantidad concreta de decimales: revisa que el formato de tu respuesta coincida exactamente.")
        if not tips:
            tips.append("Compara tu salida con la de los ejemplos carácter por carácter, incluidos espacios y saltos de línea, "
                        "y prueba casos límite como cero, negativos o los valores máximos.")
    if result not in (0, 5) and _repeated(history, result):
        tips.append("Llevas varios intentos con el mismo veredicto: crea tus propios casos pequeños y verifica a mano qué debería salir.")
    return " ".join(tips)


def diagnostic(submission, problem=None, history=None):
    result = submission.result
    category, explanation = MESSAGES.get(result, ("unknown", "No existe evidencia suficiente para un diagnóstico."))
    advice = _advice(submission, problem, history) if result in MESSAGES else ""
    evidence = ""
    if result == -2:
        # Solo números de línea explícitos; no se muestran rutas o código citado.
        raw = str((submission.statistic_info or {}).get("err_info", ""))[:4000]
        match = re.search(r"(?:\.(?:c|cpp|cc|java|py|go|js):|line\s+)(\d+)\b", raw)
        if match:
            evidence = "El diagnóstico del compilador menciona la línea " + match.group(1) + "."
    content = (explanation + " " + advice).strip()
    return {"category": category, "verdict": result, "content": content, "evidence": evidence, "uncertainty": UNCERTAINTY}
