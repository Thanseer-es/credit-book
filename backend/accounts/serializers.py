
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Shopkeeper


class RegisterSerializer(serializers.ModelSerializer):

    password = serializers.CharField(
        write_only=True,
        required=True
    )

    password2 = serializers.CharField(
        write_only=True,
        required=True
    )

    class Meta:
        model = Shopkeeper
        fields = [
            'id',
            'phone',
            'full_name',
            'password',
            'password2',
        ]

    def validate_phone(self, value):
        value = value.strip()

        if Shopkeeper.objects.filter(phone=value).exists():
            raise serializers.ValidationError(
                "This phone number is already registered."
            )

        return value

    def validate(self, attrs):

        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({
                'password2': "Passwords do not match."
            })

        validate_password(attrs['password'])

        return attrs

    def create(self, validated_data):

        validated_data.pop('password2')

        password = validated_data.pop('password')

        user = Shopkeeper.objects.create_user(
            password=password,
            **validated_data
        )

        return user


class UserProfileSerializer(serializers.ModelSerializer):

    class Meta:
        model = Shopkeeper
        fields = [
            'id',
            'phone',
            'full_name',
        ]
        read_only_fields = fields
