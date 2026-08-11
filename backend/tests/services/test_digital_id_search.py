import pytest

from app.services.digital_id_search import build_identity_search_clause


class TestBuildIdentitySearchClause:
    def test_builds_clause_for_all_columns(self):
        clause, params = build_identity_search_clause(
            ["distributions.from_user_id", "distributions.to_user_id"], "%abc%"
        )
        assert clause.startswith("(") and clause.endswith(")")
        assert "distributions.from_user_id" in clause
        assert "distributions.to_user_id" in clause
        assert clause.count("EXISTS") == 4
        assert set(params.values()) == {"%abc%"}

    def test_custom_fields(self):
        clause, params = build_identity_search_clause(
            ["def.reported_by"], "%x%", fields=["broadband_id"]
        )
        assert "def.reported_by" in clause
        assert "broadband_id LIKE" in clause
        assert "digital_id LIKE" not in clause
        assert params == {"idm_0_broadband_id": "%x%"}

    def test_rejects_unknown_field(self):
        with pytest.raises(ValueError):
            build_identity_search_clause(["defects.reported_by"], "%x%", fields=["id; DROP TABLE x"])

    def test_rejects_sql_injection_in_column(self):
        with pytest.raises(ValueError):
            build_identity_search_clause(["defects.reported_by = 1 OR 1=1"], "%x%")

    def test_rejects_bare_injection_without_aliasing(self):
        with pytest.raises(ValueError):
            build_identity_search_clause(["defects.reported_by;--"], "%x%")
