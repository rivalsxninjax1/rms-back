# accounts/urls.py
from django.urls import path
from rest_framework_simplejwt.views import TokenVerifyView

from .views import (
    # JWT Authentication Views
    CustomTokenObtainPairView,
    CustomTokenRefreshView,
    RegisterView,
    UserProfileView,
    ChangePasswordView,
    LogoutView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
    # Session-based views (backward compatibility)
    whoami,
    SessionLogout,
    SessionLoginJSON,
    RegisterJSON,
    MeView,
)

app_name = "accounts"

urlpatterns = [
    # JWT Authentication Endpoints (Primary)
    path("api/login/", CustomTokenObtainPairView.as_view(), name="jwt_login"),
    path("api/register/", RegisterView.as_view(), name="jwt_register"),
    path("api/logout/", LogoutView.as_view(), name="jwt_logout"),
    path("api/token/refresh/", CustomTokenRefreshView.as_view(), name="jwt_refresh"),
    path("api/token/verify/", TokenVerifyView.as_view(), name="jwt_verify"),
    
    # User Profile Management
    path("api/profile/", UserProfileView.as_view(), name="user_profile"),
    path("api/change-password/", ChangePasswordView.as_view(), name="change_password"),
    
    # Password Reset
    path("api/password-reset/", PasswordResetRequestView.as_view(), name="password_reset_request"),
    path("api/password-reset/confirm/", PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    
    # Session-based JSON endpoints (Backward Compatibility)
    path("login/", SessionLoginJSON.as_view(), name="login_json"),
    path("register/", RegisterJSON.as_view(), name="register_json"),
    path("logout/", SessionLogout.as_view(), name="logout_json"),
    
    # Session check + profile (Backward Compatibility)
    path("auth/whoami/", whoami, name="whoami"),
    path("me/", MeView, name="me"),
    
    # Legacy JWT endpoints (Backward Compatibility)
    path("token/refresh/", CustomTokenRefreshView.as_view(), name="token_refresh"),
    path("token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("jwt/refresh/", CustomTokenRefreshView.as_view(), name="jwt_refresh_legacy"),
]
