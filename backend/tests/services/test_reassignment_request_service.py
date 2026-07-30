from app.services.reassignment_request_service import (
    _count_total_children,
    _get_direct_children,
)


class TestCountTotalChildren:
    def test_empty(self):
        assert _count_total_children([]) == 0

    def test_flat(self):
        assert _count_total_children([{"id": "1"}, {"id": "2"}]) == 2

    def test_with_nested(self):
        children = [{"id": "1", "children": [{"id": "2"}, {"id": "3"}]}]
        assert _count_total_children(children) == 3


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
