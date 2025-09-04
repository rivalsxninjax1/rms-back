import os
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient


# Ensure development-like environment during tests if not provided externally
os.environ.setdefault("ENVIRONMENT", "development")


@pytest.fixture
def api_client() -> APIClient:
    """Unauthenticated DRF APIClient.

    Use with endpoints that allow anonymous access, or combine with
    force_login/force_authenticate for authenticated flows.
    """
    return APIClient(enforce_csrf_checks=False)


@pytest.fixture
def user(db):
    """A persisted user instance."""
    User = get_user_model()
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="password123!",
    )


@pytest.fixture
def auth_api_client(api_client: APIClient, user):
    """APIClient authenticated as the provided user via force_authenticate."""
    api_client.force_authenticate(user=user)
    return api_client

