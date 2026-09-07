from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase
from vote import models as voteModels


class CircleCredentialAPITests(APITestCase):
    def setUp(self):
        self.district = voteModels.Districts.objects.create(
            name="Vermont At-Large",
            code="VT01"
        )

        self.founder = User.objects.create_user(
            username="founder",
            password="testpass"
        )
        self.founder.users.district = self.district
        self.founder.users.save()

        self.candidate = User.objects.create_user(
            username="candidate",
            password="testpass"
        )
        self.candidate.users.district = self.district
        self.candidate.users.save()

        self.circle = voteModels.Group.objects.create(
            code="TEST1",
            district=self.district,
            invitation_code="INVITE123",
            group_type=0,
            parent_group=None
        )

        self.founder_membership = voteModels.GroupMember.objects.create(
            user=self.founder,
            group=self.circle,
            is_member=True,
            is_delegate=True
        )

        self.candidate_membership = voteModels.GroupMember.objects.create(
            user=self.candidate,
            group=self.circle,
            is_member=False,
            is_delegate=False
        )

        self.credential = voteModels.CircleCredential.objects.create(
            group_member=self.candidate_membership,
            key_version=1,
            ciphertext="encrypted-name-and-address",
            algorithm="test-algorithm"
        )

    def test_unauthenticated_user_cannot_access_circle_credential(self):
        response = self.client.get(
            "/api/circle-credential/TEST1/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED
        )

    def test_candidate_can_retrieve_own_encrypted_credential(self):
        self.client.force_authenticate(user=self.candidate)

        response = self.client.get(
            "/api/circle-credential/TEST1/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )
        self.assertEqual(
            response.data["ciphertext"],
            "encrypted-name-and-address"
        )
        self.assertEqual(response.data["key_version"], 1)
        self.assertEqual(
            response.data["algorithm"],
            "test-algorithm"
        )

    def test_candidate_can_create_own_encrypted_credential(self):
        self.credential.delete()

        voteModels.CircleKey.objects.create(
            group=self.circle,
            version=1,
            public_key="test-circle-public-key",
            algorithm="test-algorithm",
            is_active=True
        )

        self.client.force_authenticate(user=self.candidate)

        response = self.client.post(
            "/api/circle-credential/TEST1/",
            {
                "key_version": 1,
                "ciphertext": "new-encrypted-name-and-address",
                "algorithm": "test-algorithm",
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED
        )

        credential = voteModels.CircleCredential.objects.get(
            group_member=self.candidate_membership
        )

        self.assertEqual(
            credential.ciphertext,
            "new-encrypted-name-and-address"
        )
        self.assertEqual(credential.key_version, 1)
        self.assertEqual(
            credential.algorithm,
            "test-algorithm"
        )

    def test_candidate_cannot_use_nonexistent_circle_key_version(self):
        self.credential.delete()

        voteModels.CircleKey.objects.create(
            group=self.circle,
            version=1,
            public_key="test-circle-public-key",
            algorithm="test-algorithm",
            is_active=True
        )

        self.client.force_authenticate(user=self.candidate)

        response = self.client.post(
            "/api/circle-credential/TEST1/",
            {
                "key_version": 99,
                "ciphertext": "encrypted-name-and-address",
                "algorithm": "test-algorithm",
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.assertFalse(
            voteModels.CircleCredential.objects.filter(
                group_member=self.candidate_membership
            ).exists()
        )

    def test_candidate_can_update_own_encrypted_credential(self):
        voteModels.CircleKey.objects.create(
            group=self.circle,
            version=2,
            public_key="new-test-circle-public-key",
            algorithm="test-algorithm",
            is_active=True
        )

        self.client.force_authenticate(user=self.candidate)

        response = self.client.put(
            "/api/circle-credential/TEST1/",
            {
                "key_version": 2,
                "ciphertext": "replacement-encrypted-name-and-address",
                "algorithm": "test-algorithm",
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.credential.refresh_from_db()

        self.assertEqual(
            self.credential.ciphertext,
            "replacement-encrypted-name-and-address"
        )
        self.assertEqual(self.credential.key_version, 2)

    def test_candidate_cannot_use_inactive_circle_key(self):
        self.credential.delete()

        voteModels.CircleKey.objects.create(
            group=self.circle,
            version=1,
            public_key="old-circle-public-key",
            algorithm="test-algorithm",
            is_active=False
        )

        voteModels.CircleKey.objects.create(
            group=self.circle,
            version=2,
            public_key="current-circle-public-key",
            algorithm="test-algorithm",
            is_active=True
        )

        self.client.force_authenticate(user=self.candidate)

        response = self.client.post(
            "/api/circle-credential/TEST1/",
            {
                "key_version": 1,
                "ciphertext": "encrypted-with-old-key",
                "algorithm": "test-algorithm",
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.assertFalse(
            voteModels.CircleCredential.objects.filter(
                group_member=self.candidate_membership
            ).exists()
        )