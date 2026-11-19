
from decimal import Decimal
import logging

from django.db import IntegrityError, DatabaseError
from django.db import transaction
from django.db.models import Sum, Q
from django.shortcuts import get_object_or_404

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework.views import APIView

from shops.models import Shop
from customers.models import Customer
from .models import LedgerTransaction
from .serializers import (
    LedgerTransactionSerializer,
    TransactionReversalSerializer,
    TransactionSyncStatusSerializer
)

logger = logging.getLogger(__name__)

def calculate_customer_balance(shop, customer):

    totals = LedgerTransaction.objects.filter(
        shop=shop,
        customer=customer
    ).aggregate(
        credit_total=Sum(
            'amount',
            filter=Q(transaction_type='CREDIT')
        ),
        payment_total=Sum(
            'amount',
            filter=Q(transaction_type='PAYMENT')
        )
    )

    credit_total = totals['credit_total'] or Decimal('0.00')
    payment_total = totals['payment_total'] or Decimal('0.00')

    balance = credit_total - payment_total

    return {
        'credit_total': credit_total,
        'payment_total': payment_total,
        'balance': balance
    }


class TransactionListCreateAPIView(generics.ListCreateAPIView):

    serializer_class = LedgerTransactionSerializer
    permission_classes = [IsAuthenticated]

    def get_shop(self):

        return get_object_or_404(
            Shop,
            owner=self.request.user
        )

    def get_queryset(self):

        shop = self.get_shop()

        queryset = LedgerTransaction.objects.filter(
            shop=shop
        ).select_related('customer', 'created_by')

        customer_id = self.request.query_params.get('customer')

        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)

        return queryset

    def create(self, request, *args, **kwargs):

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():

            # Lock the shop to safely process concurrent
            # transaction requests for this shop.
            shop = get_object_or_404(
                Shop.objects.select_for_update(),
                owner=request.user
            )

            customer_data = serializer.validated_data['customer']
            client_id = serializer.validated_data['client_transaction_id']

            # Check whether this request was already processed.
            existing = LedgerTransaction.objects.filter(
                shop=shop,
                client_transaction_id=client_id
            ).first()

            if existing:

                same_request = (
                    existing.customer_id == customer_data.pk
                    and existing.transaction_type ==
                    serializer.validated_data['transaction_type']
                    and existing.amount == serializer.validated_data['amount']
                    and existing.description ==
                    serializer.validated_data.get('description', '')
                )

                if not same_request:
                    return Response(
                        {
                            'detail': (
                                'This client transaction ID was '
                                'already used with different details.'
                            )
                        },
                        status=status.HTTP_409_CONFLICT
                    )

                return Response(
                    self.get_serializer(existing).data,
                    status=status.HTTP_200_OK
                )

            # Ensure the customer belongs to this shop.
            customer = Customer.objects.select_for_update().filter(
                pk=customer_data.pk,
                shop=shop,
                is_active=True
            ).first()

            if not customer:
                raise ValidationError({
                    'customer': 'Invalid customer for this shop.'
                })

            transaction_type = serializer.validated_data[
                'transaction_type'
            ]

            amount = serializer.validated_data['amount']

            # Validate payment against outstanding balance.
            if transaction_type == 'PAYMENT':

                balance_data = calculate_customer_balance(
                    shop,
                    customer
                )

                if amount > balance_data['balance']:

                    raise ValidationError({
                        'amount': (
                            f"Payment exceeds outstanding balance "
                            f"of {balance_data['balance']}."
                        )
                    })

            # Save the transaction.
            serializer.save(
                shop=shop,
                customer=customer,
                created_by=request.user
            )

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED
        )


class CustomerBalanceAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request, customer_id):

        shop = get_object_or_404(
            Shop,
            owner=request.user
        )

        customer = get_object_or_404(
            Customer,
            id=customer_id,
            shop=shop
        )

        balance_data = calculate_customer_balance(
            shop,
            customer
        )

        return Response({
            'customer_id': str(customer.id),
            'customer_name': customer.name,
            'credit_total': balance_data['credit_total'],
            'payment_total': balance_data['payment_total'],
            'outstanding_balance': balance_data['balance']
        })


class TransactionReversalAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request, transaction_id):

        serializer = TransactionReversalSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        client_id = serializer.validated_data[
            'client_transaction_id'
        ]

        description = serializer.validated_data.get(
            'description', ''
        )

        with transaction.atomic():

            shop = get_object_or_404(
                Shop.objects.select_for_update(),
                owner=request.user
            )

            original = get_object_or_404(
                LedgerTransaction.objects.select_for_update(),
                id=transaction_id,
                shop=shop
            )

            # A reversal cannot itself be reversed.
            if original.reversal_of_id is not None:
                raise ValidationError({
                    'detail': 'A reversal transaction cannot be reversed.'
                })

            # Determine the opposite transaction type.
            if original.transaction_type == 'CREDIT':
                reverse_type = 'PAYMENT'
            else:
                reverse_type = 'CREDIT'

            # Handle repeated requests safely.
            existing_request = LedgerTransaction.objects.filter(
                shop=shop,
                client_transaction_id=client_id
            ).first()

            if existing_request:

                if (
                    existing_request.reversal_of_id == original.id
                    and existing_request.transaction_type == reverse_type
                    and existing_request.amount == original.amount
                ):
                    return Response(
                        LedgerTransactionSerializer(
                            existing_request
                        ).data,
                        status=status.HTTP_200_OK
                    )

                return Response(
                    {
                        'detail': (
                            'This client transaction ID '
                            'has already been used.'
                        )
                    },
                    status=status.HTTP_409_CONFLICT
                )

            # Check whether the original was already reversed.
            already_reversed = LedgerTransaction.objects.filter(
                reversal_of=original
            ).exists()

            if already_reversed:
                raise ValidationError({
                    'detail': 'This transaction has already been reversed.'
                })

            customer = Customer.objects.select_for_update().filter(
                id=original.customer_id,
                shop=shop
            ).first()

            if not customer:
                raise ValidationError({
                    'detail': 'Customer not found.'
                })

            # Reversing a credit creates a payment.
            # It cannot exceed the current outstanding balance.
            if reverse_type == 'PAYMENT':

                balance_data = calculate_customer_balance(
                    shop,
                    customer
                )

                if original.amount > balance_data['balance']:
                    raise ValidationError({
                        'detail': (
                            'Cannot reverse this credit because '
                            'the customer has already paid part '
                            'or all of this amount.'
                        )
                    })

            reversal = LedgerTransaction.objects.create(
                shop=shop,
                customer=customer,
                transaction_type=reverse_type,
                amount=original.amount,
                description=(
                    description
                    or f'Reversal of transaction {original.id}'
                ),
                client_transaction_id=client_id,
                reversal_of=original,
                created_by=request.user
            )

        return Response(
            LedgerTransactionSerializer(reversal).data,
            status=status.HTTP_201_CREATED
        )



class TransactionSyncAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):

        transaction_items = request.data.get('transactions')

        if not isinstance(transaction_items, list):
            return Response(
                {'detail': 'transactions must be a list.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if len(transaction_items) > 50:
            return Response(
                {'detail': 'Maximum 50 transactions per sync request.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        shop = get_object_or_404(
            Shop,
            owner=request.user
        )

        results = []

        synced_count = 0
        duplicate_count = 0
        rejected_count = 0
        conflict_count = 0
        retryable_count = 0

        for index, item in enumerate(transaction_items):

            if not isinstance(item, dict):

                results.append({
                    'index': index,
                    'status': 'rejected',
                    'retryable': False,
                    'detail': 'Transaction must be a JSON object.'
                })

                rejected_count += 1
                continue

            serializer = LedgerTransactionSerializer(data=item)

            if not serializer.is_valid():

                results.append({
                    'index': index,
                    'status': 'rejected',
                    'retryable': False,
                    'errors': serializer.errors
                })

                rejected_count += 1
                continue

            data = serializer.validated_data

            customer_data = data['customer']
            client_id = data['client_transaction_id']
            transaction_type = data['transaction_type']
            amount = data['amount']
            description = data.get('description', '')

            try:

                result = None

                with transaction.atomic():

                    locked_shop = Shop.objects.select_for_update().get(
                        id=shop.id
                    )

                    existing = LedgerTransaction.objects.filter(
                        shop=locked_shop,
                        client_transaction_id=client_id
                    ).first()

                    if existing:

                        same_request = (
                            existing.customer_id == customer_data.pk
                            and existing.transaction_type == transaction_type
                            and existing.amount == amount
                            and existing.description == description
                        )

                        if same_request:

                            result = {
                                'index': index,
                                'status': 'already_synced',
                                'retryable': False,
                                'transaction_id': str(existing.id)
                            }

                        else:

                            result = {
                                'index': index,
                                'status': 'conflict',
                                'retryable': False,
                                'detail': (
                                    'Client transaction ID was '
                                    'already used with different details.'
                                )
                            }

                    else:

                        customer = Customer.objects.select_for_update().filter(
                            id=customer_data.pk,
                            shop=locked_shop,
                            is_active=True
                        ).first()

                        if not customer:

                            result = {
                                'index': index,
                                'status': 'rejected',
                                'retryable': False,
                                'detail': 'Customer not found or inactive.'
                            }

                        else:

                            if transaction_type == 'PAYMENT':

                                balance_data = calculate_customer_balance(
                                    locked_shop,
                                    customer
                                )

                                if amount > balance_data['balance']:

                                    result = {
                                        'index': index,
                                        'status': 'rejected',
                                        'retryable': False,
                                        'detail': (
                                            'Payment exceeds outstanding balance.'
                                        )
                                    }

                            if result is None:

                                saved_transaction = serializer.save(
                                    shop=locked_shop,
                                    customer=customer,
                                    created_by=request.user
                                )

                                result = {
                                    'index': index,
                                    'status': 'synced',
                                    'retryable': False,
                                    'transaction_id': str(saved_transaction.id)
                                }

                # Count the result only after the database transaction
                # has completed successfully.
                results.append(result)

                if result['status'] == 'synced':
                    synced_count += 1

                elif result['status'] == 'already_synced':
                    duplicate_count += 1

                elif result['status'] == 'conflict':
                    conflict_count += 1

                elif result['status'] == 'rejected':
                    rejected_count += 1

            except IntegrityError:

                # A unique constraint may have been hit by a
                # concurrent request. Check whether it was saved.
                existing = LedgerTransaction.objects.filter(
                    shop=shop,
                    client_transaction_id=client_id
                ).first()

                if existing:

                    same_request = (
                        existing.customer_id == customer_data.pk
                        and existing.transaction_type == transaction_type
                        and existing.amount == amount
                        and existing.description == description
                    )

                    if same_request:

                        results.append({
                            'index': index,
                            'status': 'already_synced',
                            'retryable': False,
                            'transaction_id': str(existing.id)
                        })

                        duplicate_count += 1

                    else:

                        results.append({
                            'index': index,
                            'status': 'conflict',
                            'retryable': False
                        })

                        conflict_count += 1

                else:

                    logger.exception(
                        'Database constraint error during transaction sync.'
                    )

                    results.append({
                        'index': index,
                        'status': 'failed',
                        'retryable': False,
                        'detail': 'Database constraint error.'
                    })

                    rejected_count += 1

            except DatabaseError:

                logger.exception(
                    'Temporary database error during transaction sync.'
                )

                results.append({
                    'index': index,
                    'status': 'failed',
                    'retryable': True,
                    'retry_after_seconds': 5,
                    'detail': 'Temporary database error. Retry later.'
                })

                retryable_count += 1

        return Response({

            'message': 'Synchronization completed.',

            'summary': {
                'total': len(transaction_items),
                'synced': synced_count,
                'already_synced': duplicate_count,
                'rejected': rejected_count,
                'conflicts': conflict_count,
                'retryable': retryable_count
            },

            'results': results

        }, status=status.HTTP_200_OK)


class TransactionSyncStatusAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):

        serializer = TransactionSyncStatusSerializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)

        client_ids = serializer.validated_data[
            'client_transaction_ids'
        ]

        shop = get_object_or_404(
            Shop,
            owner=request.user
        )

        # Only retrieve transactions belonging to this shop.
        existing_transactions = LedgerTransaction.objects.filter(
            shop=shop,
            client_transaction_id__in=client_ids
        ).select_related('customer')

        # Build a lookup using the client-generated IDs.
        transaction_map = {
            str(item.client_transaction_id): item
            for item in existing_transactions
        }

        results = []

        for client_id in client_ids:

            client_id_string = str(client_id)

            existing = transaction_map.get(client_id_string)

            if existing:

                results.append({
                    'client_transaction_id': client_id_string,
                    'status': 'synced',
                    'transaction_id': str(existing.id),
                    'customer_id': str(existing.customer_id),
                    'transaction_type': existing.transaction_type,
                    'amount': existing.amount
                })

            else:

                results.append({
                    'client_transaction_id': client_id_string,
                    'status': 'not_found',
                    'transaction_id': None
                })

        return Response({

            'total': len(results),

            'synced': sum(
                1 for item in results
                if item['status'] == 'synced'
            ),

            'not_found': sum(
                1 for item in results
                if item['status'] == 'not_found'
            ),

            'results': results

        })
