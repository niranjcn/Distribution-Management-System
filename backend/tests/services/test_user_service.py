from unittest.mock import patch
from contextlib import asynccontextmanager
import pytest

from app.services.user_service import (
    escape_like,
    get_users,
    get_user_by_id,
    get_user_by_email,
    create_user,
    update_user,
    delete_user,
    update_user_status,
    get_users_by_role,
    get_user_stats,
    update_user_permissions,
    reassign_user,
    get_children_users,
)
from app.models.user import UserCreate, UserUpdate, UserRole


@pytest.fixture
def mock_user_db(mock_db):
    @asynccontextmanager
    async def _fake():
        yield mock_db
    patcher = patch("app.services.user_service.get_db", _fake)
    patcher.start()
    yield mock_db
    patcher.stop()


class TestEscapeLike:
    def test_escapes_special_chars(self):
        assert escape_like("test_%") == "test\\_\\%"

    def test_normal_string_unchanged(self):
        assert escape_like("hello") == "hello"


class TestGetUsers:
    async def test_returns_paginated(self, mock_user_db):
        mock_user_db.add_result(fetchone_result=(2,))
        mock_user_db.add_result(fetchall_result=[
            {"id": 1, "email": "a@t.com", "name": "A", "role": "sub_distributor"},
            {"id": 2, "email": "b@t.com", "name": "B", "role": "cluster"},
        ])
        result = await get_users()
        assert result["pagination"]["total"] == 2
        assert len(result["data"]) == 2

    async def test_filters_by_role(self, mock_user_db):
        mock_user_db.add_result(fetchone_result=(1,))
        mock_user_db.add_result(fetchall_result=[{"id": 1, "email": "op@t.com", "name": "Op", "role": "operator"}])
        result = await get_users(role="operator")
        assert "role = ?" in mock_user_db.executed_queries[0]

    async def test_empty(self, mock_user_db):
        mock_user_db.add_result(fetchone_result=(0,))
        result = await get_users()
        assert result["data"] == []


class TestGetUserById:
    async def test_returns_user(self, mock_user_db):
        mock_user_db.add_result(fetchone_result={"id": 1, "email": "u@t.com", "name": "U", "role": "sub_distributor"})
        result = await get_user_by_id("1")
        assert result["name"] == "U"

    async def test_not_found(self, mock_user_db):
        mock_user_db.add_result(fetchone_result=None)
        result = await get_user_by_id("999")
        assert result is None

    async def test_no_password_hash(self, mock_user_db):
        mock_user_db.add_result(fetchone_result={"id": 1, "email": "u@t.com", "name": "U", "role": "sub_distributor", "password_hash": "secret"})
        result = await get_user_by_id("1")
        assert "password_hash" not in result


class TestGetUserByEmail:
    async def test_returns_user(self, mock_user_db):
        mock_user_db.add_result(fetchone_result={"id": 1, "email": "exists@t.com"})
        result = await get_user_by_email("exists@t.com")
        assert result["email"] == "exists@t.com"

    async def test_not_found(self, mock_user_db):
        mock_user_db.add_result(fetchone_result=None)
        result = await get_user_by_email("no@t.com")
        assert result is None


class TestCreateUser:
    async def test_creates_operator(self, mock_user_db):
        mock_user_db.add_result(fetchone_result=None)
        mock_user_db.add_result(fetchone_result=(0,))
        mock_user_db.add_result(fetchone_result=None, rowcount=1, lastrowid=1)
        mock_user_db.add_result(fetchone_result={"id": 1, "email": "op@t.com", "name": "Op", "role": "operator"})
        mock_user_db.add_result(fetchone_result={"id": 1, "email": "op@t.com"})

        data = UserCreate(email="op@t.com", password="Pass@123", name="Op", role=UserRole.OPERATOR)
        with patch("app.services.user_service.get_password_hash", return_value="hash"):
            result = await create_user(data)
        assert result["email"] == "op@t.com"

    async def test_duplicate_email_raises(self, mock_user_db):
        mock_user_db.add_result(fetchone_result=(1,))
        data = UserCreate(email="exists@t.com", password="Pass@123", name="Exists", role=UserRole.OPERATOR)
        with pytest.raises(ValueError, match="Email already exists"):
            await create_user(data)

    async def test_operator_limit_exceeded_raises(self, mock_user_db):
        mock_user_db.add_result(fetchone_result=None)
        mock_user_db.add_result(fetchone_result=(5000,))
        data = UserCreate(email="too@t.com", password="Pass@123", name="TooMany", role=UserRole.OPERATOR, parent_id="1")
        with pytest.raises(ValueError, match="maximum limit"):
            await create_user(data)


class TestUpdateUser:
    async def test_updates_and_returns(self, mock_user_db):
        mock_user_db.add_result(fetchone_result=None, rowcount=1)
        mock_user_db.add_result(fetchone_result={"id": 1, "email": "upd@t.com", "name": "Updated"})
        data = UserUpdate(name="Updated")
        result = await update_user("1", data)
        assert result["name"] == "Updated"

    async def test_not_found(self, mock_user_db):
        mock_user_db.add_result(fetchone_result=None, rowcount=0)
        mock_user_db.add_result(fetchone_result=None)
        result = await update_user("999", UserUpdate(name="Nope"))
        assert result is None


class TestDeleteUser:
    async def test_returns_true(self, mock_user_db):
        mock_user_db.add_result(fetchone_result=None, rowcount=1)
        result = await delete_user("1")
        assert result is True

    async def test_returns_false(self, mock_user_db):
        mock_user_db.add_result(fetchone_result=None, rowcount=0)
        result = await delete_user("999")
        assert result is False


class TestUpdateUserStatus:
    async def test_updates_status(self, mock_user_db):
        mock_user_db.add_result(fetchone_result=None, rowcount=1)
        mock_user_db.add_result(fetchone_result={"id": 1, "status": "inactive"})
        result = await update_user_status("1", "inactive")
        assert result["status"] == "inactive"

    async def test_not_found(self, mock_user_db):
        mock_user_db.add_result(fetchone_result=None, rowcount=0)
        mock_user_db.add_result(fetchone_result=None)
        result = await update_user_status("999", "inactive")
        assert result is None


class TestGetUsersByRole:
    async def test_returns_active_users(self, mock_user_db):
        mock_user_db.add_result(fetchall_result=[
            {"id": 1, "email": "sd@t.com", "name": "SD", "role": "sub_distributor"},
        ])
        result = await get_users_by_role("sub_distributor")
        assert len(result) == 1

    async def test_empty(self, mock_user_db):
        mock_user_db.add_result(fetchall_result=[])
        result = await get_users_by_role("operator")
        assert result == []


class TestGetUserStats:
    async def test_returns_counts(self, mock_user_db):
        mock_user_db.add_result(fetchone_result=(50,))
        mock_user_db.add_result(fetchone_result=(40,))
        mock_user_db.add_result(fetchall_result=[("operator", 5), ("cluster", 3)])
        result = await get_user_stats()
        assert result["total"] == 50
        assert result["active"] == 40
        assert len(result["by_role"]) > 0

    async def test_zero_counts(self, mock_user_db):
        mock_user_db.add_result(fetchone_result=(0,))
        mock_user_db.add_result(fetchone_result=(0,))
        mock_user_db.add_result(fetchall_result=[])
        result = await get_user_stats()
        assert result["total"] == 0
        assert result["active"] == 0


class TestUpdateUserPermissions:
    async def test_updates_and_returns(self, mock_user_db):
        mock_user_db.add_result(fetchone_result=None, rowcount=1)
        mock_user_db.add_result(fetchone_result={"id": "1", "permissions": '{"can_manage": true}'})
        result = await update_user_permissions("1", {"can_manage": True})
        assert result["id"] == "1"

    async def test_not_found(self, mock_user_db):
        mock_user_db.add_result(fetchone_result=None, rowcount=0)
        mock_user_db.add_result(fetchone_result=None)
        result = await update_user_permissions("999", {})
        assert result is None


class TestReassignUser:
    async def test_reassigns(self, mock_user_db):
        mock_user_db.add_result(fetchone_result=None, rowcount=1)
        result = await reassign_user("10", {"id": "10", "name": "SD", "role": "sub_distributor"}, "2", {"id": "2", "name": "New Parent"}, {"id": "1"})
        assert result["data"]["user_id"] == "10"
        assert result["data"]["new_parent_id"] == "2"


class TestGetChildrenUsers:
    async def test_returns_children(self, mock_user_db):
        mock_user_db.add_result(fetchall_result=[
            {"id": 20, "email": "c@t.com", "name": "Child", "role": "cluster", "parent_id": "10"},
        ])
        result = await get_children_users("10")
        assert len(result) == 1
        assert "password_hash" not in result[0]

    async def test_empty(self, mock_user_db):
        mock_user_db.add_result(fetchall_result=[])
        result = await get_children_users("10")
        assert result == []
