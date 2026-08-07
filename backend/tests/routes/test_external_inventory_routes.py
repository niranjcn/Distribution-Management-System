from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_item(**overrides):
    base = {
        "id": 1,
        "name": "Test Item",
        "identifier_type": "MAC ID",
        "identifier": "AA:BB:CC:DD:EE:FF",
        "device_type": "Router",
        "price": 100.0,
        "quantity": 10,
        "supplier_name": "Acme",
        "location": "Main Store",
        "status": "active",
        "notes": None,
        "warranty_start_date": "2026-01-15",
        "warranty_duration": 12,
        "created_by": 1,
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-01T00:00:00",
    }
    base.update(overrides)
    return base


def _fake_paginated(**overrides):
    base = {
        "data": [_fake_item()],
        "pagination": {
            "page": 1,
            "page_size": 20,
            "total": 1,
            "total_pages": 1,
            "has_next": False,
        },
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# GET /items
# ---------------------------------------------------------------------------

class TestGetExternalInventoryItems:
    URL = "/api/external-inventory/items"

    def test_success(self, client, mock_inventory_services):
        import app.routes.external_inventory as mod
        mod.inventory_service.get_items = AsyncMock(return_value=_fake_paginated())
        resp = client.get(self.URL)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"] == [_fake_item()]
        mod.inventory_service.get_items.assert_awaited_once()

    def test_non_management_passes_management_false(self, client, mock_inventory_services, set_role):
        set_role("operator")
        import app.routes.external_inventory as mod
        mod.inventory_service.get_items = AsyncMock(return_value=_fake_paginated())
        client.get(self.URL)
        mod.inventory_service.get_items.assert_awaited_once()
        kwargs = mod.inventory_service.get_items.await_args.kwargs
        assert kwargs["management"] is False

    def test_management_passes_management_true(self, client, mock_inventory_services, set_role):
        set_role("pdic_staff")
        import app.routes.external_inventory as mod
        mod.inventory_service.get_items = AsyncMock(return_value=_fake_paginated())
        client.get(self.URL)
        mod.inventory_service.get_items.assert_awaited_once()
        kwargs = mod.inventory_service.get_items.await_args.kwargs
        assert kwargs["management"] is True

    def test_internal_error_returns_500(self, client, mock_inventory_services):
        import app.routes.external_inventory as mod
        mod.inventory_service.get_items = AsyncMock(side_effect=RuntimeError("error"))
        resp = client.get(self.URL)
        assert resp.status_code == 500
        assert resp.json()["detail"] == "An internal error occurred. Please try again later."


# ---------------------------------------------------------------------------
# POST /items
# ---------------------------------------------------------------------------

class TestCreateExternalInventoryItem:
    URL = "/api/external-inventory/items"
    VALID_PAYLOAD = {
        "name": "New Item",
        "identifier_type": "MAC ID",
        "quantity": 5,
    }

    def test_success(self, client, mock_inventory_services):
        import app.routes.external_inventory as mod
        mod.inventory_service.create_item = AsyncMock(return_value=_fake_item())
        resp = client.post(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "External inventory item created successfully"
        mod.inventory_service.create_item.assert_awaited_once()

    def test_internal_error_returns_500(self, client, mock_inventory_services):
        import app.routes.external_inventory as mod
        mod.inventory_service.create_item = AsyncMock(side_effect=RuntimeError("error"))
        resp = client.post(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# PUT /items/{item_id}
# ---------------------------------------------------------------------------

class TestUpdateExternalInventoryItem:
    URL = "/api/external-inventory/items/1"
    VALID_PAYLOAD = {"quantity": 15, "price": 120.0}

    def test_success(self, client, mock_inventory_services):
        import app.routes.external_inventory as mod
        mod.inventory_service.get_item_by_id = AsyncMock(return_value=_fake_item())
        mod.inventory_service.update_item = AsyncMock(return_value=_fake_item(quantity=15))
        resp = client.put(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 200
        assert resp.json()["message"] == "External inventory item updated successfully"

    def test_not_found_returns_404(self, client, mock_inventory_services):
        import app.routes.external_inventory as mod
        mod.inventory_service.get_item_by_id = AsyncMock(return_value=None)
        mod.inventory_service.update_item = AsyncMock(return_value=None)
        resp = client.put("/api/external-inventory/items/999", json=self.VALID_PAYLOAD)
        assert resp.status_code == 404
        assert resp.json()["detail"] == "External inventory item not found"

    def test_internal_error_returns_500(self, client, mock_inventory_services):
        import app.routes.external_inventory as mod
        mod.inventory_service.get_item_by_id = AsyncMock(return_value=_fake_item())
        mod.inventory_service.update_item = AsyncMock(side_effect=RuntimeError("error"))
        resp = client.put(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# DELETE /items/{item_id}
# ---------------------------------------------------------------------------

class TestDeleteExternalInventoryItem:
    URL = "/api/external-inventory/items/1"

    def test_success(self, client, mock_inventory_services):
        import app.routes.external_inventory as mod
        mod.inventory_service.delete_item = AsyncMock(return_value=_fake_item())
        resp = client.delete(self.URL)
        assert resp.status_code == 200
        assert resp.json()["message"] == "External inventory item deleted successfully"

    def test_not_found_returns_404(self, client, mock_inventory_services):
        import app.routes.external_inventory as mod
        mod.inventory_service.delete_item = AsyncMock(return_value=None)
        resp = client.delete("/api/external-inventory/items/999")
        assert resp.status_code == 404

    def test_internal_error_returns_500(self, client, mock_inventory_services):
        import app.routes.external_inventory as mod
        mod.inventory_service.delete_item = AsyncMock(side_effect=RuntimeError("error"))
        resp = client.delete(self.URL)
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# POST /distributions
# ---------------------------------------------------------------------------

class TestDistributeExternalInventoryItem:
    URL = "/api/external-inventory/distributions"
    VALID_PAYLOAD = {"item_id": 1, "to_user_id": 2, "quantity": 2, "notes": "ok"}

    def test_success(self, client, mock_inventory_services):
        import app.routes.external_inventory as mod
        result = {
            "history_id": "EXT-001",
            "item_id": 1,
            "item_name": "Test Item",
            "quantity": 2,
            "recipient_id": 2,
            "recipient_name": "Jane",
            "previous_quantity": 10,
            "remaining_quantity": 8,
        }
        mod.inventory_service.distribute_item = AsyncMock(return_value=result)
        resp = client.post(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "External inventory item distributed successfully"
        assert body["data"]["remaining_quantity"] == 8

    def test_internal_error_returns_500(self, client, mock_inventory_services):
        import app.routes.external_inventory as mod
        mod.inventory_service.distribute_item = AsyncMock(side_effect=RuntimeError("error"))
        resp = client.post(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# POST /distributions/bulk
# ---------------------------------------------------------------------------

class TestBulkDistributeExternalInventoryItems:
    URL = "/api/external-inventory/distributions/bulk"
    VALID_PAYLOAD = {
        "items": [
            {"item_id": 1, "to_user_id": 2, "quantity": 1},
            {"item_id": 2, "recipient_email": "bob@test.com", "quantity": 3},
        ]
    }

    def test_success(self, client, mock_inventory_services):
        import app.routes.external_inventory as mod
        result = {
            "created_count": 2,
            "error_count": 0,
            "created": [{"item_id": 1}, {"item_id": 2}],
            "errors": [],
        }
        mod.inventory_service.bulk_distribute = AsyncMock(return_value=result)
        resp = client.post(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["created_count"] == 2

    def test_internal_error_returns_500(self, client, mock_inventory_services):
        import app.routes.external_inventory as mod
        mod.inventory_service.bulk_distribute = AsyncMock(side_effect=RuntimeError("error"))
        resp = client.post(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /distributions (history)
# ---------------------------------------------------------------------------

class TestGetExternalInventoryDistributions:
    URL = "/api/external-inventory/distributions"

    def test_success(self, client, mock_inventory_services):
        import app.routes.external_inventory as mod
        mod.inventory_service.get_distribution_history = AsyncMock(return_value=_fake_paginated())
        resp = client.get(self.URL)
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_internal_error_returns_500(self, client, mock_inventory_services):
        import app.routes.external_inventory as mod
        mod.inventory_service.get_distribution_history = AsyncMock(side_effect=RuntimeError("error"))
        resp = client.get(self.URL)
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# POST /distributions/bulk-upload
# ---------------------------------------------------------------------------

class TestBulkDistributeExternalInventoryFromFile:
    URL = "/api/external-inventory/distributions/bulk-upload"

    def _result(self, **overrides):
        base = {
            "total_rows": 2,
            "created_count": 2,
            "error_count": 0,
            "recipient_id": 2,
            "recipient_name": "Jane",
            "created": [{"item_name": "Item One"}, {"item_name": "Item Two"}],
            "errors": [],
        }
        base.update(overrides)
        return base

    def test_success_csv(self, client, mock_inventory_services):
        import app.routes.external_inventory as mod
        mod.inventory_service.bulk_distribute_from_file = AsyncMock(return_value=self._result())
        csv_bytes = b"identifier_type,identifier,quantity\r\nMAC ID,AA:BB:CC:00:00:01,2\r\nNU ID,NU-0001,3\r\n"
        resp = client.post(
            self.URL,
            data={"to_user_id": "2"},
            files={"file": ("items.csv", BytesIO(csv_bytes), "text/csv")},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["created_count"] == 2
        mod.inventory_service.bulk_distribute_from_file.assert_awaited_once()
        kwargs = mod.inventory_service.bulk_distribute_from_file.await_args.kwargs
        assert kwargs["to_user_id"] == "2"
        assert len(kwargs["identifier_rows"]) == 2
        assert kwargs["identifier_rows"][0]["identifier_type"] == "MAC ID"
        assert kwargs["identifier_rows"][0]["identifier"] == "AA:BB:CC:00:00:01"
        assert kwargs["identifier_rows"][0]["quantity"] == "2"
        assert kwargs["identifier_rows"][0]["notes"] is None

    def test_non_supported_extension_rejected(self, client, mock_inventory_services):
        resp = client.post(
            self.URL,
            data={"to_user_id": "2"},
            files={"file": ("items.txt", BytesIO(b"abc"), "text/plain")},
        )
        assert resp.status_code == 400
        assert "Only Excel" in resp.json()["detail"]

    def test_missing_required_columns_rejected(self, client, mock_inventory_services):
        csv_bytes = b"identifier_type,quantity\r\nMAC ID,2\r\n"
        resp = client.post(
            self.URL,
            data={"to_user_id": "2"},
            files={"file": ("items.csv", BytesIO(csv_bytes), "text/csv")},
        )
        assert resp.status_code == 400
        assert "Missing required columns" in resp.json()["detail"]

    def test_internal_error_returns_500(self, client, mock_inventory_services):
        import app.routes.external_inventory as mod
        mod.inventory_service.bulk_distribute_from_file = AsyncMock(side_effect=RuntimeError("error"))
        csv_bytes = b"identifier_type,identifier,quantity\r\nMAC ID,AA:BB:CC:00:00:01,2\r\n"
        resp = client.post(
            self.URL,
            data={"to_user_id": "2"},
            files={"file": ("items.csv", BytesIO(csv_bytes), "text/csv")},
        )
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# POST /items/bulk-upload
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_bulk_upload_db():
    """Replace the DB session used inside the bulk-upload handler."""
    import app.database_sqlalchemy as dbs

    session = AsyncMock()
    session.info = {}

    result = MagicMock()
    result.mappings.return_value.all.return_value = []
    result.mappings.return_value.first.return_value = None
    session.execute.return_value = result

    class _Ctx:
        def __init__(self, s):
            self._s = s

        async def __aenter__(self):
            return self._s

        async def __aexit__(self, *args):
            return False

    def _factory():
        return _Ctx(session)

    patchers = [
        patch("app.database_sqlalchemy.async_session_factory", new=_factory),
    ]
    for p in patchers:
        p.start()
    yield session
    for p in patchers:
        p.stop()


class TestBulkUploadExternalInventoryItems:
    URL = "/api/external-inventory/items/bulk-upload"

    def test_success(self, client, mock_inventory_services, mock_bulk_upload_db):
        csv_bytes = b"name,identifier_type,identifier,quantity\r\nItem One,MAC ID,AA:BB:CC,2\r\nItem Two,MAC ID,DD:EE:FF,3\r\n"
        resp = client.post(
            self.URL,
            files={"file": ("items.csv", BytesIO(csv_bytes), "text/csv")},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["created_count"] == 2

    def test_success_with_warranty_columns(self, client, mock_inventory_services, mock_bulk_upload_db):
        csv_bytes = (
            b"name,identifier_type,identifier,quantity,warranty_start_date,warranty_duration\r\n"
            b"Item One,MAC ID,AA:BB:CC,2,2026-01-15,12\r\n"
            b"Item Two,MAC ID,DD:EE:FF,3,2026-02-01,6\r\n"
        )
        resp = client.post(
            self.URL,
            files={"file": ("items.csv", BytesIO(csv_bytes), "text/csv")},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["created_count"] == 2
        assert body["data"]["error_count"] == 0

    def test_invalid_warranty_start_date_rejected(self, client, mock_inventory_services, mock_bulk_upload_db):
        csv_bytes = b"name,quantity,warranty_start_date,warranty_duration\r\nItem One,2,not-a-date,12\r\n"
        resp = client.post(
            self.URL,
            files={"file": ("items.csv", BytesIO(csv_bytes), "text/csv")},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["data"]["created_count"] == 0
        assert body["data"]["error_count"] == 1
        assert "warranty_start_date" in body["data"]["errors"][0]["error"]

    def test_invalid_warranty_duration_rejected(self, client, mock_inventory_services, mock_bulk_upload_db):
        csv_bytes = b"name,quantity,warranty_duration\r\nItem One,2,abc\r\n"
        resp = client.post(
            self.URL,
            files={"file": ("items.csv", BytesIO(csv_bytes), "text/csv")},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["data"]["created_count"] == 0
        assert body["data"]["error_count"] == 1
        assert "warranty_duration" in body["data"]["errors"][0]["error"]

    def test_duplicate_identifier_pair_rejected(self, client, mock_inventory_services, mock_bulk_upload_db):
        csv_bytes = (
            b"name,identifier_type,identifier,quantity\r\n"
            b"Item One,MAC ID,AA:BB:CC,2\r\n"
            b"Item Two,MAC ID,AA:BB:CC,3\r\n"
        )
        resp = client.post(
            self.URL,
            files={"file": ("items.csv", BytesIO(csv_bytes), "text/csv")},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["data"]["created_count"] == 1
        assert body["data"]["error_count"] == 1
        assert "Duplicate identifier_type and identifier" in body["data"]["errors"][0]["error"]

    def test_non_csv_rejected(self, client, mock_inventory_services):
        resp = client.post(
            self.URL,
            files={"file": ("items.txt", BytesIO(b"abc"), "text/plain")},
        )
        assert resp.status_code == 400
        assert "CSV" in resp.json()["detail"]

    def test_missing_required_column_rejected(self, client, mock_inventory_services):
        csv_bytes = b"identifier_type,quantity\r\nMAC ID,2\r\n"
        resp = client.post(
            self.URL,
            files={"file": ("items.csv", BytesIO(csv_bytes), "text/csv")},
        )
        assert resp.status_code == 400
        assert "Missing required columns" in resp.json()["detail"]

    def test_internal_error_returns_500(self, client, mock_inventory_services, mock_bulk_upload_db):
        csv_bytes = b"name,quantity\r\nItem One,2\r\n"
        with patch(
            "app.routes.external_inventory.chunked_executemany",
            AsyncMock(side_effect=RuntimeError("error")),
        ):
            resp = client.post(
                self.URL,
                files={"file": ("items.csv", BytesIO(csv_bytes), "text/csv")},
            )
        assert resp.status_code == 500