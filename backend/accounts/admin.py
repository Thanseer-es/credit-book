from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Shopkeeper


@admin.register(Shopkeeper)
class ShopkeeperAdmin(UserAdmin):

    model = Shopkeeper

    ordering = ('phone',)

    list_display = (
        'phone',
        'full_name',
        'is_staff',
        'is_active',
    )

    fieldsets = (
        (None, {'fields': ('phone', 'password')}),
        ('Personal info', {'fields': ('full_name',)}),
        ('Permissions', {
            'fields': (
                'is_active',
                'is_staff',
                'is_superuser',
                'groups',
                'user_permissions',
            )
        }),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'phone',
                'full_name',
                'password1',
                'password2',
            ),
        }),
    )