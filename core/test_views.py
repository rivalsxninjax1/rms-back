from django.http import JsonResponse, Http404
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError
import json


def test_404_error(request):
    """Test view that raises a 404 error"""
    raise Http404("This is a test 404 error")


def test_403_error(request):
    """Test view that raises a 403 error"""
    raise PermissionDenied("This is a test 403 error")


def test_400_error(request):
    """Test view that raises a 400 error"""
    raise ValidationError("This is a test 400 error")


def test_500_error(request):
    """Test view that raises a 500 error"""
    raise Exception("This is a test 500 error")


def test_database_error(request):
    """Test view that raises a database error"""
    raise DatabaseError("This is a test database error")


@csrf_exempt
def test_json_error(request):
    """Test view that returns JSON and raises an error"""
    if request.headers.get('Accept') == 'application/json':
        raise Exception("This is a test JSON error")
    raise Exception("This is a test HTML error")


def test_success(request):
    """Test view that succeeds"""
    return JsonResponse({"message": "Success! Error handling middleware is working."})