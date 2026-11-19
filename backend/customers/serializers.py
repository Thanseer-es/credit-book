
import re

from rest_framework import serializers
from .models import Customer


class CustomerSerializer(serializers.ModelSerializer):

    class Meta:
        model = Customer

        fields = [
            'id',
            'name',
            'phone',
            'address',
            'notes',
            'is_active',
            'created_at',
            'updated_at',
        ]

        read_only_fields = [
            'id',
            'is_active',
            'created_at',
            'updated_at',
        ]

    def validate_name(self, value):

        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Customer name cannot be empty."
            )

        return value

    def validate_phone(self, value):

        value = value.strip()

        # Validate Indian mobile number
        if not re.fullmatch(r'[6-9]\d{9}', value):
            raise serializers.ValidationError(
                "Enter a valid 10-digit Indian mobile number."
            )

        shop = self.context.get('shop')

        queryset = Customer.objects.filter(
            shop=shop,
            phone=value
        )

        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise serializers.ValidationError(
                "This phone number already exists in your shop."
            )

        return value
