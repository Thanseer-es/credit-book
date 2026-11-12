
from django.db import models
from django.conf import settings


class Shop(models.Model):

    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='shop'
    )

    shop_name = models.CharField(max_length=150)

    address = models.TextField(blank=True, null=True)

    city = models.CharField(max_length=100, blank=True)

    pincode = models.CharField(max_length=10, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.shop_name
