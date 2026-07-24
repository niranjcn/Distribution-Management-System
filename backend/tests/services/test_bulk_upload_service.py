from unittest.mock import AsyncMock, patch, MagicMock
from contextlib import asynccontextmanager
import io
import pytest
from fastapi import HTTPException

from app.services.bulk_upload_service import (
    chunks,
    parse_file,
    validate_upload_signature,
    _is_likely_text,
    fetch_existing_values,
    fetch_user_parent_map,
    process_bulk_user_upload,
    _build_response,
)


# ---------------------------------------------------------------------------
# Helper: chunks
# ---------------------------------------------------------------------------

class TestChunks:
    def test_yields_chunks_of_given_size(self):
        result = list(chunks([1, 2, 3, 4, 5], 2))
        assert result == [[1, 2], [3, 4], [5]]

    def test_small_list_single_chunk(self):
        result = list(chunks([1], 10))
        assert result == [[1]]

    def test_empty_list(self):
        result = list(chunks([], 5))
        assert result == []


# ---------------------------------------------------------------------------
# Helper: parse_file
# ---------------------------------------------------------------------------

class TestParseFile:
    def test_parses_csv(self):
        csv_content = b"email,name,role\nfoo@t.com,Foo,operator\n"
        result = parse_file(csv_content, "csv")
        assert len(result) == 1
        assert result[0]["email"] == "foo@t.com"
        assert result[0]["name"] == "Foo"
        assert result[0]["role"] == "operator"

    def test_parses_csv_with_bom(self):
        csv_content = b"\xef\xbb\xbfemail,name\nfoo@t.com,Foo\n"
        result = parse_file(csv_content, "csv")
        assert len(result) == 1
        assert result[0]["email"] == "foo@t.com"

    def test_empty_csv(self):
        result = parse_file(b"", "csv")
        assert result == []

    def test_csv_header_only(self):
        result = parse_file(b"email,name\n", "csv")
        assert result == []

    def test_unknown_ext_returns_empty_list(self):
        result = parse_file(b"some content", "txt")
        assert result == []

    def test_strips_whitespace(self):
        csv_content = b"email, name \n  foo@t.com ,  bar  \n"
        result = parse_file(csv_content, "csv")
        assert result[0]["email"] == "foo@t.com"
        assert result[0]["name"] == "bar"


# ---------------------------------------------------------------------------
# Helper: _is_likely_text / validate_upload_signature
# ---------------------------------------------------------------------------

class TestValidateUploadSignature:
    def test_valid_xlsx_passes(self):
        validate_upload_signature("data.xlsx", b"PK\x03\x04...")

    def test_valid_csv_passes(self):
        validate_upload_signature("data.csv", b"hello,world\n1,2\n")

    def test_invalid_xlsx_raises(self):
        with pytest.raises(HTTPException) as exc:
            validate_upload_signature("bad.xlsx", b"not a zip")
        assert exc.value.status_code == 400

    def test_invalid_xls_raises(self):
        with pytest.raises(HTTPException) as exc:
            validate_upload_signature("bad.xls", b"not ole2")
        assert exc.value.status_code == 400

    def test_binary_csv_raises(self):
        with pytest.raises(HTTPException) as exc:
            validate_upload_signature("bad.csv", b"\x00\x01\x02")
        assert exc.value.status_code == 400

    def test_non_matching_ext_does_nothing(self):
        validate_upload_signature("readme.txt", b"whatever")


class TestIsLikelyText:
    def test_empty_is_text(self):
        assert _is_likely_text(b"") is True

    def test_ascii_is_text(self):
        assert _is_likely_text(b"hello world") is True

    def test_null_bytes_not_text(self):
        assert _is_likely_text(b"\x00\x01\x02") is False


# ---------------------------------------------------------------------------
# Helper: fetch_existing_values
# ---------------------------------------------------------------------------

class TestFetchExistingValues:
    async def test_empty_values_returns_empty_set(self, mock_db):
        result = await fetch_existing_values(mock_db, "users", "email", [])
        assert result == set()

    async def test_no_matches(self, mock_db):
        mock_db.add_result(fetchall_result=[])
        result = await fetch_existing_values(mock_db, "users", "email", ["no@t.com"])
        assert result == set()

    async def test_finds_matches(self, mock_db):
        mock_db.add_result(fetchall_result=[
            {"email": "exists@t.com"},
        ])
        result = await fetch_existing_values(mock_db, "users", "email", ["exists@t.com", "no@t.com"])
        assert "exists@t.com" in result
        assert "no@t.com" not in result

    async def test_handles_row_without_column_key(self, mock_db):
        mock_db.add_result(fetchall_result=[{"email": "exists@t.com"}])
        result = await fetch_existing_values(mock_db, "users", "email", ["exists@t.com"])
        assert "exists@t.com" in result


# ---------------------------------------------------------------------------
# Helper: fetch_user_parent_map
# ---------------------------------------------------------------------------

class TestFetchUserParentMap:
    async def test_empty_emails(self, mock_db):
        result = await fetch_user_parent_map(mock_db, set(), "sub_distributor")
        assert result == {}

    async def test_finds_parents(self, mock_db):
        mock_db.add_result(fetchall_result=[
            {"email": "sub@t.com", "id": 10},
        ])
        result = await fetch_user_parent_map(mock_db, {"sub@t.com"}, "sub_distributor")
        assert result == {"sub@t.com": 10}

    async def test_no_matches(self, mock_db):
        mock_db.add_result(fetchall_result=[])
        result = await fetch_user_parent_map(mock_db, {"missing@t.com"}, "sub_distributor")
        assert result == {}


# ---------------------------------------------------------------------------
# _build_response helper
# ---------------------------------------------------------------------------

class TestBuildResponse:
    def test_minimal(self):
        r = _build_response(1, 0, 0, [], [], [])
        assert r["success"] is True
        assert r["data"]["created_count"] == 1
        assert "total" not in r["data"]

    def test_with_total(self):
        r = _build_response(1, 2, 3, [], [], [], total=10)
        assert r["data"]["total"] == 10


# ---------------------------------------------------------------------------
# Orchestrator: process_bulk_user_upload
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_bulk_db(mock_db):
    @asynccontextmanager
    async def _fake():
        yield mock_db

    patcher = patch("app.services.bulk_upload_service.get_db", _fake)
    patcher.start()
    yield mock_db
    patcher.stop()


def _rows(*dicts):
    return list(dicts)


class TestProcessBulkUserUpload:
    """Tests the orchestrator by patching fetch_existing_values,
    fetch_user_parent_map, get_password_hash, and the DB layer."""

    SUPER_ADMIN_USER = {"role": "super_admin", "name": "Admin", "email": "admin@t.com"}
    MANAGER_USER = {"role": "manager", "name": "Manager", "email": "mgr@t.com"}
    OPERATOR_USER = {"role": "operator", "name": "Op", "email": "op@t.com"}

    # ---------- permission checks ----------

    async def test_insufficient_permissions_raises(self):
        with pytest.raises(HTTPException) as exc:
            await process_bulk_user_upload([], self.OPERATOR_USER)
        assert exc.value.status_code == 403

    # ---------- empty / all-error cases ----------

    async def test_empty_rows_returns_zero_counts(self):
        result = await process_bulk_user_upload([], self.SUPER_ADMIN_USER)
        assert result["success"] is True
        assert result["data"]["created_count"] == 0
        assert result["data"]["skipped_count"] == 0
        assert result["data"]["error_count"] == 0

    async def test_all_missing_fields(self):
        rows = _rows({"email": "", "password": "", "name": ""})
        result = await process_bulk_user_upload(rows, self.SUPER_ADMIN_USER)
        assert result["data"]["created_count"] == 0
        assert result["data"]["error_count"] == 1
        assert "Missing required fields" in result["data"]["errors"][0]["error"]

    async def test_invalid_role(self):
        rows = _rows({"email": "u@t.com", "password": "P@ss1", "name": "U", "role": "bad_role"})
        result = await process_bulk_user_upload(rows, self.SUPER_ADMIN_USER)
        assert result["data"]["error_count"] == 1
        assert "Invalid role" in result["data"]["errors"][0]["error"]

    async def test_duplicate_email_in_file(self, mock_bulk_db, mocker):
        mocker.patch("app.services.bulk_upload_service.fetch_existing_values", return_value=set())
        mocker.patch("app.services.bulk_upload_service.fetch_user_parent_map", return_value={})
        with patch("app.services.bulk_upload_service.log_business_activity", new=AsyncMock()):
            with patch("app.services.bulk_upload_service.audit_logger"):
                with patch("app.utils.security.get_password_hash", return_value="h"):
                    rows = _rows(
                        {"email": "dup@t.com", "password": "P@ss1", "name": "A", "role": "operator", "cluster_email": "cl@t.com"},
                        {"email": "dup@t.com", "password": "P@ss2", "name": "B", "role": "operator", "cluster_email": "cl@t.com"},
                    )
                    result = await process_bulk_user_upload(rows, self.SUPER_ADMIN_USER)
        assert result["data"]["created_count"] == 0
        assert result["data"]["skipped_count"] == 1
        assert "Duplicate email" in result["data"]["skipped"][0]["reason"]

    # ---------- DB interaction with mocked helpers ----------

    async def test_successful_upload(self, mock_bulk_db, mocker):
        mocker.patch("app.services.bulk_upload_service.fetch_existing_values", return_value=set())
        mocker.patch("app.services.bulk_upload_service.fetch_user_parent_map",
                      return_value={"cl@t.com": 20})
        with patch("app.services.bulk_upload_service.log_business_activity", new=AsyncMock()):
            with patch("app.services.bulk_upload_service.audit_logger"):
                with patch("app.utils.security.get_password_hash", return_value="hashed_pw"):
                    rows = _rows({
                        "email": "op@t.com",
                        "password": "P@ss123!",
                        "name": "Operator",
                        "role": "operator",
                        "cluster_email": "cl@t.com",
                    })
                    result = await process_bulk_user_upload(rows, self.SUPER_ADMIN_USER)

        assert result["success"] is True
        assert result["data"]["created_count"] == 1
        assert result["data"]["error_count"] == 0
        assert result["data"]["created"][0]["email"] == "op@t.com"

    async def test_existing_email_in_db_skipped(self, mock_bulk_db, mocker):
        mocker.patch("app.services.bulk_upload_service.fetch_existing_values",
                      return_value={"exists@t.com"})
        mocker.patch("app.services.bulk_upload_service.fetch_user_parent_map", return_value={})
        with patch("app.services.bulk_upload_service.log_business_activity", new=AsyncMock()):
            with patch("app.services.bulk_upload_service.audit_logger"):
                with patch("app.utils.security.get_password_hash", return_value="h"):
                    rows = _rows({
                        "email": "exists@t.com",
                        "password": "P@ss1",
                        "name": "Exists",
                        "role": "operator",
                        "cluster_email": "cl@t.com",
                    })
                    result = await process_bulk_user_upload(rows, self.SUPER_ADMIN_USER)

        assert result["data"]["created_count"] == 0
        assert result["data"]["skipped_count"] == 1
        assert "already exists" in result["data"]["skipped"][0]["reason"]

    async def test_parent_not_found_logged_as_error(self, mock_bulk_db, mocker):
        mocker.patch("app.services.bulk_upload_service.fetch_existing_values", return_value=set())
        mocker.patch("app.services.bulk_upload_service.fetch_user_parent_map", return_value={})
        with patch("app.services.bulk_upload_service.log_business_activity", new=AsyncMock()):
            with patch("app.services.bulk_upload_service.audit_logger"):
                with patch("app.utils.security.get_password_hash", return_value="h"):
                    rows = _rows({
                        "email": "op@t.com",
                        "password": "P@ss1",
                        "name": "Op",
                        "role": "operator",
                        "cluster_email": "missing_cluster@t.com",
                    })
                    result = await process_bulk_user_upload(rows, self.SUPER_ADMIN_USER)

        assert result["data"]["created_count"] == 0
        assert result["data"]["error_count"] == 1
        assert "not found" in result["data"]["errors"][0]["error"].lower()

    async def test_missing_parent_email_for_cluster(self, mock_bulk_db, mocker):
        mocker.patch("app.services.bulk_upload_service.fetch_existing_values", return_value=set())
        mocker.patch("app.services.bulk_upload_service.fetch_user_parent_map", return_value={})
        with patch("app.services.bulk_upload_service.log_business_activity", new=AsyncMock()):
            with patch("app.services.bulk_upload_service.audit_logger"):
                with patch("app.utils.security.get_password_hash", return_value="h"):
                    rows = _rows({
                        "email": "cl@t.com",
                        "password": "P@ss1",
                        "name": "Cluster",
                        "role": "cluster",
                    })
                    result = await process_bulk_user_upload(rows, self.SUPER_ADMIN_USER)
        assert result["data"]["created_count"] == 0
        assert result["data"]["error_count"] == 1
        assert "sub_distributor_email is required" in result["data"]["errors"][0]["error"]

    async def test_manager_can_upload(self):
        result = await process_bulk_user_upload([], self.MANAGER_USER)
        assert result["success"] is True

    # ---------- batch insert fallback ----------

    async def test_batch_fallback_on_executemany_error(self, mock_bulk_db, mocker):
        mocker.patch("app.services.bulk_upload_service.fetch_existing_values", return_value=set())
        mocker.patch("app.services.bulk_upload_service.fetch_user_parent_map",
                      return_value={"cl@t.com": 20})

        async def _executemany_raises(*a, **kw):
            raise Exception("Batch insert failed")

        mock_bulk_db.executemany = _executemany_raises

        with patch("app.services.bulk_upload_service.log_business_activity", new=AsyncMock()):
            with patch("app.services.bulk_upload_service.audit_logger"):
                with patch("app.utils.security.get_password_hash", return_value="h"):
                    rows = _rows({
                        "email": "op@t.com",
                        "password": "P@ss1",
                        "name": "Op",
                        "role": "operator",
                        "cluster_email": "cl@t.com",
                    })
                    result = await process_bulk_user_upload(rows, self.SUPER_ADMIN_USER)

        # fallback: per-row insert succeeds, so the user is still created
        assert result["data"]["created_count"] == 1

    async def test_rollback_on_unrecoverable_error(self, mock_bulk_db, mocker):
        mocker.patch("app.services.bulk_upload_service.fetch_existing_values", return_value=set())
        mocker.patch("app.services.bulk_upload_service.fetch_user_parent_map",
                      return_value={"cl@t.com": 20})

        async def _executemany_raises(*a, **kw):
            raise Exception("Batch failed")

        async def _execute_raises(*a, **kw):
            raise Exception("Disk full")

        mock_bulk_db.executemany = _executemany_raises
        mock_bulk_db.execute = _execute_raises

        with patch("app.services.bulk_upload_service.log_business_activity", new=AsyncMock()):
            with patch("app.services.bulk_upload_service.audit_logger"):
                with patch("app.utils.security.get_password_hash", return_value="h"):
                    rows = _rows({
                        "email": "op@t.com",
                        "password": "P@ss1",
                        "name": "Op",
                        "role": "operator",
                        "cluster_email": "cl@t.com",
                    })
                    with pytest.raises(HTTPException) as exc:
                        await process_bulk_user_upload(rows, self.SUPER_ADMIN_USER)

        assert exc.value.status_code == 500
        assert "rolled back" in exc.value.detail.lower()

    # ---------- full integration with real helpers ----------

    async def test_integration_with_real_fetchers(self, mock_bulk_db):
        # This test lets fetch_existing_values / fetch_user_parent_map
        # run against the mock DB, validating end-to-end wiring.

        # fetch_existing_values → no existing emails
        mock_bulk_db.add_result(fetchall_result=[])
        # fetch_user_parent_map (sub_distributor) → found parent
        mock_bulk_db.add_result(fetchall_result=[{"email": "sub@t.com", "id": 10}])
        # fetch_user_parent_map (cluster) → no cluster emails, so no query
        # executemany → success (no registered result, default MockCursor)
        # commit

        with patch("app.services.bulk_upload_service.log_business_activity", new=AsyncMock()):
            with patch("app.services.bulk_upload_service.audit_logger"):
                with patch("app.utils.security.get_password_hash", return_value="h"):
                    rows = _rows({
                        "email": "newcl@t.com",
                        "password": "P@ss1",
                        "name": "New Cluster",
                        "role": "cluster",
                        "sub_distributor_email": "sub@t.com",
                    })
                    result = await process_bulk_user_upload(rows, self.SUPER_ADMIN_USER)

        assert result["data"]["created_count"] == 1
        assert result["data"]["error_count"] == 0
