"""
Tests for login app models.
"""

import uuid
from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from apps.login.models import EmailVerification, PasswordReset


class EmailVerificationModelTest(TestCase):
    """Test EmailVerification model functionality."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            is_active=False,
        )

    def test_email_verification_creation(self):
        """Test creating an email verification record."""
        verification = EmailVerification.objects.create(user=self.user)

        self.assertIsInstance(verification.token, uuid.UUID)
        self.assertFalse(verification.is_verified)
        self.assertIsNone(verification.verified_at)
        self.assertIsNotNone(verification.created_at)
        self.assertEqual(
            str(verification), f"Email verification for {self.user.username}"
        )

    def test_email_verification_unique_per_user(self):
        """Test that only one email verification can exist per user."""
        EmailVerification.objects.create(user=self.user)

        # Creating another should raise an IntegrityError due to OneToOneField
        with self.assertRaises(Exception):
            EmailVerification.objects.create(user=self.user)

    def test_is_expired_not_expired(self):
        """Test that a recent verification is not expired."""
        verification = EmailVerification.objects.create(user=self.user)
        self.assertFalse(verification.is_expired())

    def test_is_expired_when_expired(self):
        """Test that an old verification is expired."""
        verification = EmailVerification.objects.create(user=self.user)
        # Manually set created_at to 25 hours ago
        verification.created_at = timezone.now() - timedelta(hours=25)
        verification.save()

        self.assertTrue(verification.is_expired())

    def test_is_expired_boundary(self):
        """Test expiration exactly at 24 hour boundary."""
        verification = EmailVerification.objects.create(user=self.user)
        # Set to exactly 24 hours ago
        verification.created_at = timezone.now() - timedelta(hours=24)
        verification.save()

        # Should be expired (boundary condition)
        self.assertTrue(verification.is_expired())

    def test_verify_method(self):
        """Test the verify method activates user and marks as verified."""
        verification = EmailVerification.objects.create(user=self.user)
        self.assertFalse(self.user.is_active)
        self.assertFalse(verification.is_verified)

        verification.verify()

        # Refresh user from database
        self.user.refresh_from_db()
        verification.refresh_from_db()

        self.assertTrue(self.user.is_active)
        self.assertTrue(verification.is_verified)
        self.assertIsNotNone(verification.verified_at)

    def test_verify_method_idempotent(self):
        """Test that calling verify multiple times is safe."""
        verification = EmailVerification.objects.create(user=self.user)

        # Call verify twice
        verification.verify()
        first_verified_at = verification.verified_at

        verification.verify()
        second_verified_at = verification.verified_at

        # Should still be verified and timestamps should be the same
        self.assertTrue(verification.is_verified)
        self.assertEqual(first_verified_at, second_verified_at)


class PasswordResetModelTest(TestCase):
    """Test PasswordReset model functionality."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

    def test_password_reset_creation(self):
        """Test creating a password reset record."""
        reset = PasswordReset.objects.create(user=self.user)

        self.assertIsInstance(reset.token, uuid.UUID)
        self.assertFalse(reset.is_used)
        self.assertIsNone(reset.used_at)
        self.assertIsNotNone(reset.created_at)
        self.assertEqual(str(reset), f"Password reset for {self.user.username}")

    def test_password_reset_unique_tokens(self):
        """Test that each reset gets a unique token."""
        reset1 = PasswordReset.objects.create(user=self.user)
        reset2 = PasswordReset.objects.create(user=self.user)

        self.assertNotEqual(reset1.token, reset2.token)

    def test_is_expired_not_expired(self):
        """Test that a recent reset token is not expired."""
        reset = PasswordReset.objects.create(user=self.user)
        self.assertFalse(reset.is_expired())

    def test_is_expired_when_expired(self):
        """Test that an old reset token is expired."""
        reset = PasswordReset.objects.create(user=self.user)
        # Manually set created_at to 2 hours ago
        reset.created_at = timezone.now() - timedelta(hours=2)
        reset.save()

        self.assertTrue(reset.is_expired())

    def test_is_expired_boundary(self):
        """Test expiration exactly at 1 hour boundary."""
        reset = PasswordReset.objects.create(user=self.user)
        # Set to exactly 1 hour ago
        reset.created_at = timezone.now() - timedelta(hours=1)
        reset.save()

        # Should be expired (boundary condition)
        self.assertTrue(reset.is_expired())

    def test_mark_as_used(self):
        """Test marking a reset token as used."""
        reset = PasswordReset.objects.create(user=self.user)
        self.assertFalse(reset.is_used)
        self.assertIsNone(reset.used_at)

        reset.mark_as_used()

        self.assertTrue(reset.is_used)
        self.assertIsNotNone(reset.used_at)

    def test_mark_as_used_idempotent(self):
        """Test that marking as used multiple times is safe."""
        reset = PasswordReset.objects.create(user=self.user)

        # Mark as used twice
        reset.mark_as_used()
        first_used_at = reset.used_at

        reset.mark_as_used()
        second_used_at = reset.used_at

        # Should still be used and timestamps should be the same
        self.assertTrue(reset.is_used)
        self.assertEqual(first_used_at, second_used_at)

    def test_multiple_reset_tokens_per_user(self):
        """Test that a user can have multiple reset tokens."""
        reset1 = PasswordReset.objects.create(user=self.user)
        reset2 = PasswordReset.objects.create(user=self.user)

        self.assertEqual(PasswordReset.objects.filter(user=self.user).count(), 2)
        self.assertNotEqual(reset1.token, reset2.token)

    def test_reset_tokens_for_different_users(self):
        """Test that different users can have reset tokens."""
        user2 = User.objects.create_user(
            username="testuser2", email="test2@example.com", password="testpass123"
        )

        reset1 = PasswordReset.objects.create(user=self.user)
        reset2 = PasswordReset.objects.create(user=user2)

        self.assertEqual(PasswordReset.objects.filter(user=self.user).count(), 1)
        self.assertEqual(PasswordReset.objects.filter(user=user2).count(), 1)
        self.assertNotEqual(reset1.token, reset2.token)


@pytest.mark.django_db
class TestModelConstraints:
    """Test model constraints and edge cases."""

    def test_email_verification_cascade_delete(self, user_factory):
        """Test that deleting user deletes verification."""
        user = user_factory()
        verification = EmailVerification.objects.create(user=user)

        verification_id = verification.id

        # Delete user
        user.delete()

        # Verification should be deleted too
        assert not EmailVerification.objects.filter(id=verification_id).exists()

    def test_password_reset_cascade_delete(self, user_factory):
        """Test that deleting user deletes password resets."""
        user = user_factory()
        reset1 = PasswordReset.objects.create(user=user)
        reset2 = PasswordReset.objects.create(user=user)

        reset1_id = reset1.id
        reset2_id = reset2.id

        # Delete user
        user.delete()

        # All resets should be deleted too
        assert not PasswordReset.objects.filter(id=reset1_id).exists()
        assert not PasswordReset.objects.filter(id=reset2_id).exists()

    def test_token_uniqueness_across_models(self, user_factory):
        """Test that tokens are unique across all instances."""
        user1 = user_factory(username="user1", email="user1@test.com")
        user2 = user_factory(username="user2", email="user2@test.com")

        # Create multiple instances
        verification = EmailVerification.objects.create(user=user1)
        reset1 = PasswordReset.objects.create(user=user1)
        reset2 = PasswordReset.objects.create(user=user2)

        tokens = [verification.token, reset1.token, reset2.token]

        # All tokens should be unique
        assert len(tokens) == len(set(tokens))
