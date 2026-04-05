import importlib.util
import os
import unittest
from datetime import datetime

from app.repository import RequestRecord


HAS_SQLALCHEMY = importlib.util.find_spec("sqlalchemy") is not None
TEST_DB_URL = os.getenv("TEST_DATABASE_URL")


@unittest.skipUnless(HAS_SQLALCHEMY and TEST_DB_URL, "requires sqlalchemy and TEST_DATABASE_URL")
class PostgresRepositoryIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from sqlalchemy import create_engine, text

        cls.text = text
        cls.engine = create_engine(TEST_DB_URL, future=True, pool_pre_ping=True)

        from app.postgres_repository import PostgresRepository

        cls.repo = PostgresRepository(TEST_DB_URL)

    def setUp(self):
        with self.engine.begin() as conn:
            conn.execute(self.text("DELETE FROM request_comments"))
            conn.execute(self.text("DELETE FROM requests"))
            conn.execute(self.text("DELETE FROM inventory"))
            conn.execute(self.text("DELETE FROM telegram_accounts"))
            conn.execute(self.text("DELETE FROM bhm_branches"))

            conn.execute(
                self.text(
                    """
                    INSERT INTO bhm_branches (id, bhm_code, branch_name, region_name, city_name, street_name)
                    VALUES (1, '12345', 'Toshkent Markaz', 'Toshkent', 'Toshkent shahri', 'Amir Temur')
                    """
                )
            )
            conn.execute(
                self.text(
                    """
                    INSERT INTO inventory (id, inventory_code, branch_id, equipment_type, issue_year, status)
                    VALUES (1, 'PC-DB-001', 1, 'computer', 2022, 'active')
                    """
                )
            )

    def test_get_or_create_telegram_account_is_idempotent(self):
        a1 = self.repo.get_or_create_telegram_account(10001)
        a2 = self.repo.get_or_create_telegram_account(10001)

        self.assertEqual(a1.id, a2.id)

    def test_create_and_list_requests_by_tg(self):
        account = self.repo.get_or_create_telegram_account(20001)

        record = RequestRecord(
            id=0,
            request_number=self.repo.next_request_number(),
            telegram_account_id=account.id,
            employee_fio_snapshot="Ali Valiyev",
            employee_fio_normalized_basic="ali valiyev",
            employee_fio_normalized_translit="али валиев",
            employee_position_snapshot="Mutaxassis",
            branch_id=1,
            bhm_code_snapshot="12345",
            branch_name_snapshot="Toshkent Markaz",
            request_type="repair",
            equipment_type="computer",
            inventory_id=1,
            inventory_code_snapshot="PC-DB-001",
            reason_text=None,
            problem_text="No signal",
            status="new",
            final_decision="pending",
            created_at=datetime.utcnow(),
        )

        created = self.repo.create_request(record)
        self.assertGreater(created.id, 0)

        listed = self.repo.list_requests_by_tg(20001)
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0].request_number, created.request_number)

    def test_open_request_check(self):
        account = self.repo.get_or_create_telegram_account(30001)

        record = RequestRecord(
            id=0,
            request_number=self.repo.next_request_number(),
            telegram_account_id=account.id,
            employee_fio_snapshot="Ali Valiyev",
            employee_fio_normalized_basic="ali valiyev",
            employee_fio_normalized_translit="али валиев",
            employee_position_snapshot="Mutaxassis",
            branch_id=1,
            bhm_code_snapshot="12345",
            branch_name_snapshot="Toshkent Markaz",
            request_type="repair",
            equipment_type="computer",
            inventory_id=1,
            inventory_code_snapshot="PC-DB-001",
            reason_text=None,
            problem_text="No signal",
            status="new",
            final_decision="pending",
            created_at=datetime.utcnow(),
        )
        self.repo.create_request(record)

        self.assertTrue(self.repo.has_open_request_for_inventory("PC-DB-001"))


if __name__ == "__main__":
    unittest.main()
