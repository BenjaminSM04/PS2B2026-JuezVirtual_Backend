#!/usr/bin/env python3
import base64
import copy
import random
import string
import hashlib
import json
import os
import zipfile
# defusedxml bloquea XXE y bombas de entidades en XML subido por usuarios
import defusedxml.ElementTree as ET


class FPSParser(object):
    def __init__(self, fps_path=None, string_data=None):
        if fps_path:
            if zipfile.is_zipfile(fps_path):
                from utils.archive import validate_archive
                with zipfile.ZipFile(fps_path) as archive:
                    validate_archive(archive)
                    names = [name for name in archive.namelist() if name.lower().endswith(".xml")]
                    if len(names) != 1 or archive.getinfo(names[0]).file_size > 16 * 1024 * 1024:
                        raise ValueError("El FPS comprimido requiere un único XML de hasta 16 MiB.")
                    self._etree = ET.fromstring(archive.read(names[0]))
            else:
                if os.path.getsize(fps_path) > 16 * 1024 * 1024:
                    raise ValueError("El FPS supera 16 MiB.")
                self._etree = ET.parse(fps_path).getroot()
        elif string_data:
            # fromstring ya devuelve el elemento raiz (no tiene getroot)
            self._etree = ET.fromstring(string_data)
        else:
            raise ValueError("You must tell me the file path or directly give me the data for the file")
        version = self._etree.attrib.get("version", "No Version")
        if version not in ["1.1", "1.2"]:
            raise ValueError("Unsupported version '" + version + "'")

    @property
    def etree(self):
        return self._etree

    def parse(self):
        ret = []
        for node in self._etree:
            if node.tag == "item":
                ret.append(self._parse_one_problem(node))
        return ret

    def _parse_one_problem(self, node):
        sample_start = True
        test_case_start = True
        problem = {"title": "No Title", "description": "No Description",
                   "input": "No Input Description",
                   "output": "No Output Description",
                   "memory_limit": {"unit": None, "value": None},
                   "time_limit": {"unit": None, "value": None},
                   "samples": [], "images": [], "append": [],
                   "template": [], "prepend": [], "test_cases": [],
                   "hint": None, "source": None, "spj": None, "solution": []}
        for item in node:
            tag = item.tag
            if tag in ["title", "description", "input", "output", "hint", "source"]:
                problem[item.tag] = item.text
            elif tag == "time_limit":
                unit = item.attrib.get("unit", "s")
                if unit not in ["s", "ms"]:
                    raise ValueError("Invalid time limit unit")
                problem["time_limit"]["unit"] = "ms"
                value = int(item.text)
                value *= 1000 if unit == "s" else 1
                if not 1 <= value <= 60000:
                    raise ValueError("Invalid time limit value")
                problem["time_limit"]["value"] = value
            elif tag == "memory_limit":
                unit = item.attrib.get("unit", "MB")
                if unit not in ["MB", "KB", "mb", "kb"]:
                    raise ValueError("Invalid memory limit unit")
                problem["memory_limit"]["unit"] = "MB"
                value = int(item.text)
                value = (value + 1023) // 1024 if unit.upper() == "KB" else value
                if not 1 <= value <= 1024:
                    raise ValueError("Invalid memory limit value")
                problem["memory_limit"]["value"] = value
            elif tag in ["template", "append", "prepend", "solution"]:
                lang = item.attrib.get("language")
                if not lang:
                    raise ValueError("Invalid " + tag + ", language name is missed")
                problem[tag].append({"language": lang, "code": item.text})
            elif tag == "spj":
                lang = item.attrib.get("language")
                if not lang:
                    raise ValueError("Invalid spj, language name if missed")
                problem["spj"] = {"language": lang, "code": item.text}
            elif tag == "img":
                problem["images"].append({"src": None, "blob": None})
                for child in item:
                    if child.tag == "src":
                        problem["images"][-1]["src"] = child.text
                    elif child.tag == "base64":
                        problem["images"][-1]["blob"] = base64.b64decode(child.text)
            elif tag == "sample_input":
                if not sample_start:
                    raise ValueError("Invalid xml, error 'sample_input' tag order")
                problem["samples"].append({"input": item.text, "output": None})
                sample_start = False
            elif tag == "sample_output":
                if sample_start:
                    raise ValueError("Invalid xml, error 'sample_output' tag order")
                problem["samples"][-1]["output"] = item.text
                sample_start = True
            elif tag == "test_input":
                if not test_case_start:
                    raise ValueError("Invalid xml, error 'test_input' tag order")
                problem["test_cases"].append({"input": item.text, "output": None})
                test_case_start = False
            elif tag == "test_output":
                if test_case_start:
                    raise ValueError("Invalid xml, error 'test_output' tag order")
                problem["test_cases"][-1]["output"] = item.text
                test_case_start = True

        return problem


class FPSHelper(object):
    def save_image(self, problem, base_dir, base_url):
        _problem = copy.deepcopy(problem)
        for img in _problem["images"]:
            from io import BytesIO
            from PIL import Image
            if len(img["blob"]) > 5 * 1024 * 1024:
                raise ValueError("La imagen FPS supera el tamaño permitido.")
            with Image.open(BytesIO(img["blob"])) as image:
                if image.format not in {"PNG", "JPEG", "GIF", "BMP"} or image.width * image.height > 16000000:
                    raise ValueError("Imagen FPS no permitida.")
                extension = {"PNG": ".png", "JPEG": ".jpg", "GIF": ".gif", "BMP": ".bmp"}[image.format]
                image.verify()
            name = "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(12))
            ext = extension
            file_name = name + ext
            with open(os.path.join(base_dir, file_name), "wb") as f:
                f.write(img["blob"])
            for item in ["description", "input", "output"]:
                _problem[item] = _problem[item].replace(img["src"], os.path.join(base_url, file_name))
        return _problem

    # {
    #     "spj": false,
    #     "test_cases": {
    #         "1": {
    #             "stripped_output_md5": "84f244e41d3c8fd4bdb43ed0e1f7a067",
    #             "input_size": 12,
    #             "output_size": 7,
    #             "input_name": "1.in",
    #             "output_name": "1.out"
    #         }
    #     }
    # }
    def save_test_case(self, problem, base_dir):
        spj = problem.get("spj", {})
        test_cases = {}
        for index, item in enumerate(problem["test_cases"]):
            input_content = item.get("input")
            output_content = item.get("output")
            if input_content:
                with open(os.path.join(base_dir, str(index + 1) + ".in"), "w", encoding="utf-8") as f:
                    f.write(input_content)
            if output_content:
                with open(os.path.join(base_dir, str(index + 1) + ".out"), "w", encoding="utf-8") as f:
                    f.write(output_content)
            if spj:
                one_info = {
                    "input_size": len(input_content.encode("utf-8")),
                    "input_name": f"{index + 1}.in"
                }
            else:
                one_info = {
                    "input_size": len(input_content.encode("utf-8")),
                    "input_name": f"{index + 1}.in",
                    "output_size": len(output_content.encode("utf-8")),
                    "output_name": f"{index + 1}.out",
                    "stripped_output_md5": hashlib.md5(output_content.rstrip().encode("utf-8")).hexdigest()
                }
            test_cases[index] = one_info
        info = {
            "spj": True if spj else False,
            "test_cases": test_cases
        }
        with open(os.path.join(base_dir, "info"), "w", encoding="utf-8") as f:
            f.write(json.dumps(info, indent=4))
        return info


if __name__ == "__main__":
    import pprint

    parser = FPSParser("fps.xml")
    helper = FPSHelper()
    problems = parser.parse()
    for index, problem in enumerate(problems):
        path = os.path.join("/tmp/", str(index + 1))
        os.mkdir(path)
        helper.save_test_case(problem, path)

        pprint.pprint(helper.save_image(problem, "/tmp", "/static/img"))
