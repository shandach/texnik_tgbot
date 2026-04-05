import unittest

from app.models import EquipmentType, Locale, NewIssueCreateRequest, RepairCreateRequest, ReplacementCreateRequest
from app.repository import InMemoryRepository
from app.services import DomainError, FioNormalizer, RequestService


class RequestServiceTests(unittest.TestCase):
    def setUp(self):
        self.repo = InMemoryRepository()
        self.service = RequestService(repo=self.repo, normalizer=FioNormalizer())

    def test_replacement_year_rule_blocks_2024_and_newer(self):
        payload = ReplacementCreateRequest(
            telegram_user_id=1,
            locale=Locale.uz,
            bxm_code="12345",
            fio="Ali Valiyev",
            position="Mutaxassis",
            equipment_type=EquipmentType.printer,
            inventory_code="PR-0001",
            reason_text="eski qurilmani almashtirish",
        )

        with self.assertRaises(DomainError) as err:
            self.service.create_replacement(payload, payload.inventory_code, payload.reason_text)

        self.assertEqual(err.exception.code, "REPLACEMENT_YEAR_BLOCKED")

    def test_repair_has_no_year_restriction(self):
        payload = RepairCreateRequest(
            telegram_user_id=1,
            locale=Locale.uz,
            bxm_code="12345",
            fio="Ali Valiyev",
            position="Mutaxassis",
            equipment_type=EquipmentType.printer,
            inventory_code="PR-0001",
            problem_text="Printer ishlamayapti",
        )

        result = self.service.create_repair(payload, payload.inventory_code, payload.problem_text)
        self.assertEqual(result.status_ui, "processing")
        self.assertTrue(result.request_number.startswith("REQ-"))

    def test_open_request_block_per_inventory(self):
        payload = RepairCreateRequest(
            telegram_user_id=1,
            locale=Locale.uz,
            bxm_code="12345",
            fio="Ali Valiyev",
            position="Mutaxassis",
            equipment_type=EquipmentType.printer,
            inventory_code="PR-0001",
            problem_text="Printer ishlamayapti",
        )

        self.service.create_repair(payload, payload.inventory_code, payload.problem_text)

        with self.assertRaises(DomainError) as err:
            self.service.create_repair(payload, payload.inventory_code, payload.problem_text)

        self.assertEqual(err.exception.code, "INVENTORY_ALREADY_HAS_OPEN_REQUEST")

    def test_status_requests_support_translit_filter(self):
        create_payload = NewIssueCreateRequest(
            telegram_user_id=111,
            locale=Locale.uz,
            bxm_code="12345",
            fio="ALI VALIYEV",
            position="Mutaxassis",
            equipment_type=EquipmentType.computer,
            reason_text="Yangi ish joyi",
        )
        self.service.create_new_issue(create_payload, create_payload.reason_text)

        status = self.service.get_status_requests(telegram_user_id=111, fio_query="ali valiyev", page=1, page_size=10)
        self.assertEqual(status.total, 1)
        self.assertEqual(status.items[0].status_ui, "processing")


if __name__ == "__main__":
    unittest.main()
