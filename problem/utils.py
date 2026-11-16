import re
from functools import lru_cache

from utils.constants import Difficulty


def difficulty_levels_from_tags(tags):
    tag_levels = {
        "Dificultad: Baja": Difficulty.LOW,
        "Dificultad: Media": Difficulty.MID,
        "Dificultad: Alta": Difficulty.HIGH,
    }
    return {tag_levels[tag] for tag in tags if tag in tag_levels}


def resolve_import_difficulty(problem_info):
    # El serializer valida el campo explícito antes de resolver las etiquetas.
    if "difficulty" in problem_info:
        return problem_info["difficulty"]
    levels = difficulty_levels_from_tags(problem_info.get("tags", []))
    return levels.pop() if len(levels) == 1 else Difficulty.MID


TEMPLATE_BASE = """//PREPEND BEGIN
{}
//PREPEND END

//TEMPLATE BEGIN
{}
//TEMPLATE END

//APPEND BEGIN
{}
//APPEND END"""


@lru_cache(maxsize=100)
def parse_problem_template(template_str):
    prepend = re.findall(r"//PREPEND BEGIN\n([\s\S]+?)//PREPEND END", template_str)
    template = re.findall(r"//TEMPLATE BEGIN\n([\s\S]+?)//TEMPLATE END", template_str)
    append = re.findall(r"//APPEND BEGIN\n([\s\S]+?)//APPEND END", template_str)
    return {"prepend": prepend[0] if prepend else "",
            "template": template[0] if template else "",
            "append": append[0] if append else ""}


@lru_cache(maxsize=100)
def build_problem_template(prepend, template, append):
    return TEMPLATE_BASE.format(prepend, template, append)
