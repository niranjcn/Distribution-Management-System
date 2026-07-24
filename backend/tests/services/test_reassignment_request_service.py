from unittest.mock import patch, AsyncMock
from contextlib import asynccontextmanager
import pytest

from app.services.reassignment_request_service import (
    _count_total_children,
    _get_direct_children,
    create_reassignment_request,
    get_reassignment_requests,
    get_reassignment_request,
    reassign_users,
    reject_request,
)


@pytest.fixture
def mock_reassign_db(mock_db):
    @asynccontextmanager
    async def _fake():
        yield mock_db
    patcher = patch("app.services.reassignment_request_service.get_db", _fake)
    patcher.start()
    yield mock_db
    patcher.stop()


@pytest.fixture
def sample_children():
    return [
        {"id": "10", "name": "SD1", "email": "sd1@t.com", "role": "sub_distributor", "parent_id": "1"},
        {"id": "20", "name": "CL1", "email": "cl1@t.com", "role": "cluster", "parent_id": "1",
         "children": [{"id": "30", "name": "OP1", "email": "op1@t.com", "role": "operator", "parent_id": "20"}]},
    ]


class TestCountTotalChildren:
    def test_empty(self):
        assert _count_total_children([]) == 0

    def test_flat(self):
        assert _count_total_children([{"id": "1"}, {"id": "2"}]) == 2

    def test_with_nested(self):
        children = [{"id": "1", "children": [{"id": "2"}, {"id": "3"}]}]
        assert _count_total_children(children) == 3  # 1 parent + 2 children


class TestGetDirectChildren:
    def test_empty(self):
        assert _get_direct_children([]) == []

    def test_extracts_top_level(self):
        children = [
            {"id": "10", "name": "SD1", "email": "sd@t.com", "role": "sub_distributor", "parent_id": "1",
             "children": [{"id": "20"}]},
        ]
        result = _get_direct_children(children)
        assert len(result) == 1
        assert result[0]["id"] == "10"
        assert "children" not in result[0]


class TestCreateReassignmentRequest:
    async def test_creates_request(self, mock_reassign_db):
        mock_reassign_db.add_result(fetchone_result=(0,))
        mock_reassign_db.add_result(fetchone_result=None, rowcount=1, lastrowid=1)
        mock_reassign_db.add_result(fetchone_result={"id": 1, "request_id": "REASSIGN-2026-0001", "status": "pending"})

        result = await create_reassignment_request(
            {"id": "5", "name": "Del User", "role": "sub_distributor"},
            [{"id": "10", "name": "Child", "email": "c@t.com", "role": "operator"}],
            "Admin"
        )
        assert result["request_id"] == "REASSIGN-2026-0001"

    async def test_increments_id(self, mock_reassign_db):
        mock_reassign_db.add_result(fetchone_result=(3,))
        mock_reassign_db.add_result(fetchone_result=None, rowcount=1, lastrowid=2)
        mock_reassign_db.add_result(fetchone_result={"id": 2, "request_id": "REASSIGN-2026-0004", "status": "pending"})

        result = await create_reassignment_request(
            {"id": "5", "name": "Del User", "role": "sub_distributor"},
            [],
            "Admin"
        )
        assert result["request_id"] == "REASSIGN-2026-0004"


class TestGetReassignmentRequests:
    async def test_returns_paginated(self, mock_reassign_db):
        mock_reassign_db.add_result(fetchone_result=(1,))
        mock_reassign_db.add_result(fetchall_result=[
            {"id": 1, "request_id": "REASSIGN-2026-0001", "status": "pending",
             "children_json": '[{"id":"10"}]'},
        ])
        result = await get_reassignment_requests()
        assert result["pagination"]["total"] == 1
        assert "children" in result["data"][0]
        assert "children_json" not in result["data"][0]

    async def test_empty(self, mock_reassign_db):
        mock_reassign_db.add_result(fetchone_result=(0,))
        result = await get_reassignment_requests()
        assert result["data"] == []

    async def test_filters_by_status(self, mock_reassign_db):
        mock_reassign_db.add_result(fetchone_result=(1,))
        mock_reassign_db.add_result(fetchall_result=[
            {"id": 1, "request_id": "R1", "status": "completed", "children_json": "[]"},
        ])
        result = await get_reassignment_requests(status="completed")
        assert result["data"][0]["status"] == "completed"


class TestGetReassignmentRequest:
    async def test_returns_request(self, mock_reassign_db):
        mock_reassign_db.add_result(fetchone_result={
            "id": 1, "request_id": "R1", "status": "pending",
            "children_json": '[{"id":"10","name":"SD1"}]',
        })
        result = await get_reassignment_request("1")
        assert result["children"][0]["id"] == "10"

    async def test_not_found_returns_none(self, mock_reassign_db):
        mock_reassign_db.add_result(fetchone_result=None)
        result = await get_reassignment_request("999")
        assert result is None

    async def test_empty_children(self, mock_reassign_db):
        mock_reassign_db.add_result(fetchone_result={
            "id": 2, "request_id": "R2", "status": "pending", "children_json": "[]",
        })
        result = await get_reassignment_request("2")
        assert result["children"] == []


class TestReassignUsers:
    async def test_reassigns_and_deletes(self, mock_reassign_db):
        mock_reassign_db.add_result(fetchone_result={
            "id": 1, "request_id": "REASSIGN-2026-0001", "status": "pending",
            "deleted_user_id": "5",
            "children_json": '[{"id":"10","name":"SD1","email":"sd@t.com","role":"sub_distributor","parent_id":"1"}]',
        })
        mock_reassign_db.add_result(fetchone_result=None, rowcount=1)
        mock_reassign_db.add_result(fetchone_result=None, rowcount=1)
        mock_reassign_db.add_result(fetchone_result={"name": "Del User", "email": "del@t.com", "role": "sub_distributor"})
        mock_reassign_db.add_result(fetchone_result=None, rowcount=1)

        success, msg = await reassign_users("1", 2, "New Parent", "sub_distributor")
        assert success is True
        assert "Reassigned" in msg

    async def test_not_found(self, mock_reassign_db):
        mock_reassign_db.add_result(fetchone_result=None)
        success, msg = await reassign_users("999", 2, "NP", "sub_distributor")
        assert success is False
        assert "not found" in msg

    async def test_already_completed(self, mock_reassign_db):
        mock_reassign_db.add_result(fetchone_result={
            "id": 1, "status": "completed", "deleted_user_id": "5",
            "children_json": '[]',
        })
        success, msg = await reassign_users("1", 2, "NP", "sub_distributor")
        assert success is False
        assert "already" in msg

    async def test_no_children(self, mock_reassign_db):
        mock_reassign_db.add_result(fetchone_result={
            "id": 1, "status": "pending", "deleted_user_id": "5",
            "children_json": '[]',
        })
        success, msg = await reassign_users("1", 2, "NP", "sub_distributor")
        assert success is False
        assert "No children" in msg


class TestRejectRequest:
    async def test_rejects_pending(self, mock_reassign_db):
        mock_reassign_db.add_result(fetchone_result={"id": 1, "status": "pending"})
        mock_reassign_db.add_result(fetchone_result=None, rowcount=1)
        success, msg = await reject_request("1")
        assert success is True
        assert "rejected" in msg

    async def test_not_found(self, mock_reassign_db):
        mock_reassign_db.add_result(fetchone_result=None)
        success, msg = await reject_request("999")
        assert success is False
        assert "not found" in msg

    async def test_already_completed(self, mock_reassign_db):
        mock_reassign_db.add_result(fetchone_result={"id": 1, "status": "completed"})
        success, msg = await reject_request("1")
        assert success is False
        assert "already" in msg
