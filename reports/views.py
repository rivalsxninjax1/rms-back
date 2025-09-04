from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from django.db.models import Count, Sum, Avg, Q, F
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework import mixins, viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from orders.models import Order, OrderItem
from menu.models import MenuItem, MenuCategory
from .models import DailySales, ShiftReport, AuditLog
from .serializers import DailySalesSerializer, ShiftReportSerializer, AuditLogSerializer, CoreAuditLogSerializer
from core.models import AuditLog as CoreAuditLog


class DailySalesViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    Read-only API for daily sales aggregates (admin-only).
    """
    queryset = DailySales.objects.all()
    serializer_class = DailySalesSerializer
    permission_classes = [IsAdminUser]
    filterset_fields = ["date"]
    ordering = ["-date", "-id"]

    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    def payments(self, request):
        """
        Aggregate daily captured payments grouped by date and method.
        Includes totals and sums of tips/discounts from engagement.OrderExtras.
        Query params: date_from, date_to (YYYY-MM-DD)
        """
        try:
            from billing.models import Payment
        except Exception:
            return Response({'detail': 'Billing app not available'}, status=501)

        qs = Payment.objects.filter(status='captured')
        df = request.query_params.get('date_from')
        dt = request.query_params.get('date_to')
        from datetime import datetime as _dt
        try:
            if df:
                qs = qs.filter(created_at__date__gte=_dt.fromisoformat(df).date())
            if dt:
                qs = qs.filter(created_at__date__lte=_dt.fromisoformat(dt).date())
        except Exception:
            pass

        # Join to OrderExtras for tip/coupon/loyalty aggregates
        agg = (
            qs.annotate(day=TruncDate('created_at'))
              .values('day', 'method')
              .annotate(
                  total=Sum('amount'),
                  count=Count('id'),
                  tip=Sum('order__extras__amount', filter=Q(order__extras__name='tip')),
                  coupon=Sum('order__extras__amount', filter=Q(order__extras__name='coupon_discount')),
                  loyalty=Sum('order__extras__amount', filter=Q(order__extras__name='loyalty_discount')),
              )
              .order_by('day', 'method')
        )
        # Normalize nulls to 0 for numeric fields
        results = []
        for row in agg:
            row = dict(row)
            for k in ('total','tip','coupon','loyalty'):
                row[k] = row.get(k) or 0
            results.append(row)
        return Response({'results': results})

    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    def export_csv(self, request):
        """Export daily sales between date_from and date_to (YYYY-MM-DD)."""
        df = request.query_params.get('date_from')
        dt = request.query_params.get('date_to')
        qs = self.get_queryset()
        from datetime import datetime as _dt
        try:
            if df:
                qs = qs.filter(date__gte=_dt.fromisoformat(df).date())
            if dt:
                qs = qs.filter(date__lte=_dt.fromisoformat(dt).date())
        except Exception:
            pass
        import io, csv
        sio = io.StringIO()
        w = csv.writer(sio)
        w.writerow(['date','total_orders','subtotal_cents','tip_cents','discount_cents','total_cents'])
        for r in qs.order_by('date'):
            w.writerow([r.date, r.total_orders, r.subtotal_cents, r.tip_cents, r.discount_cents, r.total_cents])
        from django.http import HttpResponse
        resp = HttpResponse(sio.getvalue(), content_type='text/csv')
        resp['Content-Disposition'] = 'attachment; filename="daily_sales.csv"'
        return resp


class ShiftReportViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    Read-only API for shift reports (admin-only).
    """
    queryset = ShiftReport.objects.all()
    serializer_class = ShiftReportSerializer
    permission_classes = [IsAdminUser]
    filterset_fields = ["date", "shift"]
    ordering = ["-date", "shift", "-id"]

    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def open(self, request):
        """Open a shift. Body: {date: YYYY-MM-DD, shift: code, staff, cash_open_cents} """
        body = request.data or {}
        date = (body.get('date') or str(timezone.now().date()))
        shift = (body.get('shift') or 'evening')
        staff = (body.get('staff') or '')
        try:
            cash_open = int(body.get('cash_open_cents') or 0)
        except Exception:
            cash_open = 0
        obj, _ = ShiftReport.objects.get_or_create(date=date, shift=shift, defaults={'staff': staff})
        obj.staff = staff or obj.staff
        obj.cash_open_cents = cash_open
        obj.opened_at = timezone.now()
        obj.save(update_fields=['staff','cash_open_cents','opened_at'])
        return Response({'ok': True, 'id': obj.id})

    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def close(self, request):
        """Close a shift. Body: {date, shift, cash_close_cents, cash_sales_cents, notes?} """
        body = request.data or {}
        date = (body.get('date') or str(timezone.now().date()))
        shift = (body.get('shift') or 'evening')
        obj = ShiftReport.objects.filter(date=date, shift=shift).first()
        if not obj:
            return Response({'detail': 'Shift not found'}, status=status.HTTP_404_NOT_FOUND)
        try:
            obj.cash_close_cents = int(body.get('cash_close_cents') or 0)
            obj.cash_sales_cents = int(body.get('cash_sales_cents') or 0)
        except Exception:
            return Response({'detail': 'Invalid cash values'}, status=400)
        obj.closed_at = timezone.now()
        obj.over_short_cents = int(obj.cash_close_cents) - int(obj.cash_open_cents) - int(obj.cash_sales_cents)
        if body.get('notes'):
            obj.notes = str(body.get('notes'))
        obj.save(update_fields=['cash_close_cents','cash_sales_cents','closed_at','over_short_cents','notes'])
        return Response({'ok': True, 'id': obj.id, 'over_short_cents': obj.over_short_cents})

    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    def export_csv(self, request):
        """Export shift reports with optional filters: date_from, date_to, shift."""
        df = request.query_params.get('date_from')
        dt = request.query_params.get('date_to')
        sh = request.query_params.get('shift')
        qs = self.get_queryset()
        from datetime import datetime as _dt
        try:
            if df:
                qs = qs.filter(date__gte=_dt.fromisoformat(df).date())
            if dt:
                qs = qs.filter(date__lte=_dt.fromisoformat(dt).date())
        except Exception:
            pass
        if sh:
            qs = qs.filter(shift=sh)
        import io, csv
        sio = io.StringIO()
        w = csv.writer(sio)
        w.writerow(['date','shift','staff','orders_count','total_cents','cash_open_cents','cash_close_cents','cash_sales_cents','over_short_cents','opened_at','closed_at','notes'])
        for r in qs.order_by('date','shift'):
            w.writerow([r.date, r.shift, r.staff, r.orders_count, r.total_cents, r.cash_open_cents, r.cash_close_cents, r.cash_sales_cents, r.over_short_cents, r.opened_at, r.closed_at, r.notes])
        from django.http import HttpResponse
        resp = HttpResponse(sio.getvalue(), content_type='text/csv')
        resp['Content-Disposition'] = 'attachment; filename="shift_reports.csv"'
        return resp


class OrderAnalyticsViewSet(viewsets.GenericViewSet):
    """
    Comprehensive order analytics for admin dashboard.
    """
    permission_classes = [IsAdminUser]
    
    @action(detail=False, methods=['get'])
    def overview(self, request):
        """
        Get overall order statistics and KPIs.
        """
        # Date range filtering
        days = int(request.query_params.get('days', 30))
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        orders_qs = Order.objects.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )
        
        # Basic metrics
        total_orders = orders_qs.count()
        completed_orders = orders_qs.filter(status=Order.STATUS_COMPLETED).count()
        cancelled_orders = orders_qs.filter(status=Order.STATUS_CANCELLED).count()
        
        # Revenue metrics
        revenue_data = orders_qs.filter(
            status__in=[Order.STATUS_COMPLETED, Order.STATUS_PAID]
        ).aggregate(
            total_revenue=Sum('total_amount'),
            avg_order_value=Avg('total_amount'),
            total_tips=Sum('tip_amount'),
            total_tax=Sum('tax_amount')
        )
        
        # Order status breakdown
        status_breakdown = orders_qs.values('status').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Service type breakdown
        service_breakdown = orders_qs.values(
            'service_type__name'
        ).annotate(
            count=Count('id'),
            revenue=Sum('total_amount')
        ).order_by('-revenue')
        
        return Response({
            'period': {
                'start_date': start_date,
                'end_date': end_date,
                'days': days
            },
            'orders': {
                'total': total_orders,
                'completed': completed_orders,
                'cancelled': cancelled_orders,
                'completion_rate': round((completed_orders / total_orders * 100) if total_orders > 0 else 0, 2)
            },
            'revenue': {
                'total': revenue_data['total_revenue'] or Decimal('0.00'),
                'average_order_value': revenue_data['avg_order_value'] or Decimal('0.00'),
                'total_tips': revenue_data['total_tips'] or Decimal('0.00'),
                'total_tax': revenue_data['total_tax'] or Decimal('0.00')
            },
            'status_breakdown': list(status_breakdown),
            'service_breakdown': list(service_breakdown)
        })
    
    @action(detail=False, methods=['get'])
    def revenue_trends(self, request):
        """
        Get daily revenue trends for charting.
        """
        days = int(request.query_params.get('days', 30))
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        daily_revenue = Order.objects.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
            status__in=[Order.STATUS_COMPLETED, Order.STATUS_PAID]
        ).extra(
            select={'day': 'date(created_at)'}
        ).values('day').annotate(
            revenue=Sum('total_amount'),
            orders=Count('id'),
            avg_order_value=Avg('total_amount')
        ).order_by('day')
        
        return Response({
            'period': {
                'start_date': start_date,
                'end_date': end_date,
                'days': days
            },
            'daily_data': list(daily_revenue)
        })
    
    @action(detail=False, methods=['get'])
    def customer_insights(self, request):
        """
        Get customer behavior analytics.
        """
        days = int(request.query_params.get('days', 30))
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        orders_qs = Order.objects.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )
        
        # Customer type breakdown
        customer_types = {
            'registered': orders_qs.filter(user__isnull=False).count(),
            'guest': orders_qs.filter(user__isnull=True).count()
        }
        
        # Repeat customers (registered users with multiple orders)
        repeat_customers = orders_qs.filter(
            user__isnull=False
        ).values('user').annotate(
            order_count=Count('id')
        ).filter(order_count__gt=1).count()
        
        # Average order frequency for registered users
        registered_users_orders = orders_qs.filter(
            user__isnull=False
        ).values('user').annotate(
            order_count=Count('id'),
            total_spent=Sum('total_amount')
        )
        
        # Top customers by spending
        top_customers = registered_users_orders.order_by('-total_spent')[:10]
        
        return Response({
            'period': {
                'start_date': start_date,
                'end_date': end_date,
                'days': days
            },
            'customer_types': customer_types,
            'repeat_customers': repeat_customers,
            'top_customers': list(top_customers)
        })


class MenuAnalyticsViewSet(viewsets.GenericViewSet):
    """
    Menu performance analytics for admin dashboard.
    """
    permission_classes = [IsAdminUser]
    
    @action(detail=False, methods=['get'])
    def item_performance(self, request):
        """
        Get menu item performance metrics.
        """
        days = int(request.query_params.get('days', 30))
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        # Top selling items
        top_items = OrderItem.objects.filter(
            order__created_at__date__gte=start_date,
            order__created_at__date__lte=end_date,
            order__status__in=[Order.STATUS_COMPLETED, Order.STATUS_PAID]
        ).values(
            'menu_item__name',
            'menu_item__id'
        ).annotate(
            total_quantity=Sum('quantity'),
            total_revenue=Sum('line_total'),
            order_count=Count('order', distinct=True)
        ).order_by('-total_quantity')[:20]
        
        # Category performance
        category_performance = OrderItem.objects.filter(
            order__created_at__date__gte=start_date,
            order__created_at__date__lte=end_date,
            order__status__in=[Order.STATUS_COMPLETED, Order.STATUS_PAID]
        ).values(
            'menu_item__category__name'
        ).annotate(
            total_quantity=Sum('quantity'),
            total_revenue=Sum('line_total'),
            unique_items=Count('menu_item', distinct=True)
        ).order_by('-total_revenue')
        
        # Items with no sales
        items_with_sales = OrderItem.objects.filter(
            order__created_at__date__gte=start_date,
            order__created_at__date__lte=end_date
        ).values_list('menu_item__id', flat=True).distinct()
        
        items_no_sales = MenuItem.objects.filter(
            is_available=True
        ).exclude(
            id__in=items_with_sales
        ).values('id', 'name', 'category__name', 'price')
        
        return Response({
            'period': {
                'start_date': start_date,
                'end_date': end_date,
                'days': days
            },
            'top_items': list(top_items),
            'category_performance': list(category_performance),
            'items_no_sales': list(items_no_sales)
        })
    
    @action(detail=False, methods=['get'])
    def pricing_analysis(self, request):
        """
        Analyze menu pricing and profitability.
        """
        days = int(request.query_params.get('days', 30))
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        # Price range analysis
        price_ranges = [
            {'min': 0, 'max': 10, 'label': '$0-$10'},
            {'min': 10, 'max': 20, 'label': '$10-$20'},
            {'min': 20, 'max': 30, 'label': '$20-$30'},
            {'min': 30, 'max': 50, 'label': '$30-$50'},
            {'min': 50, 'max': 999, 'label': '$50+'}
        ]
        
        price_analysis = []
        for price_range in price_ranges:
            items_in_range = OrderItem.objects.filter(
                order__created_at__date__gte=start_date,
                order__created_at__date__lte=end_date,
                order__status__in=[Order.STATUS_COMPLETED, Order.STATUS_PAID],
                unit_price__gte=price_range['min'],
                unit_price__lt=price_range['max']
            ).aggregate(
                total_quantity=Sum('quantity'),
                total_revenue=Sum('line_total'),
                avg_price=Avg('unit_price')
            )
            
            price_analysis.append({
                'range': price_range['label'],
                'total_quantity': items_in_range['total_quantity'] or 0,
                'total_revenue': items_in_range['total_revenue'] or Decimal('0.00'),
                'avg_price': items_in_range['avg_price'] or Decimal('0.00')
            })
        
        return Response({
            'period': {
                'start_date': start_date,
                'end_date': end_date,
                'days': days
            },
            'price_analysis': price_analysis
        })


class AuditLogViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    Admin-only audit log for tracking system changes and user actions.
    """
    queryset = AuditLog.objects.all().select_related('user', 'content_type').order_by('-created_at')
    serializer_class = AuditLogSerializer
    permission_classes = [IsAdminUser]
    filterset_fields = ['action', 'severity', 'category', 'user']
    search_fields = ['description', 'object_repr', 'user__username']
    ordering = ['-created_at']
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """
        Get audit log summary statistics.
        """
        # Actions by type
        actions_by_type = (
            AuditLog.objects
            .values('action')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        
        # Actions by severity
        actions_by_severity = (
            AuditLog.objects
            .values('severity')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        
        # Most active users
        most_active_users = (
            AuditLog.objects
            .values('user__username', 'user__email')
            .annotate(action_count=Count('id'))
            .order_by('-action_count')[:10]
        )
        
        # Recent activity (last 24 hours)
        twenty_four_hours_ago = timezone.now() - timedelta(hours=24)
        recent_activity_count = AuditLog.objects.filter(
            created_at__gte=twenty_four_hours_ago
        ).count()
        
        return Response({
            'actions_by_type': list(actions_by_type),
            'actions_by_severity': list(actions_by_severity),
            'most_active_users': list(most_active_users),
            'recent_activity_count': recent_activity_count
        })


class CoreAuditLogViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    Read-only API for core audit logs tracking Orders, Reservations, and Payments changes.
    Admin-only access.
    """
    queryset = CoreAuditLog.objects.all().select_related('by_user').order_by('-at')
    serializer_class = CoreAuditLogSerializer
    permission_classes = [IsAdminUser]
    filterset_fields = ['model_name', 'action', 'by_user']
    search_fields = ['model_name', 'object_id', 'by_user__username']
    ordering = ['-at']
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """
        Get audit log summary statistics for core models.
        """
        # Actions by model
        actions_by_model = (
            CoreAuditLog.objects
            .values('model_name')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        
        # Actions by type
        actions_by_type = (
            CoreAuditLog.objects
            .values('action')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        
        # Most active users
        most_active_users = (
            CoreAuditLog.objects
            .values('by_user__username', 'by_user__email')
            .annotate(action_count=Count('id'))
            .order_by('-action_count')[:10]
        )
        
        # Recent activity (last 24 hours)
        twenty_four_hours_ago = timezone.now() - timedelta(hours=24)
        recent_activity_count = CoreAuditLog.objects.filter(
            at__gte=twenty_four_hours_ago
        ).count()
        
        return Response({
            'actions_by_model': list(actions_by_model),
            'actions_by_type': list(actions_by_type),
            'most_active_users': list(most_active_users),
            'recent_activity_count': recent_activity_count
        })
