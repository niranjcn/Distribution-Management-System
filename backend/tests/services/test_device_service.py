from unittest.mock import patch, AsyncMock
from contextlib import asynccontextmanager
import pytest

from app.services.device_service import (
    get_devices,
    get_device_by_id,
    get_device_by_serial,
    create_device,
    update_device,
    delete_device,
    update_device_status,
    update_device_holder,
    get_available_devices,
    get_held_devices,
    get_device_history,
    get_device_stats,
    get_management_insights,
)
from app.models.device import DeviceCreate, DeviceUpdate


@pytest.fixture
def mock_dev_db(mock_db):
    @asynccontextmanager
    async def _fake():
        yield mock_db
    patcher = patch("app.services.device_service.get_db", _fake)
    patcher.start()
    yield mock_db
    patcher.stop()


@pytest.fixture
def sample_device():
    return {
        "id": "1", "_id": "1",
        "device_id": "DEV-001",
        "device_type": "ONT",
        "model": "HG8245",
        "manufacturer": "Huawei",
        "serial_number": "SN001",
        "mac_address": "AA:BB:CC:DD:EE:01",
        "status": "available",
        "current_holder_id": None,
        "current_holder_name": None,
        "current_holder_type": None,
        "location": None,
    }


class TestGetDevices:
    async def test_returns_paginated(self, mock_dev_db):
        mock_dev_db.add_result(fetchone_result=(2,))
        mock_dev_db.add_result(fetchall_result=[
            {"id": 1, "device_id": "D1", "status": "available"},
            {"id": 2, "device_id": "D2", "status": "available"},
        ])
        result = await get_devices()
        assert result["pagination"]["total"] == 2
        assert len(result["data"]) == 2

    async def test_empty(self, mock_dev_db):
        mock_dev_db.add_result(fetchone_result=(0,))
        result = await get_devices()
        assert result["data"] == []

    async def test_filters_by_status(self, mock_dev_db):
        mock_dev_db.add_result(fetchone_result=(1,))
        mock_dev_db.add_result(fetchall_result=[{"id": 1, "device_id": "D1", "status": "defective"}])
        result = await get_devices(status="defective")
        assert result["data"][0]["status"] == "defective"


class TestGetDeviceById:
    async def test_returns_device(self, mock_dev_db, sample_device):
        mock_dev_db.add_result(fetchone_result=sample_device)
        result = await get_device_by_id("1")
        assert result["device_id"] == "DEV-001"

    async def test_not_found(self, mock_dev_db):
        mock_dev_db.add_result(fetchone_result=None)
        result = await get_device_by_id("999")
        assert result is None


class TestGetDeviceBySerial:
    async def test_finds_by_serial(self, mock_dev_db):
        mock_dev_db.add_result(fetchone_result={"id": 1, "device_id": "D1", "serial_number": "SN001"})
        result = await get_device_by_serial("SN001")
        assert result["serial_number"] == "SN001"

    async def test_not_found(self, mock_dev_db):
        mock_dev_db.add_result(fetchone_result=None)
        result = await get_device_by_serial("UNKNOWN")
        assert result is None


class TestCreateDevice:
    async def test_creates_device(self, mock_dev_db):
        mock_dev_db.add_result(fetchone_result=None)
        mock_dev_db.add_result(fetchone_result=None, rowcount=1, lastrowid=1)
        mock_dev_db.add_result(fetchone_result={"id": 1, "device_id": "DEV-001", "device_type": "ONT", "status": "available"})
        data = DeviceCreate(device_type="ONT", model="HG8245", manufacturer="Huawei", nuid="NUID001", serial_number="SN001")
        with (
            patch("app.services.device_service.generate_device_id", return_value="DEV-001"),
            patch("app.services.device_service._add_device_history", return_value=None),
        ):
            result = await create_device(data, "1", "Admin")
        assert result["device_id"] == "DEV-001"

    async def test_duplicate_nuid_raises(self, mock_dev_db):
        mock_dev_db.add_result(fetchone_result=(1,))
        data = DeviceCreate(device_type="Set-top box", model="M", manufacturer="MFR", nuid="EXISTING", box_type="HD")
        with pytest.raises(ValueError, match="already exists"):
            await create_device(data, "1", "Admin")


class TestUpdateDevice:
    async def test_updates_and_returns(self, mock_dev_db, sample_device):
        mock_dev_db.add_result(fetchone_result=sample_device)
        mock_dev_db.add_result(fetchone_result=None, rowcount=1)
        mock_dev_db.add_result(fetchone_result={"id": "1", "device_id": "DEV-001", "model": "Updated", "status": "available"})
        data = DeviceUpdate(model="Updated")
        result = await update_device("1", data)
        assert result["model"] == "Updated"

    async def test_not_found(self, mock_dev_db):
        mock_dev_db.add_result(fetchone_result=None)
        data = DeviceUpdate(model="Nope")
        result = await update_device("999", data)
        assert result is None


class TestDeleteDevice:
    async def test_deletes_device_and_history(self, mock_dev_db):
        mock_dev_db.add_result(fetchone_result=None, rowcount=1)
        mock_dev_db.add_result(fetchone_result=None, rowcount=1)
        result = await delete_device("1")
        assert result is True

    async def test_not_found(self, mock_dev_db):
        mock_dev_db.add_result(fetchone_result=None, rowcount=0)
        result = await delete_device("999")
        assert result is False


class TestUpdateDeviceStatus:
    async def test_updates_valid_status(self, mock_dev_db, sample_device):
        mock_dev_db.add_result(fetchone_result=sample_device)
        mock_dev_db.add_result(fetchone_result=None, rowcount=1)
        mock_dev_db.add_result(fetchone_result=sample_device)
        with patch("app.services.device_service._add_device_history", return_value=None):
            result = await update_device_status("1", "distributed", "1", "Admin")
        assert result["status"] == sample_device["status"]

    async def test_not_found(self, mock_dev_db):
        mock_dev_db.add_result(fetchone_result=None)
        result = await update_device_status("999", "available", "1", "Admin")
        assert result is None

    async def test_invalid_status_raises(self, mock_dev_db, sample_device):
        mock_dev_db.add_result(fetchone_result=sample_device)
        with pytest.raises(ValueError, match="Invalid device status"):
            await update_device_status("1", "bogus", "1", "Admin")


class TestUpdateDeviceHolder:
    async def test_updates_holder(self, mock_dev_db, sample_device):
        mock_dev_db.add_result(fetchone_result=sample_device)
        mock_dev_db.add_result(fetchone_result=None, rowcount=1)
        mock_dev_db.add_result(fetchone_result=sample_device)
        with patch("app.services.device_service._add_device_history", return_value=None):
            result = await update_device_holder("1", "10", "SD1", "sub_distributor", "Location A", "distributed", "1", "Admin")
        assert result["device_id"] == "DEV-001"

    async def test_not_found(self, mock_dev_db):
        mock_dev_db.add_result(fetchone_result=None)
        result = await update_device_holder("999", "10", "SD1", "sub_distributor", "Loc", "distributed", "1", "Admin")
        assert result is None


class TestGetAvailableDevices:
    async def test_returns_available(self, mock_dev_db):
        mock_dev_db.add_result(fetchall_result=[
            {"id": 1, "device_id": "D1", "status": "available"},
            {"id": 2, "device_id": "D2", "status": "available"},
        ])
        with patch("app.services.device_service._get_locked_distribution_device_ids", return_value=set()):
            result = await get_available_devices()
        assert len(result) == 2

    async def test_filters_locked(self, mock_dev_db):
        mock_dev_db.add_result(fetchall_result=[
            {"id": 1, "device_id": "D1", "status": "available"},
            {"id": 2, "device_id": "D2", "status": "available"},
        ])
        with patch("app.services.device_service._get_locked_distribution_device_ids", return_value={"1"}):
            result = await get_available_devices()
        assert len(result) == 1
        assert result[0]["device_id"] == "D2"


class TestGetHeldDevices:
    async def test_returns_devices_for_holder(self, mock_dev_db):
        mock_dev_db.add_result(fetchall_result=[
            {"id": 1, "device_id": "D1", "current_holder_id": "10"},
        ])
        with patch("app.services.device_service._get_locked_distribution_device_ids", return_value=set()):
            result = await get_held_devices("10")
        assert len(result) == 1

    async def test_empty(self, mock_dev_db):
        mock_dev_db.add_result(fetchall_result=[])
        with patch("app.services.device_service._get_locked_distribution_device_ids", return_value=set()):
            result = await get_held_devices("99")
        assert result == []


class TestGetDeviceHistory:
    async def test_returns_history(self, mock_dev_db):
        mock_dev_db.add_result(fetchall_result=[
            {"id": 1, "device_id": "1", "action": "created", "timestamp": "2025-01-01T00:00:00"},
            {"id": 2, "device_id": "1", "action": "distributed", "timestamp": "2025-06-01T00:00:00"},
        ])
        result = await get_device_history("1")
        assert len(result) == 2

    async def test_empty(self, mock_dev_db):
        mock_dev_db.add_result(fetchall_result=[])
        result = await get_device_history("999")
        assert result == []


class TestGetDeviceStats:
    async def test_returns_counts(self, mock_dev_db):
        mock_dev_db.add_result(fetchall_result=[
            ("available", 50),
            ("distributed", 30),
            ("in_use", 10),
            ("defective", 3),
            ("returned", 5),
            ("other", 2),
        ])
        result = await get_device_stats()
        assert result["total"] == 100
        assert result["available"] == 50
        assert result["distributed"] == 30

    async def test_with_date_filter(self, mock_dev_db):
        mock_dev_db.add_result(fetchall_result=[])
        result = await get_device_stats("2025-01-01", "2025-12-31")
        assert "created_at" in mock_dev_db.executed_queries[0]


class TestGetManagementInsights:
    async def test_returns_insights(self, mock_dev_db):
        mock_dev_db.add_result(fetchall_result=[
            {"device_type": "ONT", "COUNT(*)": 50},
            {"device_type": "Router", "COUNT(*)": 30},
        ])
        mock_dev_db.add_result(fetchall_result=[
            {"manufacturer": "Huawei", "device_type": "ONT", "COUNT(*)": 30},
            {"manufacturer": "ZTE", "device_type": "ONT", "COUNT(*)": 20},
        ])
        result = await get_management_insights()
        assert "by_type" in result
        assert "by_vendor" in result
