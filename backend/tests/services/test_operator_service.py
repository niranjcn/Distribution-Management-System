from unittest.mock import patch
from contextlib import asynccontextmanager
import pytest

from app.services.operator_service import (
    get_operators,
    get_operator_by_id,
    create_operator,
    update_operator,
    delete_operator,
    get_operator_devices,
    update_operator_device_count,
    get_operator_stats,
)
from app.models.operator import OperatorCreate, OperatorUpdate, ConnectionType


@pytest.fixture
def mock_op_db(mock_db):
    @asynccontextmanager
    async def _fake():
        yield mock_db
    patcher = patch("app.services.operator_service.get_db", _fake)
    patcher.start()
    yield mock_db
    patcher.stop()


@pytest.fixture
def creator():
    return {"_id": "1", "name": "Admin", "role": "super_admin"}


class TestGetOperators:
    async def test_returns_paginated_data(self, mock_op_db):
        mock_op_db.add_result(fetchone_result=(2,))
        mock_op_db.add_result(fetchall_result=[
            {"id": 1, "name": "Op1", "status": "active"},
            {"id": 2, "name": "Op2", "status": "active"},
        ])
        result = await get_operators()
        assert result["pagination"]["total"] == 2
        assert len(result["data"]) == 2

    async def test_filters_by_assigned_to(self, mock_op_db):
        mock_op_db.add_result(fetchone_result=(1,))
        mock_op_db.add_result(fetchall_result=[{"id": 1, "name": "Op1", "status": "active"}])
        result = await get_operators(assigned_to="1")
        assert "assigned_to" in mock_op_db.executed_queries[0]

    async def test_filters_by_status(self, mock_op_db):
        mock_op_db.add_result(fetchone_result=(1,))
        mock_op_db.add_result(fetchall_result=[{"id": 1, "name": "Op1", "status": "inactive"}])
        result = await get_operators(status="inactive")
        assert result["data"][0]["status"] == "inactive"

    async def test_empty(self, mock_op_db):
        mock_op_db.add_result(fetchone_result=(0,))
        result = await get_operators()
        assert result["data"] == []


class TestGetOperatorById:
    async def test_returns_operator(self, mock_op_db):
        mock_op_db.add_result(fetchone_result={"id": 1, "name": "Op1", "status": "active"})
        result = await get_operator_by_id("1")
        assert result["name"] == "Op1"

    async def test_returns_none_when_not_found(self, mock_op_db):
        mock_op_db.add_result(fetchone_result=None)
        result = await get_operator_by_id("999")
        assert result is None


class TestCreateOperator:
    async def test_creates_and_returns(self, mock_op_db, creator):
        mock_op_db.add_result(fetchone_result=None, rowcount=1, lastrowid=1)
        mock_op_db.add_result(fetchone_result={"id": 1, "name": "New Op", "status": "active"})
        data = OperatorCreate(name="New Op", phone="123", email="op@test.com")
        result = await create_operator(data, creator)
        assert result["name"] == "New Op"

    async def test_with_connection_type(self, mock_op_db, creator):
        mock_op_db.add_result(fetchone_result=None, rowcount=1, lastrowid=2)
        mock_op_db.add_result(fetchone_result={"id": 2, "name": "Fiber Op", "connection_type": "fiber", "status": "active"})
        data = OperatorCreate(name="Fiber Op", phone="456", email="fiber@test.com", connection_type=ConnectionType.FIBER)
        result = await create_operator(data, creator)
        assert result["connection_type"] == "fiber"


class TestUpdateOperator:
    async def test_updates_and_returns(self, mock_op_db):
        mock_op_db.add_result(fetchone_result=None, rowcount=1)
        mock_op_db.add_result(fetchone_result={"id": 1, "name": "Updated", "status": "active"})
        data = OperatorUpdate(name="Updated")
        result = await update_operator("1", data)
        assert result["name"] == "Updated"

    async def test_no_changes_returns_existing(self, mock_op_db):
        mock_op_db.add_result(fetchone_result={"id": 1, "name": "Same"})
        data = OperatorUpdate()
        result = await update_operator("1", data)
        assert result["name"] == "Same"

    async def test_not_found_returns_none(self, mock_op_db):
        mock_op_db.add_result(fetchone_result=None, rowcount=0)
        data = OperatorUpdate(name="Noop")
        result = await update_operator("999", data)
        assert result is None


class TestDeleteOperator:
    async def test_returns_true(self, mock_op_db):
        mock_op_db.add_result(fetchone_result=None, rowcount=1)
        result = await delete_operator("1")
        assert result is True

    async def test_returns_false_when_not_found(self, mock_op_db):
        mock_op_db.add_result(fetchone_result=None, rowcount=0)
        result = await delete_operator("999")
        assert result is False


class TestGetOperatorDevices:
    async def test_returns_devices(self, mock_op_db):
        mock_op_db.add_result(fetchall_result=[
            {"id": 1, "device_id": "DEV001", "device_type": "ONT"},
            {"id": 2, "device_id": "DEV002", "device_type": "Router"},
        ])
        result = await get_operator_devices("1")
        assert len(result) == 2

    async def test_empty(self, mock_op_db):
        mock_op_db.add_result(fetchall_result=[])
        result = await get_operator_devices("1")
        assert result == []


class TestUpdateOperatorDeviceCount:
    async def test_updates_count(self, mock_op_db):
        mock_op_db.add_result(fetchone_result=(5,))
        mock_op_db.add_result(fetchone_result=None, rowcount=1)
        await update_operator_device_count("1")
        assert "UPDATE operators SET device_count = ?" in mock_op_db.executed_queries[1]

    async def test_zero_devices(self, mock_op_db):
        mock_op_db.add_result(fetchone_result=(0,))
        mock_op_db.add_result(fetchone_result=None, rowcount=1)
        await update_operator_device_count("1")
        assert "device_count = ?" in mock_op_db.executed_queries[1]


class TestGetOperatorStats:
    async def test_returns_stats(self, mock_op_db):
        mock_op_db.add_result(fetchone_result=(10,))
        mock_op_db.add_result(fetchone_result=(7,))
        mock_op_db.add_result(fetchone_result=(3,))
        result = await get_operator_stats()
        assert result == {"total": 10, "active": 7, "inactive": 3}

    async def test_zero_counts(self, mock_op_db):
        mock_op_db.add_result(fetchone_result=(0,))
        mock_op_db.add_result(fetchone_result=(0,))
        mock_op_db.add_result(fetchone_result=(0,))
        result = await get_operator_stats()
        assert result == {"total": 0, "active": 0, "inactive": 0}

    async def test_scoped_by_assigned_to(self, mock_op_db):
        mock_op_db.add_result(fetchone_result=(5,))
        mock_op_db.add_result(fetchone_result=(3,))
        mock_op_db.add_result(fetchone_result=(2,))
        result = await get_operator_stats(assigned_to="1")
        assert "assigned_to = ?" in mock_op_db.executed_queries[0]
