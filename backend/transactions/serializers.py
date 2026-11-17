
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


class TransactionReversalSerializer(serializers.Serializer):

    client_transaction_id = serializers.UUIDField()

    description = serializers.CharField(
        required=False,
        allow_blank=True
    )