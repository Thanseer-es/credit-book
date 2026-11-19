
from rest_framework import serializers
from .models import LedgerTransaction


class LedgerTransactionSerializer(serializers.ModelSerializer):

    class Meta:
        model = LedgerTransaction

        fields = [
            'id',
            'customer',
            'transaction_type',
            'amount',
            'description',
            'client_transaction_id',
            'reversal_of',
            'created_at',
        ]

        read_only_fields = [
            'id',
            'created_at',
            'reversal_of',
        ]

    def validate_amount(self, value):

        if value <= 0:
            raise serializers.ValidationError(
                "Amount must be greater than zero."
            )

        return value

    def validate_description(self, value):

        return value.strip()


class TransactionReversalSerializer(serializers.Serializer):

    client_transaction_id = serializers.UUIDField()

    description = serializers.CharField(
        required=False,
        allow_blank=True
    )

    def validate_description(self, value):

        return value.strip()


class TransactionSyncStatusSerializer(serializers.Serializer):

    client_transaction_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        max_length=50
    )

    def validate_client_transaction_ids(self, value):

        if len(value) != len(set(value)):
            raise serializers.ValidationError(
                "Duplicate transaction IDs are not allowed."
            )

        return value
