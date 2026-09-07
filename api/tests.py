from rest_framework import status
from rest_framework.test import APITestCase


class CircleCredentialAPITests(APITestCase):
    def test_unauthenticated_user_cannot_access_circle_credential(self):
        response = self.client.get(
            "/api/circle-credential/TEST1/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED
        )