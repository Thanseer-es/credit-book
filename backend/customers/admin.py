
from django.contrib import admin
from .models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'name',
        'phone',
        'shop',
        'is_active',
        'created_at',
    )

    search_fields = (
        'name',
        'phone',
    )

    list_filter = (
        'is_active',
        'created_at',
    )
