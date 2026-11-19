
import re

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

    def validate_shop_name(self, value):

        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Shop name cannot be empty."
            )

        return value

    def validate_pincode(self, value):

        value = value.strip()

        if value and not re.fullmatch(r'\d{6}', value):
            raise serializers.ValidationError(
                "Pincode must contain exactly 6 digits."
            )

        return value

    def validate_city(self, value):

        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "City cannot contain only spaces."
            )

        return value
