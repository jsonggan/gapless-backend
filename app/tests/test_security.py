"""Tests for security utilities."""


from app.core.security import decode_access_token, verify_password


class TestDecodeAccessToken:
    """Tests for JWT decoding."""

    def test_decode_invalid_token(self) -> None:
        """Test decoding an invalid token returns None."""
        result = decode_access_token("invalid.token.here")
        assert result is None


class TestVerifyPassword:
    """Tests for password verification."""

    def test_verify_password_failure(self) -> None:
        """Test verifying wrong password returns False."""
        from app.core.security import get_password_hash

        hashed = get_password_hash("correct")
        assert verify_password("wrong", hashed) is False
