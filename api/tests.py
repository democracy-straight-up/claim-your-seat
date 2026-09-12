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

    def test_candidate_cannot_update_to_inactive_circle_key(self):
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

        response = self.client.put(
            "/api/circle-credential/TEST1/",
            {
                "key_version": 1,
                "ciphertext": "updated-with-old-key",
                "algorithm": "test-algorithm",
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.credential.refresh_from_db()

        self.assertEqual(
            self.credential.ciphertext,
            "encrypted-name-and-address"
        )

    def test_circle_member_can_retrieve_candidate_encrypted_credential(self):
        self.client.force_authenticate(user=self.founder)

        response = self.client.get(
            f"/api/circle-credential/TEST1/{self.candidate_membership.id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )
        self.assertEqual(
            response.data["ciphertext"],
            "encrypted-name-and-address"
        )
    def test_candidate_cannot_review_another_circle_credential(self):
        self.client.force_authenticate(user=self.candidate)

        response = self.client.get(
            f"/api/circle-credential/TEST1/{self.founder_membership.id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND
        )
    def test_circle_member_cannot_review_credential_from_another_circle(self):
        other_user = User.objects.create_user(
            username="otheruser",
            password="testpass"
        )
        other_user.users.district = self.district
        other_user.users.save()

        other_circle = voteModels.Group.objects.create(
            code="TEST2",
            district=self.district,
            invitation_code="INVITE456",
            group_type=0,
            parent_group=None
        )

        other_membership = voteModels.GroupMember.objects.create(
            user=other_user,
            group=other_circle
        )

        voteModels.CircleCredential.objects.create(
            group_member=other_membership,
            key_version=1,
            ciphertext="other-circle-secret",
            algorithm="test-algorithm"
        )

        self.client.force_authenticate(user=self.founder)

        response = self.client.get(
            f"/api/circle-credential/TEST1/{other_membership.id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND
        )

    def test_candidate_cannot_create_second_circle_credential(self):
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
                "ciphertext": "replacement-via-post",
                "algorithm": "test-algorithm",
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.credential.refresh_from_db()
        self.assertEqual(
            self.credential.ciphertext,
            "encrypted-name-and-address"
        )

class CircleKeyEnvelopeAPITests(APITestCase):
    def setUp(self):
        self.district = voteModels.Districts.objects.create(
            name="Vermont At-Large",
            code="VT01"
        )

        self.member = User.objects.create_user(
            username="member",
            password="testpass"
        )
        self.member.users.district = self.district
        self.member.users.save()

        self.circle = voteModels.Group.objects.create(
            code="TEST1",
            district=self.district,
            invitation_code="INVITE123",
            group_type=0,
            parent_group=None
        )

        self.membership = voteModels.GroupMember.objects.create(
            user=self.member,
            group=self.circle,
            is_member=True,
            is_delegate=True
        )

        self.account_key = voteModels.AccountKey.objects.create(
            user=self.member,
            version=1,
            public_key="test-account-public-key",
            algorithm="test-algorithm",
            is_active=True
        )

        self.circle_key = voteModels.CircleKey.objects.create(
            group=self.circle,
            version=1,
            public_key="test-circle-public-key",
            algorithm="test-algorithm",
            is_active=True
        )

        self.envelope = voteModels.CircleKeyEnvelope.objects.create(
            circle_key=self.circle_key,
            group_member=self.membership,
            account_key=self.account_key,
            wrapped_key="wrapped-circle-private-key",
            algorithm="test-algorithm"
        )

    def test_unauthenticated_user_cannot_access_circle_key_envelope(self):
        response = self.client.get(
            "/api/circle-key-envelope/TEST1/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED
        )
    def test_candidate_cannot_retrieve_circle_key_envelope(self):
        candidate = User.objects.create_user(
            username="candidate",
            password="testpass"
        )
        candidate.users.district = self.district
        candidate.users.save()

        candidate_membership = voteModels.GroupMember.objects.create(
            user=candidate,
            group=self.circle,
            is_member=False,
            is_delegate=False
        )

        candidate_account_key = voteModels.AccountKey.objects.create(
            user=candidate,
            version=1,
            public_key="candidate-account-public-key",
            algorithm="test-algorithm",
            is_active=True
        )

        voteModels.CircleKeyEnvelope.objects.create(
            circle_key=self.circle_key,
            group_member=candidate_membership,
            account_key=candidate_account_key,
            wrapped_key="candidate-must-not-receive-this",
            algorithm="test-algorithm"
        )

        self.client.force_authenticate(user=candidate)

        response = self.client.get(
            "/api/circle-key-envelope/TEST1/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND
        )

    def test_circle_member_can_retrieve_own_key_envelope(self):
        self.client.force_authenticate(user=self.member)

        response = self.client.get(
            "/api/circle-key-envelope/TEST1/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )
        self.assertEqual(
            response.data["wrapped_key"],
            "wrapped-circle-private-key"
        )
        self.assertEqual(
            response.data["circle_key_version"],
            1
        )
        self.assertEqual(
            response.data["account_key_version"],
            1
        )
    def test_circle_delegate_can_create_envelope_for_member(self):
        target = User.objects.create_user(
            username="target-member",
            password="testpass"
        )
        target.users.district = self.district
        target.users.save()

        target_membership = voteModels.GroupMember.objects.create(
            user=target,
            group=self.circle,
            is_member=True,
            is_delegate=False
        )

        target_account_key = voteModels.AccountKey.objects.create(
            user=target,
            version=1,
            public_key="target-account-public-key",
            algorithm="test-algorithm",
            is_active=True
        )

        self.client.force_authenticate(user=self.member)

        response = self.client.post(
            f"/api/circle-key-envelope/TEST1/{target_membership.id}/",
            {
                "wrapped_key": "wrapped-for-target",
                "algorithm": "test-algorithm",
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED
        )

        envelope = voteModels.CircleKeyEnvelope.objects.get(
            circle_key=self.circle_key,
            group_member=target_membership
        )

        self.assertEqual(
            envelope.account_key,
            target_account_key
        )
        self.assertEqual(
            envelope.wrapped_key,
            "wrapped-for-target"
        )
    def test_delegate_cannot_create_duplicate_envelope(self):
        self.client.force_authenticate(user=self.member)

        response = self.client.post(
            f"/api/circle-key-envelope/TEST1/{self.membership.id}/",
            {
                "wrapped_key": "replacement-wrapped-key",
                "algorithm": "test-algorithm",
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.envelope.refresh_from_db()
        self.assertEqual(
            self.envelope.wrapped_key,
            "wrapped-circle-private-key"
        )
    def test_delegate_cannot_create_envelope_without_wrapped_key(self):
        target = User.objects.create_user(
            username="missing-key-target",
            password="testpass"
        )
        target.users.district = self.district
        target.users.save()

        target_membership = voteModels.GroupMember.objects.create(
            user=target,
            group=self.circle,
            is_member=True,
            is_delegate=False
        )

        voteModels.AccountKey.objects.create(
            user=target,
            version=1,
            public_key="target-account-public-key",
            algorithm="test-algorithm",
            is_active=True
        )

        self.client.force_authenticate(user=self.member)

        response = self.client.post(
            f"/api/circle-key-envelope/TEST1/{target_membership.id}/",
            {
                "algorithm": "test-algorithm",
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.assertFalse(
            voteModels.CircleKeyEnvelope.objects.filter(
                circle_key=self.circle_key,
                group_member=target_membership
            ).exists()
        )
    def test_delegate_cannot_create_envelope_without_algorithm(self):
        target = User.objects.create_user(
            username="missing-algorithm-target",
            password="testpass"
        )
        target.users.district = self.district
        target.users.save()

        target_membership = voteModels.GroupMember.objects.create(
            user=target,
            group=self.circle,
            is_member=True,
            is_delegate=False
        )

        voteModels.AccountKey.objects.create(
            user=target,
            version=1,
            public_key="target-account-public-key",
            algorithm="test-algorithm",
            is_active=True
        )

        self.client.force_authenticate(user=self.member)

        response = self.client.post(
            f"/api/circle-key-envelope/TEST1/{target_membership.id}/",
            {
                "wrapped_key": "wrapped-for-target",
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.assertFalse(
            voteModels.CircleKeyEnvelope.objects.filter(
                circle_key=self.circle_key,
                group_member=target_membership
            ).exists()
        )
    def test_non_delegate_member_cannot_create_envelope(self):
        ordinary_member = User.objects.create_user(
            username="ordinary-member",
            password="testpass"
        )
        ordinary_member.users.district = self.district
        ordinary_member.users.save()

        ordinary_membership = voteModels.GroupMember.objects.create(
            user=ordinary_member,
            group=self.circle,
            is_member=True,
            is_delegate=False
        )

        self.client.force_authenticate(user=ordinary_member)

        response = self.client.post(
            f"/api/circle-key-envelope/TEST1/{ordinary_membership.id}/",
            {
                "wrapped_key": "should-not-be-accepted",
                "algorithm": "test-algorithm",
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND
        )
class CircleMemberAccountKeyAPITests(APITestCase):
    def setUp(self):
        self.district = voteModels.Districts.objects.create(
            name="Vermont At-Large",
            code="VT01"
        )

        self.delegate = User.objects.create_user(
            username="delegate",
            password="testpass"
        )
        self.delegate.users.district = self.district
        self.delegate.users.save()

        self.target = User.objects.create_user(
            username="target",
            password="testpass"
        )
        self.target.users.district = self.district
        self.target.users.save()

        self.circle = voteModels.Group.objects.create(
            code="TEST1",
            district=self.district,
            invitation_code="INVITE123",
            group_type=0,
            parent_group=None
        )

        self.delegate_membership = voteModels.GroupMember.objects.create(
            user=self.delegate,
            group=self.circle,
            is_member=True,
            is_delegate=True
        )

        self.target_membership = voteModels.GroupMember.objects.create(
            user=self.target,
            group=self.circle,
            is_member=True,
            is_delegate=False
        )

        self.target_account_key = voteModels.AccountKey.objects.create(
            user=self.target,
            version=1,
            public_key="target-public-key",
            algorithm="test-algorithm",
            is_active=True
        )

    def test_delegate_can_get_member_active_account_public_key(self):
        self.client.force_authenticate(user=self.delegate)

        response = self.client.get(
            f"/api/circle-member-account-key/TEST1/{self.target_membership.id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )
        self.assertEqual(
            response.data["public_key"],
            "target-public-key"
        )
        self.assertEqual(
            response.data["version"],
            1
        )
        self.assertEqual(
            response.data["algorithm"],
            "test-algorithm"
        )
    def test_non_delegate_cannot_get_member_account_public_key(self):
        ordinary_member = User.objects.create_user(
            username="ordinary-member",
            password="testpass"
        )
        ordinary_member.users.district = self.district
        ordinary_member.users.save()

        voteModels.GroupMember.objects.create(
            user=ordinary_member,
            group=self.circle,
            is_member=True,
            is_delegate=False
        )

        self.client.force_authenticate(user=ordinary_member)

        response = self.client.get(
            f"/api/circle-member-account-key/TEST1/{self.target_membership.id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND
        )
    def test_delegate_cannot_get_account_key_for_member_in_another_circle(self):
        other_circle = voteModels.Group.objects.create(
            code="TEST2",
            district=self.district,
            invitation_code="OTHER123",
            group_type=0,
            parent_group=None
        )

        outsider = User.objects.create_user(
            username="outsider",
            password="testpass"
        )
        outsider.users.district = self.district
        outsider.users.save()

        outsider_membership = voteModels.GroupMember.objects.create(
            user=outsider,
            group=other_circle,
            is_member=True,
            is_delegate=False
        )

        voteModels.AccountKey.objects.create(
            user=outsider,
            version=1,
            public_key="outsider-public-key",
            algorithm="test-algorithm",
            is_active=True
        )

        self.client.force_authenticate(user=self.delegate)

        response = self.client.get(
            f"/api/circle-member-account-key/TEST1/{outsider_membership.id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND
        )
    def test_delegate_cannot_get_account_key_for_candidate(self):
        candidate = User.objects.create_user(
            username="candidate",
            password="testpass"
        )
        candidate.users.district = self.district
        candidate.users.save()

        candidate_membership = voteModels.GroupMember.objects.create(
            user=candidate,
            group=self.circle,
            is_member=False,
            is_delegate=False
        )

        voteModels.AccountKey.objects.create(
            user=candidate,
            version=1,
            public_key="candidate-public-key",
            algorithm="test-algorithm",
            is_active=True
        )

        self.client.force_authenticate(user=self.delegate)

        response = self.client.get(
            f"/api/circle-member-account-key/TEST1/{candidate_membership.id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND
        )
    def test_unauthenticated_user_cannot_get_member_account_public_key(self):
        response = self.client.get(
            f"/api/circle-member-account-key/TEST1/{self.target_membership.id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED
        )