from app.services.seed_service import generate_secure_password


class TestGenerateSecurePassword:
    def test_default_length(self):
        pw = generate_secure_password()
        assert len(pw) >= 16

    def test_custom_length(self):
        pw = generate_secure_password(20)
        assert len(pw) == 20

    def test_minimum_length_12(self):
        pw = generate_secure_password(4)
        assert len(pw) >= 12

    def test_contains_all_char_types(self):
        pw = generate_secure_password()
        has_lower = any(c.islower() for c in pw)
        has_upper = any(c.isupper() for c in pw)
        has_digit = any(c.isdigit() for c in pw)
        has_symbol = any(c in "!@#$%^&*()" for c in pw)
        assert has_lower and has_upper and has_digit and has_symbol

    def test_unique_values(self):
        passwords = {generate_secure_password() for _ in range(10)}
        assert len(passwords) > 5
