
from decimal import Decimal

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
from .serializers import LedgerTransactionSerializer, TransactionReversalSerializer


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
