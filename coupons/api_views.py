from __future__ import annotations

from decimal import Decimal
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from .models import Coupon
from .api_serializers import CouponSerializer
from .services import compute_discount_for_order


class CouponViewSet(viewsets.ModelViewSet):
    queryset = Coupon.objects.all().order_by('-created_at')
    serializer_class = CouponSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['active', 'discount_type', 'customer_type']
    search_fields = ['code', 'name', 'description', 'phrase']
    ordering_fields = ['created_at', 'updated_at', 'times_used']
    ordering = ['-created_at']

    def get_permissions(self):
        # Public can list/preview; writes require staff
        if self.action in ['list', 'retrieve', 'preview']:
            return [AllowAny()]
        if not (self.request.user and self.request.user.is_authenticated and self.request.user.is_staff):
            self.permission_denied(self.request, message="Staff only")
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        obj = serializer.save(created_by=getattr(self.request, 'user', None))
        try:
            from reports.models import AuditLog
            AuditLog.log_action(self.request.user, 'CREATE', f'Coupon created: {obj.code}', content_object=obj, request=self.request, category='coupons')
        except Exception:
            pass

    def perform_update(self, serializer):
        obj = serializer.save()
        try:
            from reports.models import AuditLog
            AuditLog.log_action(self.request.user, 'UPDATE', f'Coupon updated: {obj.code}', content_object=obj, request=self.request, category='coupons')
        except Exception:
            pass

    def perform_destroy(self, instance):
        try:
            from reports.models import AuditLog
            AuditLog.log_action(self.request.user, 'DELETE', f'Coupon deleted: {instance.code}', content_object=instance, request=self.request, category='coupons')
        except Exception:
            pass
        instance.delete()

    @action(detail=True, methods=['get'])
    def preview(self, request, pk=None):
        """
        Preview discount calculation for a coupon.
        Query params: order_total (decimal), item_count (int), user_id (optional), first (bool)
        """
        coupon = self.get_object()
        try:
            order_total = Decimal(str(request.query_params.get('order_total') or '0'))
        except Exception:
            return Response({'detail': 'Invalid order_total'}, status=400)
        try:
            item_count = int(request.query_params.get('item_count') or '1')
        except Exception:
            item_count = 1
        user = None
        uid = request.query_params.get('user_id')
        if uid:
            try:
                user = get_user_model().objects.get(pk=int(uid))
            except Exception:
                user = None
        is_first = (request.query_params.get('first') or 'false').lower() in ('1','true','yes')

        amount, breakdown = compute_discount_for_order(coupon, order_total, item_count=item_count, user=user, is_first_order=is_first)
        if 'error' in breakdown:
            return Response({'ok': False, 'error': breakdown['error'], 'discount_amount': str(amount)}, status=200)
        return Response({'ok': True, 'discount_amount': str(amount), 'breakdown': breakdown}, status=200)

