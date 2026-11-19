
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from shops.models import Shop
from customers.models import Customer


User = get_user_model()


class CustomerOwnershipTests(TestCase):

    def setUp(self):

        # Create first shopkeeper
        self.user_a = User.objects.create_user(
            phone="9876543210",
            full_name="Shopkeeper A",
            password="Test@12345"
        )

        # Create second shopkeeper
        self.user_b = User.objects.create_user(
            phone="9876543211",
            full_name="Shopkeeper B",
            password="Test@12345"
        )

        # Create shops
        self.shop_a = Shop.objects.create(
            owner=self.user_a,
            shop_name="Shop A"
        )

        self.shop_b = Shop.objects.create(
            owner=self.user_b,
            shop_name="Shop B"
        )

        # Create customer belonging to Shop A
        self.customer_a = Customer.objects.create(
            shop=self.shop_a,
            name="Customer A",
            phone="9000000001"
        )

        self.client = APIClient()

        self.customer_url = "/api/customers/"
        self.detail_url = (
            f"/api/customers/{self.customer_a.id}/"
        )

    def test_shopkeeper_cannot_see_other_shop_customers(self):

        self.client.force_authenticate(user=self.user_b)

        response = self.client.get(self.customer_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

    def test_shopkeeper_cannot_view_other_shop_customer(self):

        self.client.force_authenticate(user=self.user_b)

        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, 404)

    def test_shopkeeper_cannot_update_other_shop_customer(self):

        self.client.force_authenticate(user=self.user_b)

        response = self.client.patch(
            self.detail_url,
            {"name": "Hacked Customer"},
            format="json"
        )

        self.assertEqual(response.status_code, 404)

        self.customer_a.refresh_from_db()

        self.assertEqual(
            self.customer_a.name,
            "Customer A"
        )

    def test_shopkeeper_cannot_delete_other_shop_customer(self):

        self.client.force_authenticate(user=self.user_b)

        response = self.client.delete(self.detail_url)

        self.assertEqual(response.status_code, 404)

        self.customer_a.refresh_from_db()

        self.assertTrue(self.customer_a.is_active)
