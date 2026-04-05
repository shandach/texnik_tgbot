import importlib
import unittest

import app.main as app_main
from app.models import EquipmentType, Locale, RepairCreateRequest, ReviewerStatusUpdateRequest


class InventoryStageDTests(unittest.TestCase):
    def setUp(self):
        importlib.reload(app_main)

    def test_inventory_filters_flow(self):
        regions = app_main.reviewer_inventory_regions(actor_role="reviewer")
        self.assertIn("Toshkent", regions.regions)

        streets = app_main.reviewer_inventory_streets(region_name="Toshkent", actor_role="reviewer")
        self.assertIn("Amir Temur", streets.streets)

        branches = app_main.reviewer_inventory_branches(region_name="Toshkent", street_name="Amir Temur", actor_role="reviewer")
        self.assertEqual(len(branches.branches), 1)

        inventory = app_main.reviewer_branch_inventory(branch_id=1, actor_role="reviewer")
        self.assertGreaterEqual(len(inventory.items), 1)

    def test_mock_dataset_for_bxm_11673(self):
        regions = app_main.reviewer_inventory_regions(actor_role="reviewer")
        self.assertIn("Ташкент", regions.regions)

        streets = app_main.reviewer_inventory_streets(region_name="Ташкент", actor_role="reviewer")
        self.assertIn("Чиланзар", streets.streets)

        branches = app_main.reviewer_inventory_branches(region_name="Ташкент", street_name="Чиланзар", actor_role="reviewer")
        self.assertEqual(len(branches.branches), 1)
        self.assertEqual(branches.branches[0].bhm_code, "11673")
        self.assertEqual(branches.branches[0].branch_name, "Qatartol BXM")

        inventory = app_main.reviewer_branch_inventory(branch_id=2, actor_role="reviewer")
        by_code = {item.inventory_code: item for item in inventory.items}
        self.assertEqual(by_code["5050801"].equipment_type, "computer")
        self.assertEqual(by_code["5050801"].issue_year, 2023)
        self.assertEqual(by_code["6050802"].equipment_type, "printer")
        self.assertEqual(by_code["6050802"].issue_year, 2024)

    def test_manual_inventory_status_update(self):
        updated = app_main.reviewer_update_inventory_status("PC-0001", "repair", actor_role="reviewer")
        self.assertEqual(updated["status"], "repair")

    def test_repair_approved_auto_updates_inventory_status(self):
        payload = RepairCreateRequest(
            telegram_user_id=900,
            locale=Locale.uz,
            bxm_code="12345",
            fio="Ali Valiyev",
            position="Mutaxassis",
            equipment_type=EquipmentType.computer,
            inventory_code="PC-0001",
            problem_text="No signal",
        )
        created = app_main.create_repair(payload)

        app_main.reviewer_update_status(
            request_id=created.request_id,
            payload=ReviewerStatusUpdateRequest(status="closed", final_decision="approved"),
            actor_role="reviewer",
        )

        inventory = app_main.reviewer_branch_inventory(branch_id=1, actor_role="reviewer")
        item = next(x for x in inventory.items if x.inventory_code == "PC-0001")
        self.assertEqual(item.status, "repair")


if __name__ == "__main__":
    unittest.main()
