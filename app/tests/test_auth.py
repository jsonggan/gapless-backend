"""Tests for authentication endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


class TestAuthRegister:
    """Tests for the registration endpoint."""

    @pytest.mark.asyncio
    async def test_register_success(self, client: AsyncClient) -> None:
        """Test successful user registration."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "new@example.com",
                "username": "newuser",
                "password": "password123",
                "full_name": "New User",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "new@example.com"
        assert data["username"] == "newuser"
        assert data["full_name"] == "New User"
        assert "id" in data
        assert "hashed_password" not in data

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client: AsyncClient) -> None:
        """Test registration with duplicate email fails."""
        payload = {
            "email": "dup@example.com",
            "username": "dupuser1",
            "password": "password123",
        }
        response = await client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 201

        payload["username"] = "dupuser2"
        response = await client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 400
        assert "Email already registered" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_register_duplicate_username(self, client: AsyncClient) -> None:
        """Test registration with duplicate username fails."""
        payload = {
            "email": "u1@example.com",
            "username": "sameuser",
            "password": "password123",
        }
        response = await client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 201

        payload["email"] = "u2@example.com"
        response = await client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 400
        assert "Username already taken" in response.json()["detail"]


class TestAuthLogin:
    """Tests for the login endpoint."""

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient) -> None:
        """Test successful login returns a token."""
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "login@example.com",
                "username": "loginuser",
                "password": "password123",
            },
        )
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "login@example.com", "password": "password123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self, client: AsyncClient) -> None:
        """Test login with wrong password fails."""
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "bad@example.com",
                "username": "baduser",
                "password": "password123",
            },
        )
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "bad@example.com", "password": "wrongpassword"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_inactive_user(self, client: AsyncClient, db: AsyncSession) -> None:
        """Test login for inactive user fails."""
        from app.crud.user import user as user_crud
        from app.schemas.user import UserUpdate

        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "inactive@example.com",
                "username": "inactiveuser",
                "password": "password123",
            },
        )
        assert resp.status_code == 201
        user = await user_crud.get_by_email(db, "inactive@example.com")
        assert user is not None
        await user_crud.update(db, user, UserUpdate(is_active=False))

        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "inactive@example.com", "password": "password123"},
        )
        assert response.status_code == 403
