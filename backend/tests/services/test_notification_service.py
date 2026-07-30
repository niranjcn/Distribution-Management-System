from app.services.notification_service import (
    _parse_notification_metadata,
    _parse_notification_list,
)


class TestParseNotificationMetadata:
    def test_string_metadata_parsed(self):
        n = {"metadata": '{"key": "val"}'}
        result = _parse_notification_metadata(n)
        assert result["metadata"] == {"key": "val"}

    def test_dict_metadata_unchanged(self):
        n = {"metadata": {"key": "val"}}
        result = _parse_notification_metadata(n)
        assert result["metadata"] == {"key": "val"}

    def test_invalid_json_returns_none(self):
        n = {"metadata": "not-json"}
        result = _parse_notification_metadata(n)
        assert result["metadata"] is None

    def test_missing_metadata(self):
        n = {}
        result = _parse_notification_metadata(n)
        assert "metadata" not in result


class TestParseNotificationList:
    def test_empty_list(self):
        assert _parse_notification_list([]) == []

    def test_calls_parse_on_each(self):
        items = [{"metadata": '{"a":1}'}, {"metadata": '{"b":2}'}]
        result = _parse_notification_list(items)
        assert result[0]["metadata"] == {"a": 1}
        assert result[1]["metadata"] == {"b": 2}
