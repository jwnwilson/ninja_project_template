import uuid
from datetime import timedelta

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from apps.core.models import BaseModel


class EmailVerification(BaseModel):
    """Model to store email verification tokens for new user registrations."""

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="email_verification"
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    is_verified = models.BooleanField(default=False)

    def is_expired(self):
        """Check if the verification token has expired (24 hours)."""
        return timezone.now() > self.created_at + timedelta(hours=24)

    def verify(self):
        """Mark the verification as completed."""
        if self.is_verified:
            return
        self.is_verified = True
        self.verified_at = timezone.now()
        self.user.is_active = True
        self.user.save()
        self.save()

    def __str__(self):
        return f"Email verification for {self.user.username}"
