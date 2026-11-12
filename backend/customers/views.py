
from django.shortcuts import get_object_or_404
from django.db import IntegrityError, transaction

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from shops.models import Shop
from .models import Customer
from .serializers import CustomerSerializer


class CustomerListCreateAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get_shop(self, request):
        return get_object_or_404(
            Shop,
            owner=request.user
        )

    def get(self, request):

        shop = self.get_shop(request)

        customers = Customer.objects.filter(shop=shop)

        search = request.query_params.get('search')

        if search:
            customers = customers.filter(
                name__icontains=search
            ) | customers.filter(
                phone__icontains=search
            )

        include_inactive = (
            request.query_params.get('include_inactive') == 'true'
        )

        if not include_inactive:
            customers = customers.filter(is_active=True)

        serializer = CustomerSerializer(
            customers.distinct(),
            many=True
        )

        return Response(serializer.data)

    def post(self, request):

        shop = self.get_shop(request)

        serializer = CustomerSerializer(
            data=request.data,
            context={'shop': shop}
        )

        if serializer.is_valid():

            try:
                with transaction.atomic():
                    customer = serializer.save(shop=shop)

                return Response(
                    CustomerSerializer(customer).data,
                    status=status.HTTP_201_CREATED
                )

            except IntegrityError:
                return Response(
                    {"phone": ["This phone number already exists."]},
                    status=status.HTTP_400_BAD_REQUEST
                )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )


class CustomerDetailAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get_customer(self, request, pk):

        shop = get_object_or_404(
            Shop,
            owner=request.user
        )

        return get_object_or_404(
            Customer,
            pk=pk,
            shop=shop
        )

    def get(self, request, pk):

        customer = self.get_customer(request, pk)

        serializer = CustomerSerializer(customer)

        return Response(serializer.data)

    def put(self, request, pk):

        customer = self.get_customer(request, pk)

        serializer = CustomerSerializer(
            customer,
            data=request.data,
            context={'shop': customer.shop}
        )

        if serializer.is_valid():

            serializer.save()

            return Response(serializer.data)

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )

    def patch(self, request, pk):

        customer = self.get_customer(request, pk)

        serializer = CustomerSerializer(
            customer,
            data=request.data,
            partial=True,
            context={'shop': customer.shop}
        )

        if serializer.is_valid():

            serializer.save()

            return Response(serializer.data)

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )

    def delete(self, request, pk):

        customer = self.get_customer(request, pk)

        customer.is_active = False
        customer.save(update_fields=['is_active', 'updated_at'])

        return Response(
            {"message": "Customer deactivated successfully."},
            status=status.HTTP_200_OK
        )
