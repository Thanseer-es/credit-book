
import uuid

from decimal import Decimal
from unittest.mock import patch
from django.db import DatabaseError
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from shops.models import Shop
from customers.models import Customer
from transactions.models import LedgerTransaction


User = get_user_model()


class TransactionSyncTests(TestCase):

    def setUp(self):
        self.client = APIClient()

        # Create shopkeeper
        self.user = User.objects.create_user(
            phone="9876543210",
            full_name="Test Shopkeeper",
            password="Test@12345"
        )

        # Create shop
        self.shop = Shop.objects.create(
            owner=self.user,
            shop_name="Test Grocery Store",
            address="Test Address",
            city="Aluva",
            pincode="683101"
        )

        # Create customer
        self.customer = Customer.objects.create(
            shop=self.shop,
            name="Test Customer",
            phone="9876501234"
        )

        self.client.force_authenticate(user=self.user)

        self.sync_url = "/api/transactions/sync/"

    def create_transaction(self, transaction_id=None, amount="500.00"):
        return {
            "customer": str(self.customer.id),
            "transaction_type": "CREDIT",
            "amount": amount,
            "description": "Test credit",
            "client_transaction_id": str(
                transaction_id or uuid.uuid4()
            )
        }

    def test_successful_sync(self):
        transaction_data = self.create_transaction()

        response = self.client.post(
            self.sync_url,
            {"transactions": [transaction_data]},
            format="json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            LedgerTransaction.objects.count(), 1
        )

    def test_duplicate_sync(self):
        transaction_data = self.create_transaction()

        first_response = self.client.post(
            self.sync_url,
            {"transactions": [transaction_data]},
            format="json"
        )

        second_response = self.client.post(
            self.sync_url,
            {"transactions": [transaction_data]},
            format="json"
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)

        # Duplicate must not create another record
        self.assertEqual(
            LedgerTransaction.objects.count(), 1
        )

    def test_conflicting_transaction_id(self):
        transaction_id = uuid.uuid4()

        first_transaction = self.create_transaction(
            transaction_id=transaction_id,
            amount="500.00"
        )

        second_transaction = self.create_transaction(
            transaction_id=transaction_id,
            amount="700.00"
        )

        self.client.post(
            self.sync_url,
            {"transactions": [first_transaction]},
            format="json"
        )

        response = self.client.post(
            self.sync_url,
            {"transactions": [second_transaction]},
            format="json"
        )

        self.assertEqual(response.status_code, 200)

        # The changed transaction must not be saved
        self.assertEqual(
            LedgerTransaction.objects.count(), 1
        )
        
    
    def test_invalid_transaction_rejected(self):
        transaction_data = self.create_transaction(
            amount="-100.00"
        )

        response = self.client.post(
            self.sync_url,
            {"transactions": [transaction_data]},
            format="json"
        )

        self.assertEqual(response.status_code, 200)

        # Invalid transaction must not be saved
        self.assertEqual(
            LedgerTransaction.objects.count(), 0
        )

    def test_mixed_batch_sync(self):
        valid_transaction = self.create_transaction(
            amount="500.00"
        )

        invalid_transaction = self.create_transaction(
            amount="-100.00"
        )

        response = self.client.post(
            self.sync_url,
            {
                "transactions": [
                    valid_transaction,
                    invalid_transaction
                ]
            },
            format="json"
        )

        self.assertEqual(response.status_code, 200)

        # Only the valid transaction should be saved
        self.assertEqual(
            LedgerTransaction.objects.count(), 1
        )
        
        
    @patch("transactions.views.LedgerTransaction.objects.create")
    def test_temporary_database_failure(self, mock_create):

        mock_create.side_effect = DatabaseError(
            "Temporary database failure"
        )

        transaction_data = self.create_transaction()

        response = self.client.post(
            self.sync_url,
            {"transactions": [transaction_data]},
            format="json"
        )

        self.assertEqual(response.status_code, 200)

        result = response.data["results"][0]

        self.assertEqual(result["status"], "failed")
        self.assertTrue(result["retryable"])
        self.assertEqual(result["retry_after_seconds"], 5)
        
    
    def create_second_shopkeeper(self):

        user_b = User.objects.create_user(
            phone="9876543211",
            full_name="Shopkeeper B",
            password="Test@12345"
        )

        shop_b = Shop.objects.create(
            owner=user_b,
            shop_name="Shop B"
        )

        return user_b, shop_b

    def create_original_transaction(self):

        return LedgerTransaction.objects.create(
            shop=self.shop,
            customer=self.customer,
            transaction_type="CREDIT",
            amount=Decimal("500.00"),
            description="Test credit",
            client_transaction_id=uuid.uuid4(),
            created_by=self.user
        )

    def test_shopkeeper_cannot_see_other_shop_transactions(self):

        self.create_original_transaction()

        user_b, shop_b = self.create_second_shopkeeper()

        self.client.force_authenticate(user=user_b)

        response = self.client.get("/api/transactions/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

    def test_shopkeeper_cannot_view_other_shop_balance(self):

        user_b, shop_b = self.create_second_shopkeeper()

        self.client.force_authenticate(user=user_b)

        url = f"/api/transactions/balance/{self.customer.id}/"

        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)

    def test_shopkeeper_cannot_reverse_other_shop_transaction(self):

        original = self.create_original_transaction()

        user_b, shop_b = self.create_second_shopkeeper()

        self.client.force_authenticate(user=user_b)

        url = f"/api/transactions/{original.id}/reverse/"

        response = self.client.post(
            url,
            {
                "client_transaction_id": str(uuid.uuid4()),
                "description": "Unauthorized reversal"
            },
            format="json"
        )

        self.assertEqual(response.status_code, 404)

    def test_sync_status_does_not_reveal_other_shop_transactions(self):

        original = self.create_original_transaction()

        user_b, shop_b = self.create_second_shopkeeper()

        self.client.force_authenticate(user=user_b)

        response = self.client.post(
            "/api/transactions/sync/status/",
            {
                "client_transaction_ids": [
                    str(original.client_transaction_id)
                ]
            },
            format="json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["results"][0]["status"],
            "not_found"
        )

    def test_sync_rejects_other_shop_customer(self):

        user_b, shop_b = self.create_second_shopkeeper()

        self.client.force_authenticate(user=user_b)

        transaction_data = {
            "customer": str(self.customer.id),
            "transaction_type": "CREDIT",
            "amount": "500.00",
            "description": "Unauthorized credit",
            "client_transaction_id": str(uuid.uuid4())
        }

        response = self.client.post(
            "/api/transactions/sync/",
            {"transactions": [transaction_data]},
            format="json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["results"][0]["status"],
            "rejected"
        )

    def test_create_rejects_other_shop_customer(self):

        user_b, shop_b = self.create_second_shopkeeper()

        self.client.force_authenticate(user=user_b)

        response = self.client.post(
            "/api/transactions/",
            {
                "customer": str(self.customer.id),
                "transaction_type": "CREDIT",
                "amount": "500.00",
                "description": "Unauthorized credit",
                "client_transaction_id": str(uuid.uuid4())
            },
            format="json"
        )

        self.assertEqual(response.status_code, 400)


