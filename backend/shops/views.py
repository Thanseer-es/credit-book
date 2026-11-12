
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from .models import Shop
from .serializers import ShopSerializer


class ShopAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        try:
            shop = Shop.objects.get(owner=request.user)
        except Shop.DoesNotExist:
            return Response(
                {"message": "Shop profile not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = ShopSerializer(shop)

        return Response(serializer.data)

    def post(self, request):

        if Shop.objects.filter(owner=request.user).exists():
            return Response(
                {"message": "You already have a shop profile."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = ShopSerializer(data=request.data)

        if serializer.is_valid():

            shop = serializer.save(owner=request.user)

            return Response(
                ShopSerializer(shop).data,
                status=status.HTTP_201_CREATED
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )

    def put(self, request):

        try:
            shop = Shop.objects.get(owner=request.user)
        except Shop.DoesNotExist:
            return Response(
                {"message": "Shop profile not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = ShopSerializer(
            shop,
            data=request.data
        )

        if serializer.is_valid():

            serializer.save()

            return Response(serializer.data)

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )

    def patch(self, request):

        try:
            shop = Shop.objects.get(owner=request.user)
        except Shop.DoesNotExist:
            return Response(
                {"message": "Shop profile not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = ShopSerializer(
            shop,
            data=request.data,
            partial=True
        )

        if serializer.is_valid():

            serializer.save()

            return Response(serializer.data)

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )
