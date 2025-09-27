from __future__ import annotations

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from loyalty.models import LoyaltyProfile, LoyaltyRank, LoyaltyPointsLedger
from .api_serializers import LoyaltyProfileSerializer, LoyaltyRankSerializer, LoyaltyPointsLedgerSerializer


class LoyaltyRankViewSet(viewsets.ModelViewSet):
    queryset = LoyaltyRank.objects.all().order_by('sort_order', 'name')
    serializer_class = LoyaltyRankSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active']
    search_fields = ['code', 'name']
    ordering_fields = ['sort_order', 'name']

    def get_permissions(self):
        if self.request.method in ('GET',):
            return [AllowAny()]
        if not (self.request.user and self.request.user.is_authenticated and self.request.user.is_staff):
            self.permission_denied(self.request, message='Staff only')
        return [IsAuthenticated()]


class LoyaltyProfileViewSet(viewsets.ModelViewSet):
    queryset = LoyaltyProfile.objects.select_related('user', 'rank').all().order_by('user__username')
    serializer_class = LoyaltyProfileSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['rank']
    search_fields = ['user__username', 'user__email']
    ordering_fields = ['points']
    ordering = ['-points']

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user and self.request.user.is_staff:
            return qs
        # Non-staff only sees their own profile
        return qs.filter(user=self.request.user)

    @action(detail=True, methods=['post'])
    def adjust(self, request, pk=None):
        """Manual adjustment with reason. Body: {delta:int, reason:str, reference?:str}"""
        profile = self.get_object()
        try:
            delta = int(request.data.get('delta'))
        except Exception:
            return Response({'detail': 'delta is required (int)'}, status=400)
        reason = (request.data.get('reason') or '').strip()
        ref = (request.data.get('reference') or '').strip()
        if not reason:
            return Response({'detail': 'reason is required'}, status=400)
        if not (request.user and request.user.is_staff):
            return Response({'detail': 'Forbidden'}, status=403)
        with transaction.atomic():
            entry = LoyaltyPointsLedger.objects.create(profile=profile, delta=delta, type='ADJUST', reason=reason, reference=ref, created_by=request.user)
            entry.apply()
        try:
            from reports.models import AuditLog
            AuditLog.log_action(request.user, 'UPDATE', f'Adjusted loyalty points by {delta} (reason: {reason})', content_object=profile, request=request, category='loyalty')
        except Exception:
            pass
        return Response({'ok': True, 'profile_id': profile.id, 'new_points': profile.points})

    @action(detail=True, methods=['get'])
    def ledger(self, request, pk=None):
        profile = self.get_object()
        ser = LoyaltyPointsLedgerSerializer(profile.ledger.all()[:200], many=True)
        return Response(ser.data)

    @action(detail=False, methods=['get'])
    def export_csv(self, request):
        if not (request.user and request.user.is_staff):
            return Response({'detail': 'Forbidden'}, status=403)
        import io, csv
        sio = io.StringIO()
        writer = csv.writer(sio)
        writer.writerow(['user_id','user','rank','points'])
        for p in self.get_queryset().select_related('user','rank'):
            writer.writerow([p.user_id, getattr(p.user,'username',''), getattr(p.rank,'name',''), p.points])
        from django.http import HttpResponse
        resp = HttpResponse(sio.getvalue(), content_type='text/csv')
        resp['Content-Disposition'] = 'attachment; filename="loyalty_profiles.csv"'
        return resp


class LoyaltyLedgerViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = LoyaltyPointsLedger.objects.select_related('profile','created_by','profile__user').all().order_by('-created_at')
    serializer_class = LoyaltyPointsLedgerSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['type', 'profile']
    search_fields = ['reason', 'reference', 'profile__user__username']
    ordering_fields = ['created_at']
