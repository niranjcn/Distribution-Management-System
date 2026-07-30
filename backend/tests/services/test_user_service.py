from app.services.user_service import escape_like


class TestEscapeLike:
    def test_escapes_special_chars(self):
        assert escape_like("test_%") == "test\\_\\%"

    def test_normal_string_unchanged(self):
        assert escape_like("hello") == "hello"
