import unittest

from . import _bootstrap
from app.services.execution_service import validate_generated_code


class ExecutionSafetyTests(unittest.TestCase):
    def test_allows_basic_selenium_script(self) -> None:
        code = (
            "from selenium import webdriver\n"
            "from selenium.webdriver.common.by import By\n"
            "import time\n"
            "driver = webdriver.Chrome()\n"
            "time.sleep(1)\n"
            "print('Test Completed')\n"
        )
        self.assertEqual(validate_generated_code(code), [])

    def test_allows_urllib_quote_plus_for_search_urls(self) -> None:
        code = (
            "from urllib.parse import quote_plus\n"
            "url = f'https://www.baidu.com/s?wd={quote_plus(\"DeepSeek\")}'\n"
            "print(url)\n"
        )
        self.assertEqual(validate_generated_code(code), [])

    def test_blocks_dangerous_imports(self) -> None:
        code = "import os\nos.system('dir')\n"
        errors = validate_generated_code(code)
        self.assertTrue(any("Import 'os'" in issue for issue in errors))
        self.assertTrue(any("os.system" in issue for issue in errors))


if __name__ == "__main__":
    unittest.main()