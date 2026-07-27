from unittest.mock import AsyncMock, patch, MagicMock
from contextlib import asynccontextmanager
import io
import pytest
from tests.conftest import MockDB


class TestListDevices:
    URL = "/api/devices"

    def test_success_returns_200(self, client, mock_device_services):
        import app.routes.devices as mod

        mod.device_service.get_devices = AsyncMock(
            return_value={
                "data": [{"id": "1", "serial_number": "SN001", "device_type": "ONT"}],
                "pagination": {"page": 1, "page_size": 20, "total": 1, "total_pages": 1},
            }
        )

        resp = client.get(self.URL)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Devices retrieved successfully"
        assert "data" in body
        assert "pagination" in body

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.get(self.URL)
        assert resp.status_code == 401

    def test_internal_error_returns_500(self, client, mock_device_services):
        import app.routes.devices as mod

        mod.device_service.get_devices = AsyncMock(side_effect=RuntimeError("error"))
        resp = client.get(self.URL)
        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()


class TestGetDevice:
    URL = "/api/devices/1"

    def _fake_device(self):
        return {
            "id": "1",
            "device_id": "ONT-2026-ABC123",
            "serial_number": "SN001",
            "device_type": "ONT",
            "status": "available",
            "model": "Model X",
            "manufacturer": "Vendor A",
        }

    def test_success_returns_200(self, client, mock_device_services):
        import app.routes.devices as mod

        mod.device_service.get_device_by_id = AsyncMock(return_value=self._fake_device())

        resp = client.get(self.URL)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Device retrieved successfully"
        assert body["data"]["id"] == "1"

    def test_not_found_returns_404(self, client, mock_device_services):
        import app.routes.devices as mod

        mod.device_service.get_device_by_id = AsyncMock(return_value=None)

        resp = client.get(self.URL)
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Device not found"

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.get(self.URL)
        assert resp.status_code == 401

    def test_internal_error_returns_500(self, client, mock_device_services):
        import app.routes.devices as mod

        mod.device_service.get_device_by_id = AsyncMock(side_effect=RuntimeError("error"))

        resp = client.get(self.URL)
        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()


class TestCreateDevice:
    URL = "/api/devices"

    def _payload(self):
        return {
            "device_type": "ONT",
            "serial_number": "SN001",
            "model": "Model X",
            "manufacturer": "Vendor A",
        }

    def _fake_device(self):
        return {
            "id": "1",
            "device_id": "ONT-2026-ABC123",
            **self._payload(),
            "status": "available",
        }

    def test_success_returns_201(self, client, mock_device_services):
        import app.routes.devices as mod

        mod.device_service.create_device = AsyncMock(return_value=self._fake_device())

        resp = client.post(self.URL, json=self._payload())
        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Device registered successfully"
        assert body["data"]["id"] == "1"

    def test_forbidden_non_management_returns_403(self, client, mock_device_services, set_role):
        set_role("operator")
        resp = client.post(self.URL, json=self._payload())
        assert resp.status_code == 403

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.post(self.URL, json=self._payload())
        assert resp.status_code == 401

    def test_internal_error_returns_500(self, client, mock_device_services):
        import app.routes.devices as mod

        mod.device_service.create_device = AsyncMock(side_effect=RuntimeError("error"))

        resp = client.post(self.URL, json=self._payload())
        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()


class TestUpdateDevice:
    URL = "/api/devices/1"

    def _payload(self):
        return {"model": "Model Y"}

    def _fake_device(self):
        return {
            "id": "1",
            "device_id": "ONT-2026-ABC123",
            "serial_number": "SN001",
            "device_type": "ONT",
            "model": "Model Y",
            "manufacturer": "Vendor A",
            "status": "available",
        }

    def test_success_returns_200(self, client, mock_device_services):
        import app.routes.devices as mod

        mod.device_service.get_device_by_id = AsyncMock(return_value=self._fake_device())
        mod.device_service.update_device = AsyncMock(return_value=self._fake_device())

        resp = client.put(self.URL, json=self._payload())
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Device updated successfully"
        assert body["data"]["id"] == "1"

    def test_not_found_returns_404(self, client, mock_device_services):
        import app.routes.devices as mod

        mod.device_service.get_device_by_id = AsyncMock(return_value=None)
        mod.device_service.update_device = AsyncMock(return_value=None)

        resp = client.put(self.URL, json=self._payload())
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Device not found"

    def test_forbidden_returns_403(self, client, set_role):
        set_role("operator")
        resp = client.put(self.URL, json=self._payload())
        assert resp.status_code == 403

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.put(self.URL, json=self._payload())
        assert resp.status_code == 401

    def test_internal_error_returns_500(self, client, mock_device_services):
        import app.routes.devices as mod

        mod.device_service.get_device_by_id = AsyncMock(return_value=self._fake_device())
        mod.device_service.update_device = AsyncMock(side_effect=RuntimeError("error"))

        resp = client.put(self.URL, json=self._payload())
        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()


class TestDeleteDevice:
    URL = "/api/devices/1"

    def test_success_returns_200(self, client, mock_device_services):
        import app.routes.devices as mod

        mod.device_service.get_device_by_id = AsyncMock(return_value={"id": "1"})
        mod.device_service.delete_device = AsyncMock(return_value=True)

        resp = client.delete(self.URL)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Device deleted successfully"

    def test_not_found_returns_404(self, client, mock_device_services):
        import app.routes.devices as mod

        mod.device_service.get_device_by_id = AsyncMock(return_value={"id": "1"})
        mod.device_service.delete_device = AsyncMock(return_value=False)

        resp = client.delete(self.URL)
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Device not found"

    def test_forbidden_returns_403(self, client, set_role):
        set_role("operator")
        resp = client.delete(self.URL)
        assert resp.status_code == 403

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.delete(self.URL)
        assert resp.status_code == 401

    def test_internal_error_returns_500(self, client, mock_device_services):
        import app.routes.devices as mod

        mod.device_service.get_device_by_id = AsyncMock(return_value={"id": "1"})
        mod.device_service.delete_device = AsyncMock(side_effect=RuntimeError("error"))

        resp = client.delete(self.URL)
        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()


class TestGetDeviceHistory:
    URL = "/api/devices/1/history"

    def test_success_returns_200(self, client, mock_device_services):
        import app.routes.devices as mod

        mod.device_service.get_device_by_id = AsyncMock(return_value={"id": "1"})
        mod.device_service.get_device_history = AsyncMock(
            return_value=[{"action": "registered", "timestamp": "2026-01-01T00:00:00"}]
        )

        resp = client.get(self.URL)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Device history retrieved successfully"
        assert len(body["data"]) == 1

    def test_not_found_returns_404(self, client, mock_device_services):
        import app.routes.devices as mod

        mod.device_service.get_device_by_id = AsyncMock(return_value=None)

        resp = client.get(self.URL)
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Device not found"

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.get(self.URL)
        assert resp.status_code == 401

    def test_internal_error_returns_500(self, client, mock_device_services):
        import app.routes.devices as mod

        mod.device_service.get_device_by_id = AsyncMock(return_value={"id": "1"})
        mod.device_service.get_device_history = AsyncMock(side_effect=RuntimeError("error"))

        resp = client.get(self.URL)
        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()


class TestTrackDevice:
    URL = "/api/devices/track/SN001"

    def test_success_returns_200(self, client, mock_device_services):
        import app.routes.devices as mod

        mod.device_service.track_device_by_serial = AsyncMock(
            return_value={
                "id": "1",
                "serial_number": "SN001",
                "device_type": "ONT",
                "status": "available",
                "history": [],
            }
        )

        resp = client.get(self.URL)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Device tracked successfully"
        assert body["data"]["serial_number"] == "SN001"

    def test_not_found_returns_404(self, client, mock_device_services):
        import app.routes.devices as mod

        mod.device_service.track_device_by_serial = AsyncMock(return_value=None)

        resp = client.get(self.URL)
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Device not found"

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.get(self.URL)
        assert resp.status_code == 401

    def test_internal_error_returns_500(self, client, mock_device_services):
        import app.routes.devices as mod

        mod.device_service.track_device_by_serial = AsyncMock(
            side_effect=RuntimeError("error")
        )

        resp = client.get(self.URL)
        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()


class TestForReplacement:
    URL = "/api/devices/for-replacement"

    def test_success_returns_200(self, client, mock_device_services):
        import app.routes.devices as mod

        mod.device_service.get_devices_for_replacement = AsyncMock(
            return_value=[{"id": "2", "serial_number": "SN002", "status": "available"}]
        )

        resp = client.get(self.URL)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Replacement-eligible devices retrieved successfully"
        assert len(body["data"]) == 1

    def test_forbidden_non_management_returns_403(self, client, set_role):
        set_role("operator")
        resp = client.get(self.URL)
        assert resp.status_code == 403
        assert "Only management" in resp.json()["detail"]

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.get(self.URL)
        assert resp.status_code == 401

    def test_internal_error_returns_500(self, client, mock_device_services):
        import app.routes.devices as mod

        mod.device_service.get_devices_for_replacement = AsyncMock(
            side_effect=RuntimeError("error")
        )

        resp = client.get(self.URL)
        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()


class TestAvailable:
    URL = "/api/devices/available"

    def test_success_management_returns_200(self, client, mock_device_services):
        import app.routes.devices as mod

        mod.device_service.get_available_devices = AsyncMock(
            return_value=[{"id": "1", "serial_number": "SN001", "status": "available"}]
        )

        resp = client.get(self.URL)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Available devices retrieved successfully"
        assert len(body["data"]) == 1

    def test_success_sub_role_returns_200(self, client, mock_device_services, set_role):
        import app.routes.devices as mod

        set_role("cluster")
        mod.device_service.get_held_devices = AsyncMock(
            return_value=[{"id": "1", "serial_number": "SN001", "status": "in_use"}]
        )

        resp = client.get(self.URL)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert len(body["data"]) == 1

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.get(self.URL)
        assert resp.status_code == 401

    def test_internal_error_returns_500(self, client, mock_device_services):
        import app.routes.devices as mod

        mod.device_service.get_available_devices = AsyncMock(
            side_effect=RuntimeError("error")
        )

        resp = client.get(self.URL)
        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()


class TestMyOverview:
    URL = "/api/devices/my-overview"

    def test_success_management_returns_200(self, client, mock_device_services):
        import app.routes.devices as mod

        mod.device_service.get_devices = AsyncMock(
            return_value={
                "data": [{"id": "1", "serial_number": "SN001"}],
                "pagination": {"page": 1, "page_size": 20, "total": 1, "total_pages": 1},
            }
        )
        mod.device_service.get_device_stats = AsyncMock(return_value={"total": 100})
        mod.device_service.get_management_insights = AsyncMock(return_value={})

        resp = client.get(self.URL)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "data" in body
        assert "held_by_me" in body["data"]
        assert "stats" in body["data"]
        assert "insights" in body["data"]
        assert "meta" in body["data"]

    def test_success_non_management_returns_200(self, client, mock_device_services, set_role):
        import app.routes.devices as mod

        set_role("operator")
        mod.device_service.get_user_device_overview = AsyncMock(
            return_value={
                "held_by_me": [{"id": "1", "serial_number": "SN001"}],
                "under_subordinates": [],
                "all_under_me": [{"id": "1", "serial_number": "SN001"}],
                "stats": {"total_in_chain": 1},
            }
        )

        resp = client.get(self.URL)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "data" in body
        assert "held_by_me" in body["data"]
        assert "meta" in body["data"]

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.get(self.URL)
        assert resp.status_code == 401

    def test_internal_error_returns_500(self, client, mock_device_services):
        import app.routes.devices as mod

        mod.device_service.get_devices = AsyncMock(side_effect=RuntimeError("error"))

        resp = client.get(self.URL)
        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()


class TestUpdateDeviceStatus:
    URL = "/api/devices/1/status"

    def test_success_returns_200(self, client, mock_device_services):
        import app.routes.devices as mod

        mod.device_service.get_device_by_id = AsyncMock(
            return_value={"id": "1", "status": "available"}
        )
        mod.device_service.update_device_status = AsyncMock(
            return_value={"id": "1", "status": "in_use"}
        )

        resp = client.patch(self.URL, json={"status": "in_use", "notes": "Assigned"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Device status updated successfully"
        assert body["data"]["status"] == "in_use"

    def test_not_found_returns_404(self, client, mock_device_services):
        import app.routes.devices as mod

        mod.device_service.get_device_by_id = AsyncMock(return_value={"id": "1"})
        mod.device_service.update_device_status = AsyncMock(return_value=None)

        resp = client.patch(self.URL, json={"status": "in_use"})
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Device not found"

    def test_missing_status_returns_400(self, client, mock_device_services):
        resp = client.patch(self.URL, json={})
        assert resp.status_code == 400
        assert "Status is required" in resp.json()["detail"]

    def test_forbidden_md_director_returns_403(self, client, set_role):
        set_role("md_director")
        resp = client.patch(self.URL, json={"status": "in_use"})
        assert resp.status_code == 403
        assert "read-only access" in resp.json()["detail"]

    def test_forbidden_sub_distribution_manager_returns_403(self, client, set_role):
        set_role("sub_distribution_manager")
        resp = client.patch(self.URL, json={"status": "in_use"})
        assert resp.status_code == 403
        assert "read-only access" in resp.json()["detail"]

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.patch(self.URL, json={"status": "in_use"})
        assert resp.status_code == 401

    def test_internal_error_returns_500(self, client, mock_device_services):
        import app.routes.devices as mod

        mod.device_service.get_device_by_id = AsyncMock(
            return_value={"id": "1", "status": "available"}
        )
        mod.device_service.update_device_status = AsyncMock(
            side_effect=RuntimeError("error")
        )

        resp = client.patch(self.URL, json={"status": "in_use"})
        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()


def _fake_db_context(mock_db):
    @asynccontextmanager
    async def _get_db():
        yield mock_db
    return _get_db


class TestBulkUploadDevices:
    URL = "/api/devices/bulk-upload"
    SB_CSV = b"vendor,device_type,model,nuid,box_type\nHuawei,SB,HG8245H,NUID-00123,HD\nZTE,stb,B866S,NUID-00456,OTT\n"

    @staticmethod
    def _patch_db(monkeypatch, mock_db):
        mock_db.add_result(fetchall_result=[])  # _fetch_existing_values → no conflicts
        mock_db.add_result(fetchall_result=[])  # second batch if any
        mock_db.add_result(fetchall_result=[   # SELECT after executemany → found ids
            {"id": "1", "device_id": "SB-2026-NUID-00123"},
            {"id": "2", "device_id": "SB-2026-NUID-00456"},
        ])

        with patch("app.routes.devices.get_db", _fake_db_context(mock_db)):
            with patch("app.routes.devices._fetch_existing_values", AsyncMock(return_value=set())):
                with patch("app.routes.devices._build_bulk_device_id") as mock_build_id:
                    mock_build_id.side_effect = [
                        "SB-2026-NUID-00123",
                        "SB-2026-NUID-00456",
                    ]
                    yield

    def test_sb_csv_success_returns_201(self, client, mock_device_services):
        mock_db = MockDB()
        for _ in self._patch_db(None, mock_db):
            resp = client.post(
                self.URL,
                files={"file": ("sb_devices.csv", io.BytesIO(self.SB_CSV), "text/csv")},
            )

        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["created_count"] == 2
        assert body["data"]["error_count"] == 0
        assert body["data"]["skipped_count"] == 0

    def test_sb_csv_missing_nuid_returns_errors(self, client, mock_device_services):
        csv = b"vendor,device_type,model,nuid,box_type\nHuawei,SB,HG8245H,,HD\n"
        resp = client.post(
            self.URL,
            files={"file": ("bad.csv", io.BytesIO(csv), "text/csv")},
        )
        body = resp.json()
        assert body["data"]["created_count"] == 0
        assert body["data"]["error_count"] >= 1
        assert any("nuid" in e["error"].lower() for e in body["data"]["errors"])

    def test_sb_csv_invalid_box_type_returns_errors(self, client, mock_device_services):
        csv = b"vendor,device_type,model,nuid,box_type\nHuawei,SB,HG8245H,NUID-00123,INVALID\n"
        resp = client.post(
            self.URL,
            files={"file": ("bad.csv", io.BytesIO(csv), "text/csv")},
        )
        body = resp.json()
        assert body["data"]["created_count"] == 0
        assert body["data"]["error_count"] >= 1
        assert any("box_type" in e["error"].lower() for e in body["data"]["errors"])

    def test_sb_csv_missing_columns_returns_400(self, client, mock_device_services):
        csv = b"vendor,model,nuid\nHuawei,HG8245H,NUID-00123\n"  # no device_type, box_type
        resp = client.post(
            self.URL,
            files={"file": ("bad.csv", io.BytesIO(csv), "text/csv")},
        )
        assert resp.status_code == 400

    def test_forbidden_non_management_returns_403(self, client, mock_device_services, set_role):
        set_role("operator")
        csv = b"vendor,device_type,model,nuid,box_type\nHuawei,SB,HG8245H,NUID-00123,HD\n"
        resp = client.post(
            self.URL,
            files={"file": ("sb.csv", io.BytesIO(csv), "text/csv")},
        )
        assert resp.status_code == 403

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user
        test_app.dependency_overrides.pop(get_current_user, None)
        csv = b"vendor,device_type,model,nuid,box_type\nHuawei,SB,HG8245H,NUID-00123,HD\n"
        resp = client.post(
            self.URL,
            files={"file": ("sb.csv", io.BytesIO(csv), "text/csv")},
        )
        assert resp.status_code == 401
