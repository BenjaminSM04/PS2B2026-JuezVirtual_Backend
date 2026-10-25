import ast
import re

VERSION = "texto-2"
PATTERNS = [r"```|<[^>]+>", r"(?im)^\s*(?:#include|def\s+\w+\(|class\s+\w+|function\s+\w+|public\s+static)",
            r"(?im)^\s*(?:import\s|from\s+\w|print\s*\(|console\.log\s*\(|System\.out\.|(?:let|const|var|int|float|double|auto)\s+\w+\s*=)",
            r"\b(?:scanf|input|readline|Scanner|fmt\.Scan)\s*[.(]",
            r"\b(?:print|printf|__import__|eval|exec|open)\s*\(|\b(?:console\.log|System\.out\.\w+|fmt\.Print\w*|std::cout)\b|\b(?:stdin|stdout)\.",
            r"\b(?:gh[pousr]_|github_pat_|sk-(?:proj-|svcacct-)?)[A-Za-z0-9_-]{16,}",
            r"(?i)ignore.{0,25}(?:instructions|instrucciones)|system prompt|prompt del sistema",
            r"(?:[A-Za-z]:[\\/]|/(?:app|data|tmp|home|etc|var)/)",
            r"(?i)(?:password|api[_-]?key|secret|token)\s*[:=]", r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",
            r"\b(?:\d{1,3}\.){3}\d{1,3}\b", r"(?i)(?:casos? ocultos?|hidden tests?|soluci[oó]n oficial)\s*[:=]"]


def validate_output(payload):
    if not isinstance(payload, dict) or set(payload) != {"content", "uncertainty", "model_version"}:
        raise ValueError("schema")
    if any(not isinstance(payload[key], str) for key in payload):
        raise ValueError("type")
    if not 1 <= len(payload["content"].strip()) <= 2000 or len(payload["uncertainty"]) > 500 or not 1 <= len(payload["model_version"]) <= 100:
        raise ValueError("length")
    text = payload["content"] + "\n" + payload["uncertainty"]
    # Reconocer sintaxis, sin ejecutar código: cubre programas Python sin fences
    # y con distintas separaciones, además de las señales de otros lenguajes.
    for candidate in [text] + text.splitlines():
        try:
            tree = ast.parse(candidate.strip())
        except (SyntaxError, ValueError):
            continue
        if any(isinstance(node, (ast.Call, ast.Assign, ast.AugAssign, ast.Import, ast.ImportFrom,
                                 ast.For, ast.While, ast.FunctionDef, ast.ClassDef)) for node in ast.walk(tree)):
            raise ValueError("program-syntax")
    for index, pattern in enumerate(PATTERNS):
        if re.search(pattern, text):
            raise ValueError("rule-" + str(index))
    # Una explicación del tutor es texto; se rechazan estructuras de programas.
    if (text.count(";") >= 2 and re.search(r"\b\w+\s*=\s*[^=]", text)) or text.count("{") + text.count("}") >= 2:
        raise ValueError("code")
    return payload
