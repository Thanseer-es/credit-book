from django.urls import path

from .views import (
    DashboardAPIView,
    CustomerOutstandingAPIView,
    TransactionSummaryAPIView,
    TopCustomersAPIView
)

urlpatterns = [

    path(
        'dashboard/',
        DashboardAPIView.as_view(),
        name='dashboard'
    ),

    path(
        'customers/outstanding/',
        CustomerOutstandingAPIView.as_view(),
        name='customer-outstanding'
    ),

    path(
        'transactions/summary/',
        TransactionSummaryAPIView.as_view(),
        name='transaction-summary'
    ),
    
    path(
    'customers/top-outstanding/',
    TopCustomersAPIView.as_view(),
    name='top-customers'
    ),

]