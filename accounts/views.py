from __future__ import annotations

import json
from typing import Any, Dict
from datetime import datetime, timedelta

from django.contrib import auth
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.http import HttpRequest, JsonResponse
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.db import transaction
from django.core.validators import validate_email
from django.contrib.auth.models import Permission

from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authentication import SessionAuthentication

from .serializers import (
    EmailOrUsernameTokenObtainPairSerializer,
    RegisterSerializer,
    UserProfileSerializer,
    ChangePasswordSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
)

User = get_user_model()


# -----------------------------------------------------------------------------
# Authentication classes
# -----------------------------------------------------------------------------

class CsrfExemptSessionAuthentication(SessionAuthentication):
    """SessionAuthentication that bypasses CSRF validation for API endpoints."""
    
    def enforce_csrf(self, request):
        return  # Skip CSRF validation


# -----------------------------------------------------------------------------
# Rate limiting classes
# -----------------------------------------------------------------------------

class LoginRateThrottle(AnonRateThrottle):
    scope = 'login'

class RegisterRateThrottle(AnonRateThrottle):
    scope = 'register'

class PasswordResetRateThrottle(AnonRateThrottle):
    scope = 'password_reset'


# -----------------------------------------------------------------------------
# Session helpers (kept for backward compatibility)
# -----------------------------------------------------------------------------

def _json_body(request: HttpRequest) -> Dict[str, Any]:
    try:
        return json.loads(request.body.decode("utf-8"))
    except Exception:
        return {}


def whoami(request: HttpRequest) -> JsonResponse:
    """
    Lightweight session/CSRF ping used by the storefront JS.
    """
    user = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
    return JsonResponse(
        {
            "ok": True,
            "is_auth": bool(user),
            "user": {"id": user.id, "username": user.get_username()} if user else None,
            "csrf": get_token(request),
        }
    )


# -----------------------------------------------------------------------------
# JWT Authentication Views
# -----------------------------------------------------------------------------

class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Enhanced JWT token obtain view with rate limiting and security features.
    """
    serializer_class = EmailOrUsernameTokenObtainPairSerializer
    authentication_classes = [CsrfExemptSessionAuthentication]
    throttle_classes = [LoginRateThrottle]
    
    def post(self, request, *args, **kwargs):
        # Check for brute force attempts
        client_ip = self.get_client_ip(request)
        cache_key = f"login_attempts_{client_ip}"
        attempts = cache.get(cache_key, 0)
        
        if attempts >= 5:  # Max 5 attempts per IP
            return Response(
                {"detail": "Too many login attempts. Please try again later."},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )
        
        response = super().post(request, *args, **kwargs)
        
        if response.status_code == 200:
            # Reset attempts on successful login
            cache.delete(cache_key)
            # Log successful login
            user = User.objects.get(username=request.data.get('username', ''))
            user.last_login = timezone.now()
            user.save(update_fields=['last_login'])
        else:
            # Increment failed attempts
            cache.set(cache_key, attempts + 1, timeout=900)  # 15 minutes
        
        return response
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class CustomTokenRefreshView(TokenRefreshView):
    """
    Enhanced JWT token refresh view with additional security.
    """
    authentication_classes = [CsrfExemptSessionAuthentication]
    
    def post(self, request, *args, **kwargs):
        try:
            response = super().post(request, *args, **kwargs)
            return response
        except TokenError as e:
            return Response(
                {"detail": "Token is invalid or expired"},
                status=status.HTTP_401_UNAUTHORIZED
            )


class RegisterView(APIView):
    """
    User registration with enhanced validation and security.
    """
    permission_classes = [AllowAny]
    authentication_classes = [CsrfExemptSessionAuthentication]
    throttle_classes = [RegisterRateThrottle]
    
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            with transaction.atomic():
                user = serializer.save()
                return Response(
                    serializer.to_representation(user),
                    status=status.HTTP_201_CREATED
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserProfileView(APIView):
    """
    User profile management.
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [CsrfExemptSessionAuthentication]
    throttle_classes = [UserRateThrottle]
    
    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)
    
    def put(self, request):
        serializer = UserProfileSerializer(
            request.user, 
            data=request.data, 
            partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ChangePasswordView(APIView):
    """
    Change user password with proper validation.
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [CsrfExemptSessionAuthentication]
    throttle_classes = [UserRateThrottle]
    
    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={'request': request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"detail": "Password changed successfully."},
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogoutView(APIView):
    """
    Logout view that blacklists the refresh token.
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [CsrfExemptSessionAuthentication]
    
    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            
            # Also logout from session if exists
            logout(request)
            
            return Response(
                {"detail": "Successfully logged out."},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {"detail": "Error during logout."},
                status=status.HTTP_400_BAD_REQUEST
            )


class PasswordResetRequestView(APIView):
    """
    Request password reset via email.
    """
    permission_classes = [AllowAny]
    authentication_classes = [CsrfExemptSessionAuthentication]
    throttle_classes = [PasswordResetRateThrottle]
    
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            # Here you would typically send an email with reset link
            # For now, we'll just return success
            return Response(
                {"detail": "Password reset email sent if account exists."},
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetConfirmView(APIView):
    """
    Confirm password reset with token.
    """
    permission_classes = [AllowAny]
    authentication_classes = [CsrfExemptSessionAuthentication]
    throttle_classes = [PasswordResetRateThrottle]
    
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        if serializer.is_valid():
            # Here you would validate the token and reset password
            # For now, we'll just return success
            return Response(
                {"detail": "Password reset successful."},
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# -----------------------------------------------------------------------------
# Session Auth JSON endpoints (kept for backward compatibility)
# -----------------------------------------------------------------------------

@method_decorator(csrf_protect, name="dispatch")
class SessionLoginJSON(View):
    """
    POST { "username": "...", "password": "..." }
    Sets Django session cookie on success (HTTPOnly).
    """
    def post(self, request: HttpRequest):
        data = _json_body(request)
        username = (data.get("username") or "").strip()
        password = (data.get("password") or "").strip()
        if not username or not password:
            return JsonResponse({"detail": "Username and password required."}, status=400)

        user = authenticate(request, username=username, password=password)
        if not user:
            return JsonResponse({"detail": "Invalid credentials."}, status=401)

        login(request, user)
        
        # Cart merging is handled automatically by the user_logged_in signal
        # in orders.signals_cart.merge_cart_on_login
        
        return JsonResponse({"ok": True, "user": {"id": user.id, "username": user.get_username()}, "csrf": get_token(request)})


@method_decorator(csrf_protect, name="dispatch")
class RegisterJSON(View):
    """
    POST { "username": "...", "password": "...", "email": "optional" }
    Creates a new user and logs them in.
    """
    def post(self, request: HttpRequest):
        data = _json_body(request)
        username = (data.get("username") or "").strip()
        password = (data.get("password") or "").strip()
        email = (data.get("email") or "").strip()

        if not username or not password:
            return JsonResponse({"detail": "Username and password required."}, status=400)
        if User.objects.filter(username__iexact=username).exists():
            return JsonResponse({"detail": "Username already exists."}, status=400)

        user = User.objects.create_user(username=username, password=password, email=email or None)
        login(request, user)
        
        # Cart merging is handled automatically by the user_logged_in signal
        # in orders.signals_cart.merge_cart_on_login
        
        return JsonResponse({"ok": True, "user": {"id": user.id, "username": user.get_username()}, "csrf": get_token(request)})


@method_decorator(csrf_protect, name="dispatch")
class SessionLogout(View):
    """
    POST {} — logs out the current user.
    """
    def post(self, request: HttpRequest):
        logout(request)
        return JsonResponse({"ok": True})


@require_GET
def MeView(request: HttpRequest):
    """
    GET current session user info.
    """
    if not (getattr(request, "user", None) and request.user.is_authenticated):
        return JsonResponse({"detail": "Not authenticated."}, status=401)
    user = request.user
    return JsonResponse({"id": user.id, "username": user.get_username(), "email": user.email or ""})
