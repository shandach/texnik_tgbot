import json
import unittest
from pathlib import Path

from app.i18n import I18NService


class I18NMappingTests(unittest.TestCase):
    def test_ru_uz_catalogs_have_same_keys(self):
        uz = json.loads(Path("i18n/uz.json").read_text(encoding="utf-8"))
        ru = json.loads(Path("i18n/ru.json").read_text(encoding="utf-8"))

        self.assertEqual(set(uz.keys()), set(ru.keys()))

    def test_i18n_formats_message_params(self):
        i18n = I18NService()

        ru = i18n.t("ru", "request_created", request_number="REQ-2026-000001")
        uz = i18n.t("uz", "status_rejected_with_reason", reject_reason="Noto'g'ri ma'lumot")

        self.assertIn("REQ-2026-000001", ru)
        self.assertIn("Noto'g'ri", uz)


if __name__ == "__main__":
    unittest.main()
