import unittest

from . import _bootstrap
from app.services.failure_diagnostic_service import FailureDiagnosticService


class FailureDiagnosticServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = FailureDiagnosticService()

    def test_diagnoses_selector_not_found(self) -> None:
        diagnosis = self.service.diagnose(
            error=(
                "selenium.common.exceptions.NoSuchElementException: "
                "Message: no such element: Unable to locate element: {'method':'css selector','selector':'#login'}"
            ),
            logs="",
        )

        self.assertEqual(diagnosis.failure_type, "selector_not_found")
        self.assertIn("NoSuchElementException", diagnosis.failure_signal)
        self.assertIn("locator", diagnosis.suspected_root_cause.lower())
        self.assertIn("selectors", diagnosis.repair_hint.lower())

    def test_diagnoses_wait_timeout(self) -> None:
        diagnosis = self.service.diagnose(
            error="selenium.common.exceptions.TimeoutException: Message: Timed out waiting for table header",
            logs="Waiting for .el-table to become visible",
        )

        self.assertEqual(diagnosis.failure_type, "wait_timeout")
        self.assertIn("TimeoutException", diagnosis.failure_signal)
        self.assertIn("waited", diagnosis.suspected_root_cause.lower())
        self.assertIn("explicit waits", diagnosis.repair_hint.lower())

    def test_diagnoses_assertion_failed(self) -> None:
        diagnosis = self.service.diagnose(
            error="AssertionError: expected 'Dashboard' in driver.title, actual 'Login'",
            logs="",
        )

        self.assertEqual(diagnosis.failure_type, "assertion_failed")
        self.assertIn("AssertionError", diagnosis.failure_signal)
        self.assertIn("expected", diagnosis.suspected_root_cause.lower())
        self.assertIn("assertion", diagnosis.repair_hint.lower())


if __name__ == "__main__":
    unittest.main()
