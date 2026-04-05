import importlib
import json
import unittest

import app.main as app_main
from app.models import (
    EquipmentType,
    Locale,
    NewIssueCreateRequest,
    ReplacementCreateRequest,
    StartSessionRequest,
)


def response_to_dict(response):
    if isinstance(response, dict):
        return response
    if hasattr(response, "body"):
        body = response.body.decode("utf-8") if isinstance(response.body, (bytes, bytearray)) else response.body
        return json.loads(body)
    return response


class ApiIntegrationTests(unittest.TestCase):
    def setUp(self):
        importlib.reload(app_main)

    def test_start_session_success(self):
        payload = StartSessionRequest(
            telegram_user_id=9001,
            locale=Locale.uz,
            fio_input="Ali Valiyev",
            bxm_code="12345",
        )
        response = app_main.start_session(payload)

        self.assertEqual(response.telegram_account_id, 1)
        self.assertEqual(response.branch["bxm_code"], "12345")
        self.assertEqual(response.message_key, "session_bxm_confirmed")

    def test_replacement_returns_localized_error(self):
        payload = ReplacementCreateRequest(
            telegram_user_id=9002,
            locale=Locale.ru,
            bxm_code="12345",
            fio="Ali Valiyev",
            position="Специалист",
            equipment_type=EquipmentType.printer,
            inventory_code="PR-0001",
            reason_text="Нужна замена",
        )

        response = app_main.create_replacement(payload)
        body = response_to_dict(response)

        self.assertEqual(response.status_code, 422)
        self.assertEqual(body["error_code"], "REPLACEMENT_YEAR_BLOCKED")
        self.assertEqual(body["message_key"], "replacement_year_blocked")
        self.assertIn("замена", body["message_text"].lower())

    def test_status_requests_404_for_unknown_fio(self):
        create_payload = NewIssueCreateRequest(
            telegram_user_id=777,
            locale=Locale.uz,
            bxm_code="12345",
            fio="Ali Valiyev",
            position="Mutaxassis",
            equipment_type=EquipmentType.computer,
            reason_text="Yangi ish joyi",
        )
        app_main.create_new_issue(create_payload)

        response = app_main.get_status_requests(
            telegram_user_id=777,
            fio_query="Not Existing",
            page=1,
            page_size=10,
            locale=Locale.uz,
        )
        body = response_to_dict(response)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(body["error_code"], "FIO_NOT_FOUND")
        self.assertEqual(body["message_key"], "fio_not_found")


if __name__ == "__main__":
    unittest.main()
