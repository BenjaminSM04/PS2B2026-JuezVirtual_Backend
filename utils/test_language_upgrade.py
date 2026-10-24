from copy import deepcopy
from django.test import SimpleTestCase
from judge.languages import languages
from utils.management.commands.update_go_compiler_budget import updated_languages


class CompilerBudgetTests(SimpleTestCase):
    def test_only_exact_legacy_go_is_changed_and_input_is_preserved(self):
        value = deepcopy(languages)
        go = next(item for item in value if item["name"] == "Golang")
        go["config"]["compile"].update(max_cpu_time=3000, max_real_time=5000,
            compile_command="/usr/bin/go build -o {exe_path} {src_path}")
        original = deepcopy(value)
        result, changed = updated_languages(value)
        self.assertEqual(changed, 1)
        self.assertEqual(value, original)
        self.assertEqual(result, languages)
        go["config"]["compile"]["max_real_time"] = 9000
        self.assertEqual(updated_languages(value), (value, 0))
