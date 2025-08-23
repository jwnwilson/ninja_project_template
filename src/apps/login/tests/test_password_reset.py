"""
Tests for password reset functionality.
"""

import json
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.login.models import PasswordReset


@pytest.mark.django_db
class TestPasswordResetEndpoints:
    """Test password reset functionality."""

    def test_request_password_reset_success(self, api_client, user_factory, mailbox):
        """Test successful password reset request."""
        user = user_factory(is_active=True)

        response = api_client.post_json(
            "/api/v1/auth/password-reset/request", {"email": user.email}
        )

        assert response.status_code == 200
        data = json.loads(response.content)

        assert data["success"] is True
        assert "reset link has been sent" in data["message"]

        # Check reset token was created
        reset = PasswordReset.objects.get(user=user)
        assert not reset.is_used

        # Check email was sent
        assert len(mailbox) == 1
        assert user.email in mailbox[0].to

    def test_request_password_reset_nonexistent_email(self, api_client):
        """Test password reset request for non-existent email."""
        response = api_client.post_json(
            "/api/v1/auth/password-reset/request", {"email": "nonexistent@example.com"}
        )

        assert response.status_code == 200
        data = json.loads(response.content)

        # Should still return success to prevent email enumeration
        assert data["success"] is True
        assert "reset link has been sent" in data["message"]

        # No reset token should be created
        assert PasswordReset.objects.count() == 0

    def test_request_password_reset_inactive_user(self, api_client, user_factory):
        """Test password reset request for inactive user."""
        user = user_factory(is_active=False)

        response = api_client.post_json(
            "/api/v1/auth/password-reset/request", {"email": user.email}
        )

        assert response.status_code == 200
        data = json.loads(response.content)

        # Should return success but no email sent
        assert data["success"] is True

        # No reset token should be created for inactive user
        assert PasswordReset.objects.filter(user=user).count() == 0

    def test_request_password_reset_invalidates_existing_tokens(
        self, api_client, user_factory
    ):
        """Test that requesting reset invalidates existing tokens."""
        user = user_factory(is_active=True)

        # Create existing reset token
        existing_reset = PasswordReset.objects.create(user=user)
        assert not existing_reset.is_used

        response = api_client.post_json(
            "/api/v1/auth/password-reset/request", {"email": user.email}
        )

        assert response.status_code == 200

        # Check existing token is now marked as used
        existing_reset.refresh_from_db()
        assert existing_reset.is_used

        # Check new token was created
        new_tokens = PasswordReset.objects.filter(user=user, is_used=False)
        assert new_tokens.count() == 1

    def test_confirm_password_reset_success(self, api_client, user_factory):
        """Test successful password reset confirmation."""
        user = user_factory(is_active=True)
        reset = PasswordReset.objects.create(user=user)
        old_password = user.password

        response = api_client.post_json(
            "/api/v1/auth/password-reset/confirm",
            {"token": str(reset.token), "new_password": "newsecurepass456"},
        )

        assert response.status_code == 200
        data = json.loads(response.content)

        assert data["success"] is True
        assert "successfully reset" in data["message"]

        # Check password was changed
        user.refresh_from_db()
        assert user.password != old_password
        assert user.check_password("newsecurepass456")

        # Check token was marked as used
        reset.refresh_from_db()
        assert reset.is_used
        assert reset.used_at is not None

    def test_confirm_password_reset_invalid_token(self, api_client, uuid_token):
        """Test password reset with invalid token."""
        response = api_client.post_json(
            "/api/v1/auth/password-reset/confirm",
            {"token": uuid_token, "new_password": "newsecurepass456"},
        )

        assert response.status_code == 200
        data = json.loads(response.content)

        assert data["success"] is False
        assert "Invalid or expired" in data["message"]

    def test_confirm_password_reset_expired_token(self, api_client, user_factory):
        """Test password reset with expired token."""
        user = user_factory(is_active=True)
        reset = PasswordReset.objects.create(user=user)

        # Make token expired
        reset.created_at = timezone.now() - timedelta(hours=2)
        reset.save()

        response = api_client.post_json(
            "/api/v1/auth/password-reset/confirm",
            {"token": str(reset.token), "new_password": "newsecurepass456"},
        )

        assert response.status_code == 200
        data = json.loads(response.content)

        assert data["success"] is False
        assert "expired" in data["message"]

    def test_confirm_password_reset_used_token(self, api_client, user_factory):
        """Test password reset with already used token."""
        user = user_factory(is_active=True)
        reset = PasswordReset.objects.create(user=user)
        reset.mark_as_used()

        response = api_client.post_json(
            "/api/v1/auth/password-reset/confirm",
            {"token": str(reset.token), "new_password": "newsecurepass456"},
        )

        assert response.status_code == 200
        data = json.loads(response.content)

        assert data["success"] is False
        assert "Invalid or expired" in data["message"]

    def test_confirm_password_reset_weak_password(self, api_client, user_factory):
        """Test password reset with weak password."""
        user = user_factory(is_active=True)
        reset = PasswordReset.objects.create(user=user)

        response = api_client.post_json(
            "/api/v1/auth/password-reset/confirm",
            {
                "token": str(reset.token),
                "new_password": "123",  # Too weak
            },
        )

        assert response.status_code == 200
        data = json.loads(response.content)

        assert data["success"] is False
        assert "Password validation failed" in data["message"]

    def test_confirm_password_reset_invalidates_other_tokens(
        self, api_client, user_factory
    ):
        """Test that successful reset invalidates all other tokens for user."""
        user = user_factory(is_active=True)
        reset1 = PasswordReset.objects.create(user=user)
        PasswordReset.objects.create(user=user)

        response = api_client.post_json(
            "/api/v1/auth/password-reset/confirm",
            {"token": str(reset1.token), "new_password": "newsecurepass456"},
        )

        assert response.status_code == 200

        # Check all tokens for user are now marked as used
        for reset in PasswordReset.objects.filter(user=user):
            reset.refresh_from_db()
            assert reset.is_used
