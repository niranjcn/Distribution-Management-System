from unittest.mock import AsyncMock
import pytest


class TestExternalInventoryDashboard:
    URL = "/api/external-inventory/dashboard"

    def test_success(self, client, mock_inventory_services):
        import app.routes.external_inventory as mod
        mod.inventory_service.get_dashboard_summary = AsyncMock(
            return_value={"total_items": 100, "low_stock": 5}
        )
        resp = client.get(self.URL)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "External inventory dashboard retrieved successfully"
        assert body["data"]["total_items"] == 100

    def test_forbidden_for_operator(self, client, set_role):
        set_role("operator")
        resp = client.get(self.URL)
        assert resp.status_code == 403

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user
        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.get(self.URL)
        assert resp.status_code == 401

    def test_internal_error_returns_500(self, client, mock_inventory_services):
        import app.routes.external_inventory as mod
        mod.inventory_service.get_dashboard_summary = AsyncMock(
            side_effect=RuntimeError("error")
        )
        resp = client.get(self.URL)
        assert resp.status_code == 500


class TestGetExternalInventoryItems:
    URL = "/api/external-inventory/items"

    def _fake_paginated(self):
        return {
            "data": [{"inventory_id": "1", "name": "Item 1"}],
            "pagination": {"page": 1, "page_size": 20, "total": 1, "total_pages": 1},
        }

    def test_success(self, client, mock_inventory_services):
        import app.routes.external_inventory as mod
        mod.inventory_service.get_items = AsyncMock(return_value=self._fake_paginated())
        resp = client.get(self.URL)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "data" in body
        assert "pagination" in body

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user
        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.get(self.URL)
        assert resp.status_code == 401

    def test_internal_error_returns_500(self, client, mock_inventory_services):
        import app.routes.external_inventory as mod
        mod.inventory_service.get_items = AsyncMock(side_effect=RuntimeError("error"))
        resp = client.get(self.URL)
        assert resp.status_code == 500


class TestCreateExternalInventoryItem:
    URL = "/api/external-inventory/items"
    VALID_PAYLOAD = {
        "item_id": "ITEM001",
        "name": "New Item",
        "serial_number": "SN001",
        "device_type": "adapter",
        "mac_id": "MAC001",
    }

    def _fake_item(self, **overrides):
        return {
            "inventory_id": "INV001",
            "name": "New Item",
            "serial_number": "SN001",
            **overrides,
        }

    def test_success(self, client, mock_inventory_services):
        import app.routes.external_inventory as mod
        mod.inventory_service.create_item = AsyncMock(return_value=self._fake_item())
        resp = client.post(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "External inventory item created successfully"
        assert body["data"]["inventory_id"] == "INV001"

    def test_forbidden_for_operator(self, client, set_role):
        set_role("operator")
        resp = client.post(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 403

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user
        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.post(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 401

    def test_internal_error_returns_500(self, client, mock_inventory_services):
        import app.routes.external_inventory as mod
        mod.inventory_service.create_item = AsyncMock(side_effect=RuntimeError("error"))
        resp = client.post(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 500


class TestUpdateExternalInventoryItem:
    URL = "/api/external-inventory/items/INV001"
    VALID_PAYLOAD = {"name": "Updated Item"}

    def _fake_item(self, **overrides):
        return {"inventory_id": "INV001", "name": "Updated Item", **overrides}

    def test_success(self, client, mock_inventory_services):
        import app.routes.external_inventory as mod
        mod.inventory_service.get_item_by_inventory_id = AsyncMock(return_value=self._fake_item())
        mod.inventory_service.update_item = AsyncMock(return_value=self._fake_item())
        resp = client.put(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "External inventory item updated successfully"
        assert body["data"]["name"] == "Updated Item"

    def test_not_found_returns_404(self, client, mock_inventory_services):
        import app.routes.external_inventory as mod
        mod.inventory_service.get_item_by_inventory_id = AsyncMock(return_value=None)
        mod.inventory_service.update_item = AsyncMock(return_value=None)
        resp = client.put("/api/external-inventory/items/NONEXIST", json=self.VALID_PAYLOAD)
        assert resp.status_code == 404

    def test_forbidden_for_operator(self, client, set_role):
        set_role("operator")
        resp = client.put(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 403

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user
        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.put(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 401

    def test_internal_error_returns_500(self, client, mock_inventory_services):
        import app.routes.external_inventory as mod
        mod.inventory_service.get_item_by_inventory_id = AsyncMock(return_value=self._fake_item())
        mod.inventory_service.update_item = AsyncMock(side_effect=RuntimeError("error"))
        resp = client.put(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 500


class TestDeleteExternalInventoryItem:
    URL = "/api/external-inventory/items/INV001"

    def _fake_item(self, **overrides):
        return {"inventory_id": "INV001", "name": "Item", **overrides}

    def test_success(self, client, mock_inventory_services):
        import app.routes.external_inventory as mod
        mod.inventory_service.delete_item = AsyncMock(return_value=self._fake_item())
        resp = client.delete(self.URL)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "External inventory item deleted successfully"

    def test_not_found_returns_404(self, client, mock_inventory_services):
        import app.routes.external_inventory as mod
        mod.inventory_service.delete_item = AsyncMock(return_value=None)
        resp = client.delete("/api/external-inventory/items/NONEXIST")
        assert resp.status_code == 404

    def test_forbidden_for_operator(self, client, set_role):
        set_role("operator")
        resp = client.delete(self.URL)
        assert resp.status_code == 403

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user
        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.delete(self.URL)
        assert resp.status_code == 401

    def test_internal_error_returns_500(self, client, mock_inventory_services):
        import app.routes.external_inventory as mod
        mod.inventory_service.delete_item = AsyncMock(side_effect=RuntimeError("error"))
        resp = client.delete(self.URL)
        assert resp.status_code == 500


class TestUploadExternalInventoryItemImage:
    URL = "/api/external-inventory/items/INV001/image"

    def test_forbidden_for_operator(self, client, set_role):
        set_role("operator")
        resp = client.post(self.URL, files={"image": ("test.jpg", b"data", "image/jpeg")})
        assert resp.status_code == 403

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user
        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.post(self.URL, files={"image": ("test.jpg", b"data", "image/jpeg")})
        assert resp.status_code == 401

    def test_not_found_returns_404(self, client, set_role, mock_inventory_services):
        import app.routes.external_inventory as mod
        set_role("manager")
        mod.inventory_service.get_item_by_inventory_id = AsyncMock(return_value=None)
        resp = client.post(self.URL, files={"image": ("test.jpg", b"data", "image/jpeg")})
        assert resp.status_code == 404


class TestCreateExternalInventoryAdjustment:
    URL = "/api/external-inventory/adjustments"
    VALID_PAYLOAD = {
        "item_inventory_id": "INV001",
        "quantity_change": 5,
        "reason": "Stock correction",
    }

    def _fake_item(self, **overrides):
        return {"inventory_id": "INV001", "quantity_on_hand": 15, **overrides}

    def test_success(self, client, mock_inventory_services):
        import app.routes.external_inventory as mod
        mod.inventory_service.create_stock_adjustment = AsyncMock(return_value=self._fake_item())
        resp = client.post(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Stock adjustment applied successfully"

    def test_forbidden_for_operator(self, client, set_role):
        set_role("operator")
        resp = client.post(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 403

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user
        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.post(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 401

    def test_internal_error_returns_500(self, client, mock_inventory_services):
        import app.routes.external_inventory as mod
        mod.inventory_service.create_stock_adjustment = AsyncMock(
            side_effect=RuntimeError("error")
        )
        resp = client.post(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 500


class TestGetExternalInventoryPurchaseOrders:
    URL = "/api/external-inventory/purchase-orders"

    def _fake_paginated(self):
        return {
            "data": [{"po_id": "PO001", "supplier_name": "Supplier"}],
            "pagination": {"page": 1, "page_size": 20, "total": 1, "total_pages": 1},
        }

    def test_success(self, client, mock_inventory_services):
        import app.routes.external_inventory as mod
        mod.inventory_service.get_purchase_orders = AsyncMock(return_value=self._fake_paginated())
        resp = client.get(self.URL)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "data" in body
        assert "pagination" in body

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user
        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.get(self.URL)
        assert resp.status_code == 401

    def test_internal_error_returns_500(self, client, mock_inventory_services):
        import app.routes.external_inventory as mod
        mod.inventory_service.get_purchase_orders = AsyncMock(side_effect=RuntimeError("error"))
        resp = client.get(self.URL)
        assert resp.status_code == 500


class TestCreateExternalInventoryPurchaseOrder:
    URL = "/api/external-inventory/purchase-orders"
    VALID_PAYLOAD = {
        "supplier_name": "Supplier Inc",
        "lines": [{"item_inventory_id": "ITEM001", "quantity_ordered": 10}],
    }

    def _fake_po(self, **overrides):
        return {"po_id": "PO001", "supplier_name": "Supplier Inc", **overrides}

    def test_success(self, client, mock_inventory_services):
        import app.routes.external_inventory as mod
        mod.inventory_service.create_purchase_order = AsyncMock(return_value=self._fake_po())
        resp = client.post(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Purchase order created successfully"
        assert body["data"]["po_id"] == "PO001"

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user
        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.post(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 401

    def test_internal_error_returns_500(self, client, mock_inventory_services):
        import app.routes.external_inventory as mod
        mod.inventory_service.create_purchase_order = AsyncMock(
            side_effect=RuntimeError("error")
        )
        resp = client.post(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 500


class TestReceiveExternalInventoryPurchaseOrder:
    URL = "/api/external-inventory/purchase-orders/PO001/receive"
    VALID_PAYLOAD = {
        "lines": [{"item_inventory_id": "ITEM001", "quantity_received": 10}],
    }

    def _fake_po(self, **overrides):
        return {"po_id": "PO001", "status": "received", **overrides}

    def test_success(self, client, mock_inventory_services):
        import app.routes.external_inventory as mod
        mod.inventory_service.receive_purchase_order = AsyncMock(return_value=self._fake_po())
        resp = client.post(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Purchase order submitted successfully"
        assert body["data"]["po_id"] == "PO001"

    def test_forbidden_for_operator(self, client, set_role):
        set_role("operator")
        resp = client.post(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 403

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user
        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.post(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 401

    def test_internal_error_returns_500(self, client, mock_inventory_services):
        import app.routes.external_inventory as mod
        mod.inventory_service.receive_purchase_order = AsyncMock(
            side_effect=RuntimeError("error")
        )
        resp = client.post(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 500


class TestGetExternalInventoryReceipts:
    URL = "/api/external-inventory/receipts"

    def _fake_paginated(self):
        return {
            "data": [{"receipt_id": "RCP001"}],
            "pagination": {"page": 1, "page_size": 20, "total": 1, "total_pages": 1},
        }

    def test_success(self, client, mock_inventory_services):
        import app.routes.external_inventory as mod
        mod.inventory_service.get_receipts = AsyncMock(return_value=self._fake_paginated())
        resp = client.get(self.URL)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "data" in body
        assert "pagination" in body

    def test_forbidden_for_operator(self, client, set_role):
        set_role("operator")
        resp = client.get(self.URL)
        assert resp.status_code == 403

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user
        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.get(self.URL)
        assert resp.status_code == 401

    def test_internal_error_returns_500(self, client, mock_inventory_services):
        import app.routes.external_inventory as mod
        mod.inventory_service.get_receipts = AsyncMock(side_effect=RuntimeError("error"))
        resp = client.get(self.URL)
        assert resp.status_code == 500


class TestGetExternalInventoryMovements:
    URL = "/api/external-inventory/movements"

    def _fake_paginated(self):
        return {
            "data": [{"movement_id": "MOV001"}],
            "pagination": {"page": 1, "page_size": 20, "total": 1, "total_pages": 1},
        }

    def test_success(self, client, mock_inventory_services):
        import app.routes.external_inventory as mod
        mod.inventory_service.get_stock_movements = AsyncMock(return_value=self._fake_paginated())
        resp = client.get(self.URL)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "data" in body
        assert "pagination" in body

    def test_forbidden_for_operator(self, client, set_role):
        set_role("operator")
        resp = client.get(self.URL)
        assert resp.status_code == 403

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user
        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.get(self.URL)
        assert resp.status_code == 401

    def test_internal_error_returns_500(self, client, mock_inventory_services):
        import app.routes.external_inventory as mod
        mod.inventory_service.get_stock_movements = AsyncMock(
            side_effect=RuntimeError("error")
        )
        resp = client.get(self.URL)
        assert resp.status_code == 500
