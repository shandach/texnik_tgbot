import importlib
import unittest

import app.main as app_main
from app.models import EquipmentType, Locale, NewIssueCreateRequest, ReviewerStatusUpdateRequest


class DashboardStageFTests(unittest.TestCase):
    def setUp(self):
        importlib.reload(app_main)
        p1 = NewIssueCreateRequest(
            telegram_user_id=1,
            locale=Locale.uz,
            bxm_code="12345",
            fio="Ali Valiyev",
            position="Mutaxassis",
            equipment_type=EquipmentType.computer,
            reason_text="Yangi ish joyi",
        )
        p2 = NewIssueCreateRequest(
            telegram_user_id=2,
            locale=Locale.uz,
            bxm_code="12345",
            fio="Vali Aliyev",
            position="Mutaxassis",
            equipment_type=EquipmentType.printer,
            reason_text="Yangi ish joyi",
        )
        r1 = app_main.create_new_issue(p1)
        r2 = app_main.create_new_issue(p2)
        app_main.reviewer_update_status(
            request_id=r1.request_id,
            payload=ReviewerStatusUpdateRequest(status="closed", final_decision="approved"),
            actor_role="reviewer",
        )
        app_main.reviewer_update_status(
            request_id=r2.request_id,
            payload=ReviewerStatusUpdateRequest(status="closed", final_decision="rejected", reject_reason="Sabab"),
            actor_role="reviewer",
        )

    def test_kpi_counts(self):
        kpi = app_main.reviewer_dashboard_kpi(actor_role="reviewer")
        self.assertEqual(kpi.closed_approved, 1)
        self.assertEqual(kpi.closed_rejected, 1)
        self.assertEqual(kpi.active_requests, 0)

    def test_stream_and_analytics(self):
        stream = app_main.reviewer_dashboard_stream(actor_role="reviewer", page=1, page_size=10)
        self.assertEqual(stream.total, 2)

        analytics = app_main.reviewer_dashboard_analytics(actor_role="reviewer")
        self.assertEqual(analytics.by_request_type.get("new_issue"), 2)
        self.assertTrue(any(v > 0 for v in analytics.by_branch.values()))

    def test_dashboard_forbidden_without_role(self):
        denied = app_main.reviewer_dashboard_kpi(actor_role=None, locale=Locale.ru)
        self.assertEqual(denied.status_code, 403)


if __name__ == "__main__":
    unittest.main()
