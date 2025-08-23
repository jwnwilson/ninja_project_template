"""
Pytest configuration and fixtures for the {{project_slug}}_be project.
"""

import os
import uuid
from unittest.mock import patch

import django
import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.core import mail
from django.test import RequestFactory


def django_db_setup(worker_id):
    """
    Configure the test database for parallel execution.
    Each worker gets its own database to avoid conflicts.
    """
    if worker_id == "master":
        # Single process run
        db_name = ":memory:"
    else:
        # Parallel run - each worker gets its own file-based database
        db_name = f"test_db_{worker_id}.sqlite3"

    settings.DATABASES["default"] = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": db_name,
        "ATOMIC_REQUESTS": False,
    }
    django.setup()

    # Cleanup after session
    yield

    # Remove temporary database files (only for parallel workers)
    if worker_id != "master" and os.path.exists(db_name):
        try:
            os.remove(db_name)
        except OSError:
            pass  # File might already be cleaned up


@pytest.fixture
def user_factory():
    """
    Factory for creating test users.
    """
    created_users = []

    def _create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
        is_active=True,
        **kwargs,
    ):
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            is_active=is_active,
            **kwargs,
        )
        created_users.append(user)
        return user

    yield _create_user

    # Cleanup
    for user in created_users:
        try:
            user.delete()
        except ValueError as err:
            if (
                "User object can't be deleted because its id attribute is set to None"
                in str(err)
            ):
                # User is already deleted
                pass


@pytest.fixture
def api_request_factory():
    """
    Factory for creating API requests.
    """
    return RequestFactory()


@pytest.fixture
def sample_user_data():
    """
    Sample user registration data.
    """
    return {
        "username": "newuser",
        "email": "newuser@example.com",
        "password": "securepass123",
        "first_name": "New",
        "last_name": "User",
    }


@pytest.fixture
def mailbox():
    """
    Access to the test mailbox.
    """
    # Clear any existing emails
    mail.outbox.clear()
    return mail.outbox


@pytest.fixture
def mock_send_mail():
    """
    Mock email sending for testing.
    """
    with patch("django.core.mail.send_mail") as mock:
        yield mock


@pytest.fixture
def uuid_token():
    """
    Generate a UUID token for testing.
    """
    return str(uuid.uuid4())


@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    """
    Allow database access for all tests.
    """
    pass


@pytest.fixture
def client(django_db_setup):
    """
    Django test client.
    """
    from django.test import Client

    return Client()


@pytest.fixture
def api_client(django_db_setup):
    """
    API test client with JSON support.
    """
    from django.test import Client

    class APIClient(Client):
        def post_json(self, path, data=None, **extra):
            """Post JSON data."""
            return self.post(path, data=data, content_type="application/json", **extra)

        def put_json(self, path, data=None, **extra):
            """Put JSON data."""
            return self.put(path, data=data, content_type="application/json", **extra)

    return APIClient()


@pytest.fixture
def authenticated_user(user_factory):
    """
    Create an authenticated user for testing.
    """
    return user_factory(
        username="authuser",
        email="auth@example.com",
        password="authpass123",
        is_active=True,
    )


@pytest.fixture
def inactive_user(user_factory):
    """
    Create an inactive user for testing.
    """
    return user_factory(
        username="inactiveuser",
        email="inactive@example.com",
        password="inactivepass123",
        is_active=False,
    )
