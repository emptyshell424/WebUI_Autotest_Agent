import unittest

from app.utils.code_parser import clean_code


class CleanCodeTests(unittest.TestCase):
    def test_extracts_python_block(self) -> None:
        raw = "```python\nprint('hello')\n```"
        self.assertEqual(clean_code(raw), "print('hello')")

    def test_strips_fallback_markdown_fence(self) -> None:
        raw = "```\nprint('fallback')\n```"
        self.assertEqual(clean_code(raw), "print('fallback')")


if __name__ == "__main__":
    unittest.main()
