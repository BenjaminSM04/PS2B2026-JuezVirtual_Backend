from django.test import SimpleTestCase

from ai_tutor.services.context import CODE_LIMIT, TEXT_LIMIT, clip, clip_code, public_text


class ContextBoundsTests(SimpleTestCase):
    def test_clip_marks_the_cut_and_never_exceeds_the_limit(self):
        self.assertEqual(clip("corto"), "corto")
        self.assertEqual(clip("a" * TEXT_LIMIT), "a" * TEXT_LIMIT)
        cut = clip("a" * (TEXT_LIMIT + 1))
        self.assertEqual((len(cut), cut[-1]), (TEXT_LIMIT, "…"))

    def test_clip_code_keeps_beginning_and_end(self):
        self.assertEqual(clip_code("x = 1"), "x = 1")
        code = "INICIO" + "a" * 10000 + "FINAL"
        cut = clip_code(code)
        self.assertLessEqual(len(cut), CODE_LIMIT)
        self.assertTrue(cut.startswith("INICIO"))
        self.assertTrue(cut.endswith("FINAL"))
        self.assertIn("\n…\n", cut)

    def test_public_text_strips_markup_collapses_whitespace_and_respects_limit(self):
        self.assertEqual(public_text("<p>Hola\n\n  <b>mundo</b> &amp; todos</p>"), "Hola mundo & todos")
        self.assertEqual(public_text(None), "")
        self.assertEqual(len(public_text("palabra " * 1000, limit=50)), 50)
