import unittest

from app.models import EquipmentType, Locale, NewIssueCreateRequest, ReviewerStatusUpdateRequest
from app.repository import InMemoryRepository
from app.services import FioNormalizer, RequestService


class StageEOutboxTests(unittest.TestCase):
    def test_create_request_pushes_outbox(self):
        repo = InMemoryRepository()
        service = RequestService(repo=repo, normalizer=FioNormalizer())

        payload = NewIssueCreateRequest(
            telegram_user_id=1,
            locale=Locale.uz,
            bxm_code="12345",
            fio="Ali Valiyev",
            position="Mutaxassis",
            equipment_type=EquipmentType.computer,
            reason_text="Yangi ish joyi",
        )

        created = service.create_new_issue(payload, payload.reason_text)
        self.assertEqual(len(repo.sheet_sync_queue), 1)
        self.assertEqual(repo.sheet_sync_queue[0].request_id, created.request_id)

    def test_status_update_upserts_same_outbox_row(self):
        repo = InMemoryRepository()
        service = RequestService(repo=repo, normalizer=FioNormalizer())

        payload = NewIssueCreateRequest(
            telegram_user_id=1,
            locale=Locale.uz,
            bxm_code="12345",
            fio="Ali Valiyev",
            position="Mutaxassis",
            equipment_type=EquipmentType.computer,
            reason_text="Yangi ish joyi",
        )
        created = service.create_new_issue(payload, payload.reason_text)

        service.update_reviewer_status(
            request_id=created.request_id,
            status="closed",
            final_decision="approved",
            reject_reason=None,
        )

        self.assertEqual(len(repo.sheet_sync_queue), 1)
        self.assertEqual(repo.sheet_sync_queue[0].status, "pending")


if __name__ == "__main__":
    unittest.main()
