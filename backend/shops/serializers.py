
from rest_framework import serializers
from .models import Shop


class ShopSerializer(serializers.ModelSerializer):

    class Meta:
        model = Shop
        fields = [
            'id',
            'shop_name',
            'address',
            'city',
            'pincode',
            'created_at',
            'updated_at',
        ]

        read_only_fields = [
            'id',
            'created_at',
            'updated_at',
        ]
