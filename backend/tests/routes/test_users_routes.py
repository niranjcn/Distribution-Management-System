from unittest.mock import AsyncMock, MagicMock
import pytest
import io


class TestListUsers:
    LIST_URL = "/api/users"

    def _fake_user(self, **overrides):
        return {
            "id": "1",
            "name": "Test User",
            "email": "user@test.com",
            "role": "operator",
            "status": "active",
            **overrides,
        }

    def _fake_paginated(self, users=None):
        if users is None:
            users = [self._fake_user()]
        return {
            "data": users,
            "pagination": {
                "page": 1,
                "page_size": 20,
                "total": len(users),
                "total_pages": 1,
                "has_next": False,
                "has_prev": False,
            },
        }

    # ---------- success ----------

    def test_list_users_success(self, client, mock_user_services):
        import app.routes.users as mod

        paginated = self._fake_paginated()
        mod.user_service.get_users = AsyncMock(return_value=paginated)

        resp = client.get(self.LIST_URL)

        assert resp.status_code == 200
        body = resp.json()
        assert list(body.keys()) == ["success", "message", "data", "pagination"]
        assert body["success"] is True
        assert len(body["data"]) == 1
        assert body["pagination"]["total"] == 1

    def test_list_users_empty(self, client, mock_user_services):
        import app.routes.users as mod

        paginated = self._fake_paginated(users=[])
        mod.user_service.get_users = AsyncMock(return_value=paginated)

        resp = client.get(self.LIST_URL)

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"] == []
        assert body["pagination"]["total"] == 0

    # ---------- filters ----------

    def test_list_users_passes_role_filter(self, client, mock_user_services):
        import app.routes.users as mod

        paginated = self._fake_paginated()
        mod.user_service.get_users = AsyncMock(return_value=paginated)

        client.get(self.LIST_URL, params={"role": "operator"})

        _, kwargs = mod.user_service.get_users.await_args
        assert kwargs.get("role") == "operator"

    def test_list_users_passes_search_filter(self, client, mock_user_services):
        import app.routes.users as mod

        paginated = self._fake_paginated()
        mod.user_service.get_users = AsyncMock(return_value=paginated)

        client.get(self.LIST_URL, params={"search": "john"})

        _, kwargs = mod.user_service.get_users.await_args
        assert kwargs.get("search") == "john"

    def test_list_users_passes_status_filter(self, client, mock_user_services):
        import app.routes.users as mod

        paginated = self._fake_paginated()
        mod.user_service.get_users = AsyncMock(return_value=paginated)

        client.get(self.LIST_URL, params={"status": "active"})

        _, kwargs = mod.user_service.get_users.await_args
        assert kwargs.get("status") == "active"

    # ---------- unauthenticated ----------

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.get(self.LIST_URL)
        assert resp.status_code == 401

    # ---------- 5xx ----------

    def test_internal_error_returns_500(self, client, mock_user_services):
        import app.routes.users as mod

        mod.user_service.get_users = AsyncMock(
            side_effect=RuntimeError("DB connection lost")
        )

        resp = client.get(self.LIST_URL)

        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()


class TestGetUser:
    GET_URL = "/api/users/1"

    def _fake_user(self, **overrides):
        return {
            "id": "1",
            "name": "Test User",
            "email": "user@test.com",
            "role": "operator",
            "status": "active",
            "parent_id": None,
            **overrides,
        }

    # ---------- success ----------

    def test_get_user_success(self, client, mock_user_services):
        import app.routes.users as mod

        fake = self._fake_user()
        mod.user_service.get_user_by_id = AsyncMock(return_value=fake)

        resp = client.get(self.GET_URL)

        assert resp.status_code == 200
        body = resp.json()
        assert list(body.keys()) == ["success", "message", "data"]
        assert body["success"] is True
        assert body["data"]["id"] == "1"
        assert body["data"]["email"] == "user@test.com"

    # ---------- not found ----------

    def test_not_found_returns_404(self, client, mock_user_services):
        import app.routes.users as mod

        mod.user_service.get_user_by_id = AsyncMock(return_value=None)

        resp = client.get("/api/users/999")

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    # ---------- unauthenticated ----------

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.get(self.GET_URL)
        assert resp.status_code == 401

    # ---------- 5xx ----------

    def test_internal_error_returns_500(self, client, mock_user_services):
        import app.routes.users as mod

        mod.user_service.get_user_by_id = AsyncMock(
            side_effect=RuntimeError("DB connection lost")
        )

        resp = client.get(self.GET_URL)

        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()


class TestCreateUser:
    CREATE_URL = "/api/users"
    VALID_PAYLOAD = {
        "email": "newuser@test.com",
        "password": "Password123!",
        "name": "New User",
        "role": "operator",
        "parent_id": "cluster-1",
    }

    def _fake_created(self, **overrides):
        return {
            "id": "2",
            "email": "newuser@test.com",
            "name": "New User",
            "role": "operator",
            "status": "active",
            "parent_id": None,
            **overrides,
        }

    # ---------- success ----------

    def test_create_user_success(self, client, mock_user_services):
        import app.routes.users as mod

        fake = self._fake_created()
        mod.user_service.create_user = AsyncMock(return_value=fake)
        mod.user_service.get_user_by_id = AsyncMock(return_value={"id": "cluster-1", "role": "cluster"})

        resp = client.post(self.CREATE_URL, json=self.VALID_PAYLOAD)

        assert resp.status_code == 201
        body = resp.json()
        assert list(body.keys()) == ["success", "message", "data"]
        assert body["success"] is True
        assert body["data"]["email"] == "newuser@test.com"

    # ---------- validation error ----------

    def test_missing_email_returns_422(self, client, mock_user_services):
        payload = {k: v for k, v in self.VALID_PAYLOAD.items() if k != "email"}
        resp = client.post(self.CREATE_URL, json=payload)
        assert resp.status_code == 422

    def test_invalid_email_format_returns_422(self, client, mock_user_services):
        payload = {**self.VALID_PAYLOAD, "email": "not-an-email"}
        resp = client.post(self.CREATE_URL, json=payload)
        assert resp.status_code == 422

    def test_missing_name_returns_422(self, client, mock_user_services):
        payload = {k: v for k, v in self.VALID_PAYLOAD.items() if k != "name"}
        resp = client.post(self.CREATE_URL, json=payload)
        assert resp.status_code == 422

    def test_invalid_role_returns_422(self, client, mock_user_services):
        payload = {**self.VALID_PAYLOAD, "role": "invalid_role"}
        resp = client.post(self.CREATE_URL, json=payload)
        assert resp.status_code == 422

    # ---------- unauthenticated ----------

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.post(self.CREATE_URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 401

    # ---------- 5xx ----------

    def test_internal_error_returns_500(self, client, mock_user_services):
        import app.routes.users as mod

        mod.user_service.get_user_by_id = AsyncMock(return_value={"id": "cluster-1", "role": "cluster"})
        mod.user_service.create_user = AsyncMock(
            side_effect=RuntimeError("DB connection lost")
        )

        resp = client.post(self.CREATE_URL, json=self.VALID_PAYLOAD)

        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()


class TestUpdateUser:
    UPDATE_URL = "/api/users/1"
    VALID_PAYLOAD = {"name": "Updated Name", "email": "updated@test.com"}

    def _fake_user(self, **overrides):
        return {
            "id": "1",
            "name": "Updated Name",
            "email": "updated@test.com",
            "role": "operator",
            "status": "active",
            **overrides,
        }

    # ---------- success ----------

    def test_update_user_success(self, client, mock_user_services):
        import app.routes.users as mod

        fake = self._fake_user()
        mod.user_service.get_user_by_id = AsyncMock(return_value=fake)
        mod.user_service.update_user = AsyncMock(return_value=fake)

        resp = client.put(self.UPDATE_URL, json=self.VALID_PAYLOAD)

        assert resp.status_code == 200
        body = resp.json()
        assert list(body.keys()) == ["success", "message", "data"]
        assert body["success"] is True
        assert body["data"]["name"] == "Updated Name"

    # ---------- not found ----------

    def test_not_found_returns_404(self, client, mock_user_services):
        import app.routes.users as mod

        mod.user_service.get_user_by_id = AsyncMock(return_value=None)

        resp = client.put("/api/users/999", json=self.VALID_PAYLOAD)

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    # ---------- unauthenticated ----------

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.put(self.UPDATE_URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 401

    # ---------- 5xx ----------

    def test_internal_error_returns_500(self, client, mock_user_services):
        import app.routes.users as mod

        mod.user_service.get_user_by_id = AsyncMock(return_value=self._fake_user())
        mod.user_service.update_user = AsyncMock(
            side_effect=RuntimeError("DB connection lost")
        )

        resp = client.put(self.UPDATE_URL, json=self.VALID_PAYLOAD)

        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()


class TestDeleteUser:
    DELETE_URL = "/api/users/2"

    def _fake_target(self, **overrides):
        return {
            "id": "2",
            "name": "Target User",
            "email": "target@test.com",
            "role": "operator",
            "status": "active",
            "parent_id": "1",
            **overrides,
        }

    # ---------- success ----------

    def test_delete_user_success(self, client, mock_user_services):
        import app.routes.users as mod

        mod.user_service.get_user_by_id = AsyncMock(return_value=self._fake_target())
        mod.user_service.delete_user = AsyncMock(return_value=True)

        resp = client.delete(self.DELETE_URL)

        assert resp.status_code == 200
        body = resp.json()
        assert list(body.keys()) == ["success", "message"]
        assert body["success"] is True
        assert body["message"] == "User deleted successfully"

    # ---------- not found ----------

    def test_not_found_returns_404(self, client, mock_user_services):
        import app.routes.users as mod

        mod.user_service.get_user_by_id = AsyncMock(return_value=None)

        resp = client.delete("/api/users/999")

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    # ---------- cannot delete self ----------

    def test_cannot_delete_self_returns_400(self, client, mock_user_services):
        import app.routes.users as mod

        mod.user_service.get_user_by_id = AsyncMock(
            return_value=self._fake_target(id="1")
        )

        resp = client.delete("/api/users/1")

        assert resp.status_code == 400
        assert "own account" in resp.json()["detail"].lower()

    # ---------- unauthenticated ----------

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.delete(self.DELETE_URL)
        assert resp.status_code == 401


class TestReassignUser:
    REASSIGN_URL = "/api/users/2/reassign"
    VALID_PAYLOAD = {"new_parent_id": "3"}

    def _fake_target(self, **overrides):
        return {
            "id": "2",
            "name": "Target User",
            "email": "target@test.com",
            "role": "operator",
            "status": "active",
            "parent_id": "1",
            **overrides,
        }

    def _fake_new_parent(self, **overrides):
        return {
            "id": "3",
            "name": "New Parent",
            "email": "parent@test.com",
            "role": "cluster",
            "status": "active",
            **overrides,
        }

    # ---------- success ----------

    def test_reassign_user_success(self, client, mock_user_services):
        import app.routes.users as mod

        mod.user_service.get_user_by_id = AsyncMock(
            side_effect=[self._fake_target(), self._fake_new_parent()]
        )
        mod.user_service.reassign_user = AsyncMock(
            return_value={"message": "User reassigned successfully", "data": None}
        )

        resp = client.post(self.REASSIGN_URL, json=self.VALID_PAYLOAD)

        assert resp.status_code == 200
        body = resp.json()
        assert list(body.keys()) == ["success", "message", "data"]
        assert body["success"] is True
        assert body["message"] == "User reassigned successfully"

    # ---------- missing new_parent_id ----------

    def test_missing_new_parent_id_returns_400(self, client, mock_user_services):
        import app.routes.users as mod

        mod.user_service.get_user_by_id = AsyncMock(return_value=self._fake_target())

        resp = client.post(self.REASSIGN_URL, json={})

        assert resp.status_code == 400
        assert "new_parent_id" in resp.json()["detail"].lower()

    # ---------- unauthenticated ----------

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.post(self.REASSIGN_URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 401


class TestUpdateUserStatus:
    STATUS_URL = "/api/users/2/status"
    VALID_PAYLOAD = {"status": "inactive"}

    def _fake_user(self, **overrides):
        return {
            "id": "2",
            "name": "Target User",
            "email": "target@test.com",
            "role": "operator",
            "status": "active",
            **overrides,
        }

    # ---------- success ----------

    def test_update_status_success(self, client, mock_user_services):
        import app.routes.users as mod

        fake = self._fake_user()
        updated = self._fake_user(status="inactive")
        mod.user_service.get_user_by_id = AsyncMock(return_value=fake)
        mod.user_service.update_user_status = AsyncMock(return_value=updated)

        resp = client.patch(self.STATUS_URL, json=self.VALID_PAYLOAD)

        assert resp.status_code == 200
        body = resp.json()
        assert list(body.keys()) == ["success", "message", "data"]
        assert body["success"] is True
        assert body["data"]["status"] == "inactive"

    # ---------- invalid status ----------

    def test_invalid_status_returns_400(self, client, mock_user_services):
        import app.routes.users as mod

        mod.user_service.get_user_by_id = AsyncMock(return_value=self._fake_user())

        resp = client.patch(self.STATUS_URL, json={"status": "nonexistent"})

        assert resp.status_code == 400
        assert "invalid status" in resp.json()["detail"].lower()

    # ---------- unauthenticated ----------

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.patch(self.STATUS_URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 401

    # ---------- forbidden for operator ----------

    def test_forbidden_for_operator(self, client, set_role):
        set_role("operator")
        resp = client.patch(self.STATUS_URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 403

    # ---------- 5xx ----------

    def test_internal_error_returns_500(self, client, mock_user_services):
        import app.routes.users as mod

        mod.user_service.get_user_by_id = AsyncMock(return_value=self._fake_user())
        mod.user_service.update_user_status = AsyncMock(
            side_effect=RuntimeError("DB connection lost")
        )

        resp = client.patch(self.STATUS_URL, json=self.VALID_PAYLOAD)

        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()


class TestGetUsersByRole:
    ROLE_URL = "/api/users/role/operator"

    def _fake_user(self, **overrides):
        return {
            "id": "1",
            "name": "Operator User",
            "email": "operator@test.com",
            "role": "operator",
            "status": "active",
            **overrides,
        }

    # ---------- success ----------

    def test_get_users_by_role_success(self, client, mock_user_services):
        import app.routes.users as mod

        fake = self._fake_user()
        mod.user_service.get_users_by_role = AsyncMock(return_value=[fake])

        resp = client.get(self.ROLE_URL)

        assert resp.status_code == 200
        body = resp.json()
        assert list(body.keys()) == ["success", "message", "data"]
        assert body["success"] is True
        assert len(body["data"]) == 1
        assert body["data"][0]["role"] == "operator"

    def test_get_users_by_role_empty_list(self, client, mock_user_services):
        import app.routes.users as mod

        mod.user_service.get_users_by_role = AsyncMock(return_value=[])

        resp = client.get("/api/users/role/operator")

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"] == []

    # ---------- unauthenticated ----------

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.get(self.ROLE_URL)
        assert resp.status_code == 401

    # ---------- forbidden for operator ----------

    def test_forbidden_for_operator(self, client, set_role):
        set_role("operator")
        resp = client.get(self.ROLE_URL)
        assert resp.status_code == 403


class TestBulkUploadUsers:
    BULK_URL = "/api/users/bulk-upload"

    def _fake_parse_file(self, rows=None):
        if rows is None:
            rows = [{"email": "new@t.com", "name": "New", "password": "Pass123", "role": "operator", "cluster_email": "cl@t.com"}]
        return rows

    def _fake_process_result(self, created_count=1, skipped_count=0, error_count=0):
        return {
            "success": True,
            "message": f"Bulk upload complete: {created_count} created, {skipped_count} skipped, {error_count} errors",
            "data": {
                "created_count": created_count,
                "skipped_count": skipped_count,
                "error_count": error_count,
                "created": [{"row": 2, "email": "new@t.com", "role": "operator", "name": "New"}],
                "skipped": [],
                "errors": [],
                "total": 1,
            },
        }

    # ---------- success ----------

    def test_bulk_upload_success(self, client, mock_user_services):
        import app.routes.users as mod

        mod.bulk_upload_service.parse_file = MagicMock(return_value=self._fake_parse_file())
        mod.bulk_upload_service.process_bulk_user_upload = AsyncMock(
            return_value=self._fake_process_result()
        )

        csv_content = b"email,name,password,role,cluster_email\nnew@t.com,New,Pass123,operator,cl@t.com\n"
        resp = client.post(
            self.BULK_URL,
            files={"file": ("users.csv", csv_content, "text/csv")},
        )

        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["created_count"] == 1

    # ---------- validation ----------

    def test_no_file_returns_422(self, client, mock_user_services):
        import app.routes.users as mod

        mod.bulk_upload_service.parse_file = MagicMock()
        mod.bulk_upload_service.process_bulk_user_upload = AsyncMock()

        resp = client.post(self.BULK_URL)
        assert resp.status_code == 422

    def test_invalid_extension_returns_400(self, client, mock_user_services):
        import app.routes.users as mod

        mod.bulk_upload_service.parse_file = MagicMock()
        mod.bulk_upload_service.process_bulk_user_upload = AsyncMock()

        resp = client.post(
            self.BULK_URL,
            files={"file": ("data.txt", b"some content", "text/plain")},
        )
        assert resp.status_code == 400
        assert "Unsupported file format" in resp.json()["detail"]

    def test_empty_file_returns_400(self, client, mock_user_services):
        import app.routes.users as mod

        mod.bulk_upload_service.parse_file = MagicMock(return_value=[])
        mod.bulk_upload_service.process_bulk_user_upload = AsyncMock()

        csv_content = b"email,name\n"
        resp = client.post(
            self.BULK_URL,
            files={"file": ("empty.csv", csv_content, "text/csv")},
        )

        assert resp.status_code == 400
        assert "empty" in resp.json()["detail"].lower()

    # ---------- parse error ----------

    def test_parse_error_returns_400(self, client, mock_user_services):
        import app.routes.users as mod

        mod.bulk_upload_service.parse_file = MagicMock(side_effect=ValueError("Bad encoding"))
        mod.bulk_upload_service.process_bulk_user_upload = AsyncMock()

        resp = client.post(
            self.BULK_URL,
            files={"file": ("bad.csv", b"\xff\xfe", "text/csv")},
        )

        assert resp.status_code == 400
        assert "Failed to parse file" in resp.json()["detail"]

    # ---------- unauthenticated ----------

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.post(
            self.BULK_URL,
            files={"file": ("u.csv", b"email\nx@t.com", "text/csv")},
        )
        assert resp.status_code == 401

    # ---------- forbidden ----------

    def test_forbidden_for_operator(self, client, set_role):
        set_role("operator")
        csv_content = b"email,name,password,role\nx@t.com,X,P@ss,operator\n"
        resp = client.post(
            self.BULK_URL,
            files={"file": ("u.csv", csv_content, "text/csv")},
        )
        assert resp.status_code == 403