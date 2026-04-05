import importlib
import unittest

import app.main as app_main
from app.models import EquipmentType, Locale, NewIssueCreateRequest, ReviewerCommentCreateRequest, ReviewerStatusUpdateRequest


class ReviewerApiTests(unittest.TestCase):
    def setUp(self):
        importlib.reload(app_main)
        create_payload = NewIssueCreateRequest(
            telegram_user_id=555,
            locale=Locale.uz,
            bxm_code="12345",
            fio="Ali Valiyev",
            position="Mutaxassis",
            equipment_type=EquipmentType.computer,
            reason_text="Yangi ish joyi",
        )
        app_main.create_new_issue(create_payload)

    def test_reviewer_list_and_detail(self):
        listing = app_main.reviewer_list_requests(page=1, page_size=20, actor_role="reviewer")
        self.assertEqual(listing.total, 1)

        detail = app_main.reviewer_request_detail(listing.items[0].id, actor_role="reviewer")
        self.assertEqual(detail.fio, "Ali Valiyev")
        self.assertEqual(detail.status, "new")

    def test_reviewer_comment_and_close(self):
        listing = app_main.reviewer_list_requests(page=1, page_size=20, actor_role="reviewer")
        req_id = listing.items[0].id

        comment = app_main.reviewer_create_comment(
            req_id,
            ReviewerCommentCreateRequest(author_name="Reviewer 1", comment_text="Jarayonda"),
            actor_role="reviewer",
        )
        self.assertEqual(comment.author_name, "Reviewer 1")

        status = app_main.reviewer_update_status(
            req_id,
            ReviewerStatusUpdateRequest(status="closed", final_decision="rejected", reject_reason="Asos yetarli emas"),
            actor_role="reviewer",
        )
        self.assertEqual(status["status"], "closed")
        self.assertEqual(status["final_decision"], "rejected")

        closed_comment_resp = app_main.reviewer_create_comment(
            req_id,
            ReviewerCommentCreateRequest(author_name="Reviewer 1", comment_text="Yana izoh"),
            actor_role="reviewer",
        )
        self.assertEqual(closed_comment_resp.status_code, 422)

    def test_reviewer_endpoints_forbidden_for_missing_role(self):
        denied = app_main.reviewer_list_requests(page=1, page_size=20, actor_role=None, locale=Locale.ru)
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied["error_code"], "FORBIDDEN")


if __name__ == "__main__":
    unittest.main()
