from django.urls import path

from .views import (
    TransactionListCreateAPIView,
    CustomerBalanceAPIView,
    TransactionReversalAPIView
)

urlpatterns = [
    path(
        '',
        TransactionListCreateAPIView.as_view(),
        name='transaction-list-create'
    ),

    path(
        'balance/<uuid:customer_id>/',
        CustomerBalanceAPIView.as_view(),
        name='customer-balance'
    ),
    
    path(
    '<uuid:transaction_id>/reverse/',
    TransactionReversalAPIView.as_view(),
    name='transaction-reverse'
),
]