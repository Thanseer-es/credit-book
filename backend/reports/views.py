
from decimal import Decimal

from django.db.models import (
    Sum, Q, Count, F, Value, DecimalField
)
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from datetime import timedelta
from django.utils.dateparse import parse_date

from shops.models import Shop
from customers.models import Customer
from transactions.models import LedgerTransaction


class DashboardAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        # Get the logged-in shopkeeper's shop.
        shop = get_object_or_404(
            Shop,
            owner=request.user
        )

        # Get all transactions belonging to this shop.
        transactions = LedgerTransaction.objects.filter(
            shop=shop
        )

        # Calculate overall credit and payment totals.
        totals = transactions.aggregate(
            total_credit=Sum(
                'amount',
                filter=Q(transaction_type='CREDIT')
            ),
            total_payments=Sum(
                'amount',
                filter=Q(transaction_type='PAYMENT')
            )
        )

        total_credit = totals['total_credit'] or Decimal('0.00')

        total_payments = totals['total_payments'] or Decimal('0.00')

        outstanding_balance = total_credit - total_payments

        # Count active customers belonging to this shop.
        active_customers = Customer.objects.filter(
            shop=shop,
            is_active=True
        ).count()

        # Today's transaction totals.
        today = timezone.localdate()

        today_totals = transactions.filter(
            created_at__date=today
        ).aggregate(
            today_credit=Sum(
                'amount',
                filter=Q(transaction_type='CREDIT')
            ),
            today_payments=Sum(
                'amount',
                filter=Q(transaction_type='PAYMENT')
            )
        )

        today_credit = (
            today_totals['today_credit'] or Decimal('0.00')
        )

        today_payments = (
            today_totals['today_payments'] or Decimal('0.00')
        )

        return Response({

            'shop_name': shop.shop_name,

            'overview': {
                'total_credit': total_credit,
                'total_payments': total_payments,
                'outstanding_balance': outstanding_balance,
                'active_customers': active_customers,
                'total_transactions': transactions.count()
            },

            'today': {
                'date': today,
                'credit': today_credit,
                'payments': today_payments
            }

        })
        

class CustomerOutstandingAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        shop = get_object_or_404(
            Shop,
            owner=request.user
        )

        customers = Customer.objects.filter(
            shop=shop,
            is_active=True
        ).annotate(

            credit_total=Coalesce(
                Sum(
                    'transactions__amount',
                    filter=Q(
                        transactions__transaction_type='CREDIT'
                    )
                ),
                Value(Decimal('0.00')),
                output_field=DecimalField(
                    max_digits=12,
                    decimal_places=2
                )
            ),

            payment_total=Coalesce(
                Sum(
                    'transactions__amount',
                    filter=Q(
                        transactions__transaction_type='PAYMENT'
                    )
                ),
                Value(Decimal('0.00')),
                output_field=DecimalField(
                    max_digits=12,
                    decimal_places=2
                )
            )

        ).annotate(

            outstanding_balance=(
                F('credit_total') - F('payment_total')
            )

        ).filter(
            outstanding_balance__gt=0
        ).order_by(
            '-outstanding_balance'
        )

        results = []

        for customer in customers:

            results.append({

                'customer_id': str(customer.id),

                'customer_name': customer.name,

                'phone': customer.phone,

                'credit_total': customer.credit_total,

                'payment_total': customer.payment_total,

                'outstanding_balance': customer.outstanding_balance

            })

        return Response({

            'total_customers_with_pending_balance': len(results),

            'customers': results

        })
        

class TransactionSummaryAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        shop = get_object_or_404(
            Shop,
            owner=request.user
        )

        today = timezone.localdate()

        # Read date filters.
        start_value = request.query_params.get('start_date')
        end_value = request.query_params.get('end_date')

        period = request.query_params.get('period', 'daily')

        # Custom date range takes priority.
        if start_value or end_value:

            if not start_value or not end_value:
                return Response(
                    {
                        'detail': (
                            'Both start_date and end_date are required.'
                        )
                    },
                    status=400
                )

            start_date = parse_date(start_value)
            end_date = parse_date(end_value)

            if not start_date or not end_date:
                return Response(
                    {
                        'detail': (
                            'Dates must use YYYY-MM-DD format.'
                        )
                    },
                    status=400
                )

            if start_date > end_date:
                return Response(
                    {
                        'detail': (
                            'start_date cannot be after end_date.'
                        )
                    },
                    status=400
                )

            report_type = 'custom'

        else:

            # Daily report.
            if period == 'daily':

                start_date = today
                end_date = today

            # Weekly report (Monday to today).
            elif period == 'weekly':

                start_date = today - timedelta(
                    days=today.weekday()
                )

                end_date = today

            # Monthly report (first day to today).
            elif period == 'monthly':

                start_date = today.replace(day=1)
                end_date = today

            else:

                return Response(
                    {
                        'detail': (
                            'Invalid period. Choose daily, weekly or monthly.'
                        )
                    },
                    status=400
                )

            report_type = period

        # Filter transactions for this shop and date range.
        transactions = LedgerTransaction.objects.filter(
            shop=shop,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )

        # Calculate totals.
        totals = transactions.aggregate(

            total_credit=Sum(
                'amount',
                filter=Q(transaction_type='CREDIT')
            ),

            total_payments=Sum(
                'amount',
                filter=Q(transaction_type='PAYMENT')
            )

        )

        credit = totals['total_credit'] or Decimal('0.00')

        payments = totals['total_payments'] or Decimal('0.00')

        net_change = credit - payments

        return Response({

            'report_type': report_type,

            'start_date': start_date,

            'end_date': end_date,

            'summary': {

                'total_credit': credit,

                'total_payments': payments,

                'net_outstanding_change': net_change,

                'total_transactions': transactions.count()

            }

        })



class TopCustomersAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        shop = get_object_or_404(
            Shop,
            owner=request.user
        )

        # Read the requested limit.
        limit_value = request.query_params.get('limit', '5')

        try:
            limit = int(limit_value)

            if limit < 1 or limit > 100:
                raise ValueError

        except (ValueError, TypeError):
            return Response(
                {
                    'detail': 'Limit must be a number between 1 and 100.'
                },
                status=400
            )

        customers = Customer.objects.filter(
            shop=shop,
            is_active=True
        ).annotate(

            credit_total=Coalesce(
                Sum(
                    'transactions__amount',
                    filter=Q(
                        transactions__transaction_type='CREDIT'
                    )
                ),
                Value(Decimal('0.00')),
                output_field=DecimalField(
                    max_digits=12,
                    decimal_places=2
                )
            ),

            payment_total=Coalesce(
                Sum(
                    'transactions__amount',
                    filter=Q(
                        transactions__transaction_type='PAYMENT'
                    )
                ),
                Value(Decimal('0.00')),
                output_field=DecimalField(
                    max_digits=12,
                    decimal_places=2
                )
            )

        ).annotate(

            outstanding_balance=(
                F('credit_total') - F('payment_total')
            )

        ).filter(
            outstanding_balance__gt=0
        ).order_by(
            '-outstanding_balance',
            'name'
        )[:limit]

        results = []

        for index, customer in enumerate(customers, start=1):

            results.append({

                'rank': index,

                'customer_id': str(customer.id),

                'customer_name': customer.name,

                'phone': customer.phone,

                'credit_total': customer.credit_total,

                'payment_total': customer.payment_total,

                'outstanding_balance': customer.outstanding_balance

            })

        return Response({

            'limit': limit,

            'total_results': len(results),

            'top_customers': results

        })
