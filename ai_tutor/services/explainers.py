"""Diagnóstico conservador a partir del veredicto y evidencia mínima."""
import re


def diagnostic(submission):
    result = submission.result
    messages = {
        -2: ("compilation", "El compilador rechazó el programa. Revisa su diagnóstico; no se ha ejecutado la solución."),
        0: ("unknown", "El juez aceptó este intento. No hay un error de ejecución que explicar."),
        1: ("complexity", "Se superó el tiempo de CPU permitido. Revisa el costo y la terminación; el veredicto no identifica una línea causal."),
        2: ("complexity", "Se superó el tiempo real permitido. Puede haber espera o falta de terminación; no basta para afirmar una causa exacta."),
        3: ("runtime", "Se superó el límite de memoria. Revisa estructuras y tamaños; no se conoce una asignación causal concreta."),
        4: ("runtime", "El programa terminó con un error de ejecución. Sin evidencia adicional no se puede afirmar señal, línea o causa."),
        5: ("unknown", "El juez informó un error de sistema. No demuestra un error en tu algoritmo; vuelve a intentarlo o consulta al docente."),
        -1: ("unknown", "La respuesta no coincide con la esperada. El veredicto por sí solo no permite distinguir lógica, concepto o formato."),
        8: ("unknown", "Solo se aceptó parte de la entrega. Revisa los requisitos y los ejemplos públicos sin inferir casos privados.")}
    category, explanation = messages.get(result, ("unknown", "No existe evidencia suficiente para un diagnóstico."))
    evidence = ""
    if result == -2:
        # Solo números de línea explícitos; no se muestran rutas o código citado.
        raw = str((submission.statistic_info or {}).get("err_info", ""))[:4000]
        match = re.search(r"(?:\.(?:c|cpp|java|py|go|js):|line\s+)(\d+)\b", raw)
        if match:
            evidence = "El diagnóstico del compilador menciona la línea " + match.group(1) + "."
    return {"category": category, "verdict": result, "content": explanation, "evidence": evidence,
            "uncertainty": "Diagnóstico basado en el veredicto; no determina una causa exacta sin más evidencia."}
