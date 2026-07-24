from unittest.mock import patch
from contextlib import asynccontextmanager
import pytest

from app.services.seed_service import generate_secure_password, seed_initial_data, reset_and_seed


class TestGenerateSecurePassword:
    def test_default_length(self):
        pw = generate_secure_password()
        assert len(pw) >= 16

    def test_custom_length(self):
        pw = generate_secure_password(20)
        assert len(pw) == 20

    def test_minimum_length_12(self):
        pw = generate_secure_password(4)
        assert len(pw) >= 12

    def test_contains_all_char_types(self):
        pw = generate_secure_password()
        has_lower = any(c.islower() for c in pw)
        has_upper = any(c.isupper() for c in pw)
        has_digit = any(c.isdigit() for c in pw)
        has_symbol = any(c in "!@#$%^&*()" for c in pw)
        assert has_lower and has_upper and has_digit and has_symbol

    def test_unique_values(self):
        passwords = {generate_secure_password() for _ in range(10)}
        assert len(passwords) > 5


@pytest.fixture
def mock_seed_db(mock_db):
    @asynccontextmanager
    async def _fake():
        yield mock_db
    patcher = patch("app.services.seed_service.get_db", _fake)
    patcher.start()
    yield mock_db
    patcher.stop()


class TestSeedInitialData:
    async def test_no_admin_creates_one(self, mock_seed_db):
        mock_seed_db.add_result(fetchone_result=None)
        mock_seed_db.add_result(fetchone_result=None, rowcount=1, lastrowid=1)
        await seed_initial_data()
        assert "INSERT OR IGNORE INTO users" in mock_seed_db.executed_queries[1]

    async def test_existing_admin_skips(self, mock_seed_db):
        mock_seed_db.add_result(fetchone_result={"id": 1, "email": "admin@dms.com", "role": "super_admin"})
        await seed_initial_data()
        assert len(mock_seed_db.executed_queries) == 1

    async def test_legacy_role_normalized(self, mock_seed_db):
        mock_seed_db.add_result(fetchone_result={"id": 1, "email": "admin@dms.com", "role": "admin"})
        mock_seed_db.add_result(fetchone_result=None, rowcount=1)
        await seed_initial_data()
        assert "UPDATE users" in mock_seed_db.executed_queries[1]

    async def test_insert_fails_rollback(self, mock_seed_db):
        mock_seed_db.add_result(fetchone_result=None)
        mock_seed_db.add_result(fetchone_result=None, rowcount=0)
        await seed_initial_data()


class TestResetAndSeed:
    async def test_clears_all_tables_and_reseeds(self, mock_seed_db):
        for _ in range(16):
            mock_seed_db.add_result(fetchone_result=None, rowcount=1)
        mock_seed_db.add_result(fetchone_result=None)
        mock_seed_db.add_result(fetchone_result=None, rowcount=1, lastrowid=1)

        result = await reset_and_seed()

        assert result["tables_cleared"] == 16
        assert result["users_created"] == 1
        delete_count = sum(1 for q in mock_seed_db.executed_queries if q.startswith("DELETE"))
        assert delete_count == 16
