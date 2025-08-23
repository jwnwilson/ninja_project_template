# User Authentication API

This document describes the user authentication endpoints including signup, email verification, and password reset functionality for the AI Pet Django-Ninja application.

## Overview

The authentication system includes:
- User registration with email verification
- Email verification via token
- Resend verification email functionality
- Password reset via email with token verification

## API Endpoints

### 1. User Signup
**POST** `/api/v1/auth/signup`

Register a new user account. The user will be created but inactive until email verification is completed.

**Request Body:**
```json
{
    "username": "john_doe",
    "email": "john@example.com", 
    "password": "secure_password123",
    "first_name": "John",
    "last_name": "Doe"
}
```

**Response:**
```json
{
    "message": "User registered successfully. Please check your email for verification link.",
    "user_id": 123,
    "verification_required": true
}
```

**Error Responses:**
- Username already exists
- Email already registered
- Password validation failed

### 2. Email Verification
**GET** `/api/v1/auth/verify/{token}`

Verify user email address using the verification token sent via email.

**Parameters:**
- `token`: UUID verification token from email

**Response:**
```json
{
    "message": "Email verified successfully. Your account is now active.",
    "verified": true
}
```

**Error Responses:**
- Invalid or expired verification token
- Email already verified
- Token expired (24 hours)

### 3. Resend Verification Email
**POST** `/api/v1/auth/resend-verification`

Resend verification email for a user who hasn't verified their email yet.

**Request Body:**
```json
{
    "email": "john@example.com"
}
```

**Response:**
```json
{
    "message": "Verification email sent. Please check your email.",
    "user_id": 123,
    "verification_required": true
}
```

### 4. Request Password Reset
**POST** `/api/v1/auth/password-reset/request`

Request a password reset email. Always returns success to prevent email enumeration attacks.

**Request Body:**
```json
{
    "email": "john@example.com"
}
```

**Response:**
```json
{
    "message": "If the email exists in our system, a password reset link has been sent.",
    "success": true
}
```

### 5. Confirm Password Reset
**POST** `/api/v1/auth/password-reset/confirm`

Reset password using the token received via email.

**Request Body:**
```json
{
    "token": "12345678-1234-1234-1234-123456789abc",
    "new_password": "new_secure_password123"
}
```

**Response:**
```json
{
    "message": "Password has been successfully reset. You can now login with your new password.",
    "success": true
}
```

**Error Responses:**
- Invalid or expired reset token
- Password validation failed
- Token expired (1 hour)

## Email Configuration

### Development
In development mode, emails are printed to the console for testing.

### Production
For production, update the email settings in `settings.py`:

```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'  # or your SMTP server
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@gmail.com'
EMAIL_HOST_PASSWORD = 'your-app-password'
```

## Database Models

### EmailVerification Model
- `user`: OneToOneField to Django User model
- `token`: UUID field for verification token
- `created_at`: Creation timestamp
- `verified_at`: Verification timestamp (null until verified)
- `is_verified`: Boolean verification status
- `is_expired()`: Method to check if token expired (24 hours)
- `verify()`: Method to mark verification as complete and activate user

### PasswordReset Model
- `user`: ForeignKey to Django User model (allows multiple reset tokens per user)
- `token`: UUID field for reset token
- `created_at`: Creation timestamp
- `used_at`: Timestamp when token was used (null until used)
- `is_used`: Boolean status indicating if token has been used
- `is_expired()`: Method to check if token expired (1 hour)
- `mark_as_used()`: Method to mark token as used

## Integration with Existing Authentication

The signup system works alongside the existing `ninja_jwt` authentication. Once a user is verified, they can use the existing JWT login endpoints to authenticate.

## Testing

To test the signup flow:

1. **Register a new user:**
   ```bash
   curl -X POST http://localhost:8000/api/v1/auth/signup \
     -H "Content-Type: application/json" \
     -d '{
       "username": "testuser",
       "email": "test@example.com",
       "password": "securepass123",
       "first_name": "Test",
       "last_name": "User"
     }'
   ```

2. **Check console for verification email** (development mode)

3. **Verify email using token from email:**
   ```bash
   curl -X GET http://localhost:8000/api/v1/auth/verify/{token}
   ```

4. **Login using existing JWT endpoints** (user is now active)

### Password Reset Flow

1. **Request password reset:**
   ```bash
   curl -X POST http://localhost:8000/api/v1/auth/password-reset/request \
     -H "Content-Type: application/json" \
     -d '{
       "email": "test@example.com"
     }'
   ```

2. **Check console for password reset email** (development mode)

3. **Reset password using token from email:**
   ```bash
   curl -X POST http://localhost:8000/api/v1/auth/password-reset/confirm \
     -H "Content-Type: application/json" \
     -d '{
       "token": "12345678-1234-1234-1234-123456789abc",
       "new_password": "mynewsecurepassword123"
     }'
   ```

4. **Login with new password using existing JWT endpoints**