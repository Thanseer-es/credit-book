
from django.urls import path

from .views import (
    CustomerListCreateAPIView,
    CustomerDetailAPIView
)


urlpatterns = [
    path(
        '',
        CustomerListCreateAPIView.as_view(),
        name='customer-list-create'
    ),

    path(
        '<uuid:pk>/',
        CustomerDetailAPIView.as_view(),
        name='customer-detail'
    ),
]
