import importlib
import unittest

import app.main as app_main
from app.models import Locale, ReviewerLoginRequest


class AuthStageC1Tests(unittest.TestCase):
    def setUp(self):
        importlib.reload(app_main)

    def test_login_success_and_token_access(self):
        login = app_main.reviewer_login(ReviewerLoginRequest(login="reviewer", password="reviewer123"), locale=Locale.ru)
        self.assertTrue(login.access_token)
        self.assertEqual(login.role, "reviewer")

        kpi = app_main.reviewer_dashboard_kpi(access_token=login.access_token, locale=Locale.ru)
        self.assertTrue(hasattr(kpi, "total_requests"))

    def test_login_invalid_credentials(self):
        denied = app_main.reviewer_login(ReviewerLoginRequest(login="reviewer", password="wrong"), locale=Locale.ru)
        self.assertEqual(denied.status_code, 401)


if __name__ == "__main__":
    unittest.main()
