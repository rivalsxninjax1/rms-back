# accounts/serializers.py
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from django.db import transaction

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken

import re
from datetime import datetime, timedelta

User = get_user_model()


class EmailOrUsernameTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Allow login with username OR email."""

    @classmethod
    def get_token(cls, user):
        tok = super().get_token(user)
        tok["username"] = user.get_username()
        tok["email"] = user.email or ""
        return tok

    def validate(self, attrs):
        supplied = (attrs.get("username") or "").strip()
        if "@" in supplied:
            try:
                user = User.objects.get(email__iexact=supplied)
                attrs["username"] = getattr(user, User.USERNAME_FIELD)
            except User.DoesNotExist:
                pass
        else:
            try:
                user = User.objects.get(**{f"{User.USERNAME_FIELD}__iexact": supplied})
                attrs["username"] = getattr(user, User.USERNAME_FIELD)
            except User.DoesNotExist:
                pass

        data = super().validate(attrs)
        data["user"] = {
            "id": self.user.id,
            "username": self.user.get_username(),
            "email": self.user.email or "",
            "first_name": getattr(self.user, "first_name", "") or "",
            "last_name": getattr(self.user, "last_name", "") or "",
        }
        return data


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name", "password")

    def validate_username(self, v):
        if User.objects.filter(username__iexact=v).exists():
            raise serializers.ValidationError("Username already taken.")
        return v

    def validate_email(self, v):
        if v and User.objects.filter(email__iexact=v).exists():
            raise serializers.ValidationError("Email already registered.")
        return v

    def create(self, validated_data):
        pwd = validated_data.pop("password")
        user = User.objects.create_user(**validated_data)
        user.set_password(pwd)
        user.save()
        return user

    def to_representation(self, instance):
        ref = RefreshToken.for_user(instance)
        return {
            "user": {
                "id": instance.id,
                "username": instance.get_username(),
                "email": instance.email or "",
                "first_name": getattr(instance, "first_name", "") or "",
                "last_name": getattr(instance, "last_name", "") or "",
            },
            "access": str(ref.access_token),
            "refresh": str(ref),
        }


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile information."""
    roles = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'date_joined', 'last_login', 'roles')
        read_only_fields = ('id', 'username', 'date_joined', 'last_login', 'roles')
    
    def get_roles(self, obj):
        """Return list of user's group names as roles."""
        try:
            return list(obj.groups.values_list('name', flat=True))
        except Exception:
            return []
    
    def validate_email(self, value):
        if value:
            validate_email(value)
            # Check if email is already taken by another user
            if User.objects.filter(email__iexact=value).exclude(pk=self.instance.pk if self.instance else None).exists():
                raise serializers.ValidationError("This email is already registered.")
        return value


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for changing user password."""
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=8)
    confirm_password = serializers.CharField(required=True)
    
    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value
    
    def validate_new_password(self, value):
        try:
            validate_password(value, self.context['request'].user)
        except ValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value
    
    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError("New passwords don't match.")
        return attrs
    
    def save(self):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user


class PasswordResetRequestSerializer(serializers.Serializer):
    """Serializer for requesting password reset."""
    email = serializers.EmailField(required=True)
    
    def validate_email(self, value):
        if not User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("No user found with this email address.")
        return value


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Serializer for confirming password reset."""
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=8)
    confirm_password = serializers.CharField(required=True)
    
    def validate_new_password(self, value):
        try:
            validate_password(value)
        except ValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value
    
    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError("Passwords don't match.")
        return attrs
