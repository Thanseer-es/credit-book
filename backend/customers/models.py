
import uuid

from django.db import models
from shops.models import Shop


class Customer(models.Model):

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name='customers'
    )

    name = models.CharField(max_length=150)

    phone = models.CharField(max_length=20)

    address = models.TextField(blank=True)

    notes = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['shop', 'phone'],
                name='unique_customer_phone_per_shop'
            )
        ]

        ordering = ['name']

    def __str__(self):
        return f"{self.name} - {self.phone}"
