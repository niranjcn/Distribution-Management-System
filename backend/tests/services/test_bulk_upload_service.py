from unittest.mock import AsyncMock, patch
import pytest
from fastapi import HTTPException

from app.services.bulk_upload_service import (
    chunks,
    parse_file,
    validate_upload_signature,
    _is_likely_text,
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


def _rows(*dicts):
    return list(dicts)


class TestProcessBulkUserUpload:
    """Tests that don't require DB mocking (validation only)."""

    SUPER_ADMIN_USER = {"role": "super_admin", "name": "Admin", "email": "admin@t.com"}
    MANAGER_USER = {"role": "manager", "name": "Manager", "email": "mgr@t.com"}
    OPERATOR_USER = {"role": "operator", "name": "Op", "email": "op@t.com"}

    async def test_insufficient_permissions_raises(self):
        with pytest.raises(HTTPException) as exc:
            await process_bulk_user_upload([], self.OPERATOR_USER)
        assert exc.value.status_code == 403

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

    async def test_manager_can_upload(self):
        result = await process_bulk_user_upload([], self.MANAGER_USER)
        assert result["success"] is True
