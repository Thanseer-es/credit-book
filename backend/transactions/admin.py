from django.contrib import admin
from .models import LedgerTransaction


@admin.register(LedgerTransaction)
class LedgerTransactionAdmin(admin.ModelAdmin):

    list_display = (
        'customer',
        'transaction_type',
        'amount',
        'shop',
        'created_by',
        'created_at',
    )

    list_filter = ('transaction_type', 'created_at')

    search_fields = (
        'customer__name',
        'customer__phone',
    )

    readonly_fields = ('id', 'created_at')