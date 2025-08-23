"""
Tests for signup functionality.
"""

import json
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from apps.login.models import EmailVerification


@pytest.mark.django_db
class TestSignupEndpoints:
    """Test SignupController signup-related endpoints."""

    @patch("apps.core.tasks.send_email_task.delay")
    def test_signup_success(
        self, mock_send_email_task, api_client, sample_user_data, mailbox
    ):
        """Test successful user signup."""
        # Mock the Celery task to return a mock result
        mock_send_email_task.return_value = MagicMock()

        response = api_client.post_json("/api/v1/auth/signup", sample_user_data)

        assert response.status_code == 200
        data = json.loads(response.content)

        assert data["verification_required"] is True
        assert "verification link" in data["message"]
        assert data["user_id"] > 0

        # Check user was created but inactive
        user = User.objects.get(username=sample_user_data["username"])
        assert not user.is_active
        assert user.email == sample_user_data["email"]

        # Check verification record was created
        verification = EmailVerification.objects.get(user=user)
        assert not verification.is_verified

        # Verify Celery task was called with correct parameters
        mock_send_email_task.assert_called_once()
        call_args = mock_send_email_task.call_args
        assert call_args.kwargs["subject"] == "Verify Your Email Address"
        assert sample_user_data["email"] in call_args.kwargs["recipient_list"]
        assert str(verification.token) in call_args.kwargs["message"]
        assert "noreply@{{project_slug}}.com" == call_args.kwargs["from_email"]

    def test_signup_duplicate_username(
        self, api_client, sample_user_data, user_factory
    ):
        """Test signup with duplicate username."""
        # Create existing user
        user_factory(username=sample_user_data["username"])

        response = api_client.post_json("/api/v1/auth/signup", sample_user_data)

        assert response.status_code == 200
        data = json.loads(response.content)

        assert data["verification_required"] is False
        assert "Username already exists" in data["message"]
        assert data["user_id"] == 0

    def test_signup_duplicate_email(self, api_client, sample_user_data, user_factory):
        """Test signup with duplicate email."""
        # Create existing user with same email
        user_factory(email=sample_user_data["email"])

        response = api_client.post_json("/api/v1/auth/signup", sample_user_data)

        assert response.status_code == 200
        data = json.loads(response.content)

        assert data["verification_required"] is False
        assert "Email already registered" in data["message"]
        assert data["user_id"] == 0

    def test_signup_weak_password(self, api_client, sample_user_data):
        """Test signup with weak password."""
        sample_user_data["password"] = "123"  # Too weak

        response = api_client.post_json("/api/v1/auth/signup", sample_user_data)

        assert response.status_code == 200
        data = json.loads(response.content)

        assert data["verification_required"] is False
        assert "Password validation failed" in data["message"]
        assert data["user_id"] == 0

    @patch("apps.core.tasks.send_email_task.delay")
    def test_signup_email_failure(
        self, mock_send_email_task, api_client, sample_user_data
    ):
        """Test signup when email sending fails."""
        mock_send_email_task.side_effect = Exception("Email failed")

        response = api_client.post_json("/api/v1/auth/signup", sample_user_data)

        assert response.status_code == 200
        data = json.loads(response.content)

        assert data["verification_required"] is False
        assert "error occurred during registration" in data["message"]
        assert data["user_id"] == 0

        # Verify Celery task was called but failed
        mock_send_email_task.assert_called_once()


@pytest.mark.django_db
class TestEmailVerificationEndpoints:
    """Test email verification endpoints."""

    def test_verify_email_success(self, api_client, user_factory):
        """Test successful email verification."""
        # Create inactive user with verification
        user = user_factory(is_active=False)
        verification = EmailVerification.objects.create(user=user)

        response = api_client.get(f"/api/v1/auth/verify/{verification.token}")

        assert response.status_code == 200
        data = json.loads(response.content)

        assert data["verified"] is True
        assert "successfully" in data["message"]

        # Check user is now active
        user.refresh_from_db()
        verification.refresh_from_db()
        assert user.is_active
        assert verification.is_verified

    def test_verify_email_invalid_token(self, api_client, uuid_token):
        """Test email verification with invalid token."""
        response = api_client.get(f"/api/v1/auth/verify/{uuid_token}")

        assert response.status_code == 404  # get_object_or_404 returns 404

    def test_verify_email_already_verified(self, api_client, user_factory):
        """Test verifying already verified email."""
        user = user_factory(is_active=True)
        verification = EmailVerification.objects.create(user=user, is_verified=True)

        response = api_client.get(f"/api/v1/auth/verify/{verification.token}")

        assert response.status_code == 200
        data = json.loads(response.content)

        assert data["verified"] is True
        assert "already verified" in data["message"]

    def test_verify_email_expired_token(self, api_client, user_factory):
        """Test verifying with expired token."""
        user = user_factory(is_active=False)
        verification = EmailVerification.objects.create(user=user)

        # Make token expired
        verification.created_at = timezone.now() - timedelta(hours=25)
        verification.save()

        response = api_client.get(f"/api/v1/auth/verify/{verification.token}")

        assert response.status_code == 200
        data = json.loads(response.content)

        assert data["verified"] is False
        assert "expired" in data["message"]

    @patch("apps.core.tasks.send_email_task.delay")
    def test_resend_verification_success(
        self, mock_send_email_task, api_client, user_factory, mailbox
    ):
        """Test successful verification email resend."""
        # Mock the Celery task to return a mock result
        mock_send_email_task.return_value = MagicMock()

        user = user_factory(is_active=False)
        verification = EmailVerification.objects.create(user=user)

        response = api_client.post_json(
            "/api/v1/auth/resend-verification", {"email": user.email}
        )

        assert response.status_code == 200
        data = json.loads(response.content)

        assert data["verification_required"] is True
        assert "email sent" in data["message"]

        # Verify Celery task was called with correct parameters
        mock_send_email_task.assert_called_once()
        call_args = mock_send_email_task.call_args
        assert call_args.kwargs["subject"] == "Verify Your Email Address"
        assert user.email in call_args.kwargs["recipient_list"]
        assert str(verification.token) in call_args.kwargs["message"]
        assert "noreply@{{project_slug}}.com" == call_args.kwargs["from_email"]

    def test_resend_verification_already_verified(self, api_client, user_factory):
        """Test resending verification for already verified user."""
        user = user_factory(is_active=True)

        response = api_client.post_json(
            "/api/v1/auth/resend-verification", {"email": user.email}
        )

        assert response.status_code == 200
        data = json.loads(response.content)

        assert data["verification_required"] is False
        assert "already verified" in data["message"]

    def test_resend_verification_nonexistent_user(self, api_client):
        """Test resending verification for non-existent user."""
        response = api_client.post_json(
            "/api/v1/auth/resend-verification", {"email": "nonexistent@example.com"}
        )

        assert response.status_code == 404  # get_object_or_404 returns 404


@pytest.mark.django_db
class TestCeleryEmailTask:
    """Test the Celery email task directly."""

    @patch("apps.core.tasks.send_mail")
    def test_send_email_task_success(self, mock_send_mail):
        """Test that the Celery email task works correctly."""
        from apps.core.tasks import send_email_task

        # Mock successful email sending
        mock_send_mail.return_value = None

        # Call the task directly
        send_email_task(
            subject="Test Subject",
            message="Test message",
            recipient_list=["test@example.com"],
            from_email="from@example.com",
            fail_silently=False,
        )

        # Verify send_mail was called with correct parameters
        mock_send_mail.assert_called_once_with(
            subject="Test Subject",
            message="Test message",
            from_email="from@example.com",
            recipient_list=["test@example.com"],
            fail_silently=False,
        )

    @patch("apps.core.tasks.send_mail")
    def test_send_email_task_failure(self, mock_send_mail):
        """Test that the Celery email task handles failures correctly."""
        from apps.core.tasks import send_email_task

        # Mock email sending failure
        mock_send_mail.side_effect = Exception("SMTP Error")

        with pytest.raises(Exception, match="SMTP Error"):
            # Call the task
            send_email_task(
                subject="Test Subject",
                message="Test message",
                recipient_list=["test@example.com"],
            )
