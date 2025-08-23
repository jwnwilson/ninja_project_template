import uuid
from datetime import timedelta

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from apps.core.models import BaseModel


class PasswordReset(BaseModel):
    """Model to store password reset tokens."""

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="password_resets"
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)
    is_used = models.BooleanField(default=False)

    def is_expired(self):
        """Check if the reset token has expired (1 hour)."""
        return timezone.now() > self.created_at + timedelta(hours=1)

    def mark_as_used(self):
        """Mark the reset token as used."""
        if self.is_used:
            return
        self.is_used = True
        self.used_at = timezone.now()
        self.save()

    def __str__(self):
        return f"Password reset for {self.user.username}"
