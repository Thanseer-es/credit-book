
from django.test import TestCase
from rest_framework.test import APIClient


class AuthenticationSecurityTests(TestCase):

    def setUp(self):
        self.client = APIClient()

    def test_customers_api_requires_authentication(self):

        response = self.client.get("/api/customers/")

        self.assertEqual(response.status_code, 401)

        self.assertFalse(response.data["success"])

        self.assertEqual(
            response.data["message"],
            "Authentication failed."
        )

    def test_transactions_api_requires_authentication(self):

        response = self.client.get("/api/transactions/")

        self.assertEqual(response.status_code, 401)

        self.assertFalse(response.data["success"])

        self.assertEqual(
            response.data["message"],
            "Authentication failed."
        )

    def test_reports_api_requires_authentication(self):

        response = self.client.get(
            "/api/reports/dashboard/"
        )

        self.assertEqual(response.status_code, 401)

        self.assertFalse(response.data["success"])

        self.assertEqual(
            response.data["message"],
            "Authentication failed."
        )
    
    def test_registration_rejects_invalid_phone(self):

        response = self.client.post(
            "/api/auth/register/",
            {
                "phone": "1234567890",
                "full_name": "Test User",
                "password": "StrongPassword@123",
                "password2": "StrongPassword@123"
            },
            format="json"
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data["success"])
        self.assertEqual(
            response.data["message"],
            "Validation failed."
        )
        self.assertIn("phone", response.data["errors"])

    def test_registration_rejects_password_mismatch(self):

        response = self.client.post(
            "/api/auth/register/",
            {
                "phone": "9876543210",
                "full_name": "Test User",
                "password": "StrongPassword@123",
                "password2": "DifferentPassword@123"
            },
            format="json"
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data["success"])
        self.assertIn("password2", response.data["errors"])
