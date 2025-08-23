import logging
from typing import Any, Dict

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from ninja import Schema
from ninja_extra import ControllerBase, api_controller, http_get, http_post
from ninja_extra.permissions import AllowAny
from ninja_jwt.controller import TokenObtainPairController, TokenVerificationController

from apps.core.tasks import send_email_task

from ..models import EmailVerification, PasswordReset

logger = logging.getLogger(__name__)


class SignupSchema(Schema):
    """Schema for user signup."""

    username: str
    email: str
    password: str
    first_name: str = ""
    last_name: str = ""


class SignupResponseSchema(Schema):
    """Schema for signup response."""

    message: str
    user_id: int
    verification_required: bool = True


class VerificationResponseSchema(Schema):
    """Schema for verification response."""

    message: str
    verified: bool


class ResendVerificationSchema(Schema):
    """Schema for resending verification email."""

    email: str


class PasswordResetRequestSchema(Schema):
    """Schema for password reset request."""

    email: str


class PasswordResetConfirmSchema(Schema):
    """Schema for password reset confirmation."""

    token: str
    new_password: str


class PasswordResetResponseSchema(Schema):
    """Schema for password reset response."""

    message: str
    success: bool


@api_controller("/token", permissions=[AllowAny], tags=["Authentication"], auth=None)
class NinjaJWTController(
    ControllerBase, TokenVerificationController, TokenObtainPairController
):
    """NinjaJWT controller for obtaining and refreshing tokens"""

    auto_import = False


@api_controller("/auth", auth=None, tags=["Authentication"])
class SignupController(ControllerBase):
    """Controller for user signup and email verification."""

    @http_post("/signup", response=SignupResponseSchema)
    def signup(self, request: HttpRequest, payload: SignupSchema) -> Dict[str, Any]:
        """
        Register a new user account.

        Creates a new user account and sends an email verification link.
        The user account will be inactive until email verification is completed.
        """
        try:
            # Check if username already exists
            if User.objects.filter(username=payload.username).exists():
                return {
                    "message": "Username already exists",
                    "user_id": 0,
                    "verification_required": False,
                }

            # Check if email already exists
            if User.objects.filter(email=payload.email).exists():
                return {
                    "message": "Email already registered",
                    "user_id": 0,
                    "verification_required": False,
                }

            # Validate password
            try:
                validate_password(payload.password)
            except ValidationError as e:
                return {
                    "message": f"Password validation failed: {', '.join(e.messages)}",
                    "user_id": 0,
                    "verification_required": False,
                }

            # Create user (inactive by default)
            user = User.objects.create_user(
                username=payload.username,
                email=payload.email,
                password=payload.password,
                first_name=payload.first_name,
                last_name=payload.last_name,
                is_active=False,  # User will be activated after email verification
            )

            # Create email verification record
            verification = EmailVerification.objects.create(user=user)

            # Send verification email
            self._send_verification_email(user, verification)

            logger.info(
                f"User {user.username} registered successfully. Verification email sent."
            )

            return {
                "message": "User registered successfully. Please check your email for verification link.",
                "user_id": user.id,
                "verification_required": True,
            }

        except Exception as e:
            logger.error(f"Error during user signup: {str(e)}")
            return {
                "message": "An error occurred during registration. Please try again.",
                "user_id": 0,
                "verification_required": False,
            }

    @http_get("/verify/{token}", response=VerificationResponseSchema)
    def verify_email(self, request: HttpRequest, token: str) -> Dict[str, Any]:
        """
        Verify user email address using verification token.

        Args:
            token: UUID verification token sent to user's email

        Returns:
            Verification result with success/failure message
        """
        # Let get_object_or_404 raise the 404 exception naturally for invalid tokens
        verification = get_object_or_404(EmailVerification, token=token)

        try:
            # Check if already verified
            if verification.is_verified:
                return {"message": "Email already verified", "verified": True}

            # Check if token is expired
            if verification.is_expired():
                return {
                    "message": "Verification token has expired. Please request a new verification email.",
                    "verified": False,
                }

            # Verify the email
            verification.verify()

            logger.info(
                f"Email verified successfully for user {verification.user.username}"
            )

            return {
                "message": "Email verified successfully. Your account is now active.",
                "verified": True,
            }

        except Exception as e:
            logger.error(f"Error during email verification: {str(e)}")
            return {
                "message": "Invalid or expired verification token.",
                "verified": False,
            }

    @http_post("/resend-verification", response=SignupResponseSchema)
    def resend_verification(
        self, request: HttpRequest, payload: ResendVerificationSchema
    ) -> Dict[str, Any]:
        """
        Resend verification email for a user.

        Expects a JSON payload with 'email' field.
        """
        # Let get_object_or_404 raise the 404 exception naturally for nonexistent users
        user = get_object_or_404(User, email=payload.email)

        try:
            # Check if user is already verified
            if user.is_active:
                return {
                    "message": "User is already verified",
                    "user_id": user.id,
                    "verification_required": False,
                }

            # Get or create verification record
            verification, created = EmailVerification.objects.get_or_create(user=user)

            # If verification exists and is not expired, use it; otherwise create new token
            if not created and verification.is_expired():
                verification.delete()
                verification = EmailVerification.objects.create(user=user)

            # Send verification email
            self._send_verification_email(user, verification)

            logger.info(f"Verification email resent for user {user.username}")

            return {
                "message": "Verification email sent. Please check your email.",
                "user_id": user.id,
                "verification_required": True,
            }

        except Exception as e:
            logger.error(f"Error resending verification email: {str(e)}")
            return {
                "message": "Error sending verification email. Please try again.",
                "user_id": 0,
                "verification_required": False,
            }

    def _send_verification_email(
        self, user: User, verification: EmailVerification
    ) -> None:
        """
        Send verification email to user.

        Args:
            user: User instance
            verification: EmailVerification instance
        """
        try:
            subject = "Verify Your Email Address"
            # In production, this should be your actual domain
            verification_url = (
                f"{getattr(settings, 'FRONTEND_VERIFY_URL')}/{verification.token}"
            )

            message = f"""
            Hi {user.first_name or user.username},
            
            Thank you for registering with AI Pet!
            
            Please click the link below to verify your email address:
            {verification_url}
            
            This link will expire in 24 hours.
            
            If you didn't create this account, please ignore this email.
            
            Best regards,
            AI Pet Team
            """

            send_email_task.delay(
                subject=subject,
                message=message,
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@{{project_slug}}.com"),
                recipient_list=[user.email],
                fail_silently=False,
            )

        except Exception as e:
            logger.error(f"Failed to send verification email to {user.email}: {str(e)}")
            # Re-raise the exception so the caller can handle it
            raise

    @http_post("/password-reset/request", response=PasswordResetResponseSchema)
    def request_password_reset(
        self, request: HttpRequest, payload: PasswordResetRequestSchema
    ) -> Dict[str, Any]:
        """
        Request a password reset email.

        Sends a password reset email to the user if the email exists in the system.
        Always returns success to prevent email enumeration attacks.
        """
        try:
            # Always return success to prevent email enumeration
            # But only send email if user exists
            try:
                user = User.objects.get(email=payload.email)

                # Only send reset email if user is active
                if user.is_active:
                    # Invalidate any existing password reset tokens for this user
                    PasswordReset.objects.filter(user=user, is_used=False).update(
                        is_used=True
                    )

                    # Create new password reset token
                    reset_token = PasswordReset.objects.create(user=user)

                    # Send password reset email
                    self._send_password_reset_email(user, reset_token)

                    logger.info(f"Password reset email sent for user {user.username}")

            except User.DoesNotExist:
                # Don't reveal that the user doesn't exist
                logger.info(
                    f"Password reset requested for non-existent email: {payload.email}"
                )
                pass

            return {
                "message": "If the email exists in our system, a password reset link has been sent.",
                "success": True,
            }

        except Exception as e:
            logger.error(f"Error during password reset request: {str(e)}")
            return {
                "message": "An error occurred while processing your request. Please try again.",
                "success": False,
            }

    @http_post("/password-reset/confirm", response=PasswordResetResponseSchema)
    def confirm_password_reset(
        self, request: HttpRequest, payload: PasswordResetConfirmSchema
    ) -> Dict[str, Any]:
        """
        Confirm password reset using the token from email.

        Args:
            payload: Contains token and new_password

        Returns:
            Success/failure message
        """
        try:
            # Get the password reset token
            try:
                reset_token = PasswordReset.objects.get(
                    token=payload.token, is_used=False
                )
            except PasswordReset.DoesNotExist:
                return {"message": "Invalid or expired reset token.", "success": False}

            # Check if token is expired
            if reset_token.is_expired():
                return {
                    "message": "Password reset token has expired. Please request a new one.",
                    "success": False,
                }

            # Validate the new password
            try:
                validate_password(payload.new_password, reset_token.user)
            except ValidationError as e:
                return {
                    "message": f"Password validation failed: {', '.join(e.messages)}",
                    "success": False,
                }

            # Update the user's password
            user = reset_token.user
            user.set_password(payload.new_password)
            user.save()

            # Mark the reset token as used
            reset_token.mark_as_used()

            # Invalidate any other unused reset tokens for this user
            PasswordReset.objects.filter(user=user, is_used=False).update(is_used=True)

            logger.info(f"Password successfully reset for user {user.username}")

            return {
                "message": "Password has been successfully reset. You can now login with your new password.",
                "success": True,
            }

        except Exception as e:
            logger.error(f"Error during password reset confirmation: {str(e)}")
            return {
                "message": "An error occurred while resetting your password. Please try again.",
                "success": False,
            }

    def _send_password_reset_email(
        self, user: User, reset_token: PasswordReset
    ) -> None:
        """
        Send password reset email to user.

        Args:
            user: User instance
            reset_token: PasswordReset instance
        """
        try:
            subject = "Reset Your Password"
            # In production, this should be your actual domain
            reset_url = "http://localhost:8000/api/v1/auth/password-reset/confirm"

            {% raw %}
            message = f"""
            Hi {user.first_name or user.username},
            
            You have requested to reset your password for your AI Pet account.
            
            Please use the following token to reset your password:
            Token: {reset_token.token}
            
            You can reset your password by making a POST request to:
            {reset_url}
            
            With the following JSON payload:
            {{
                "token": "{reset_token.token}",
                "new_password": "your_new_password"
            }}
            
            This token will expire in 1 hour.
            
            If you didn't request this password reset, please ignore this email.
            
            Best regards,
            AI Pet Team
            """
            {% endraw %}

            send_mail(
                subject=subject,
                message=message,
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@{{project_slug}}.com"),
                recipient_list=[user.email],
                fail_silently=False,
            )

        except Exception as e:
            logger.error(
                f"Failed to send password reset email to {user.email}: {str(e)}"
            )
            # Re-raise the exception so the caller can handle it
            raise
