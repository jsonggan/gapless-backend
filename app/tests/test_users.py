"""Tests for user endpoints."""

import pytest
from httpx import AsyncClient

from app.models.user import User


class TestUsersMe:
    """Tests for the /users/me endpoint."""

    @pytest.mark.asyncio
    async def test_read_me_authenticated(self, auth_client: AsyncClient, test_user: User) -> None:
        """Test reading current user when authenticated."""
        response = await auth_client.get("/api/v1/users/me")
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user.email
        assert data["username"] == test_user.username

    @pytest.mark.asyncio
    async def test_read_me_unauthenticated(self, client: AsyncClient) -> None:
        """Test reading current user without auth fails."""
        response = await client.get("/api/v1/users/me")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_update_me(self, auth_client: AsyncClient, test_user: User) -> None:
        """Test updating current user."""
        response = await auth_client.patch(
            "/api/v1/users/me",
            json={"full_name": "Updated Name"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["full_name"] == "Updated Name"


class TestListUsers:
    """Tests for listing users with RBAC."""

    @pytest.mark.asyncio
    async def test_list_users_admin(self, admin_client: AsyncClient) -> None:
        """Test admin can list users."""
        response = await admin_client.get("/api/v1/users/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_list_users_non_admin(self, auth_client: AsyncClient) -> None:
        """Test non-admin cannot list users."""
        response = await auth_client.get("/api/v1/users/")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_list_users_unauthenticated(self, client: AsyncClient) -> None:
        """Test unauthenticated cannot list users."""
        response = await client.get("/api/v1/users/")
        assert response.status_code == 401
