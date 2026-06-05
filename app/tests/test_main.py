"""Tests for the main application."""

import pytest
from httpx import AsyncClient


class TestHealthCheck:
    """Tests for the health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_check(self, client: AsyncClient) -> None:
        """Test that the health check returns OK."""
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestUsersEndpoint:
    """Tests for the users endpoints."""

    @pytest.mark.asyncio
    async def test_list_users(self, client: AsyncClient) -> None:
        """Test listing users returns an empty list."""
        response = await client.get("/api/v1/users/")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_read_user_me(self, client: AsyncClient) -> None:
        """Test reading current user returns placeholder data."""
        response = await client.get("/api/v1/users/me")
        assert response.status_code == 200
        assert response.json()["username"] == "currentuser"
