from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from api.models import BackNForthChat, SecDelMembers, SecDelModel
from vote.models import Districts


class BackNForthAppendOnlyTests(TestCase):
    def setUp(self):
        self.district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT01",
        )

        self.first_link = SecDelModel.objects.create(
            district=self.district,
        )

        self.member = User.objects.create_user(
            username="alice",
            password="testpass",
        )
        self.member.users.legalName = "Alice Member"
        self.member.users.save()

        SecDelMembers.objects.create(
            user=self.member,
            sec_del=self.first_link,
            is_member=True,
        )

        self.message = BackNForthChat.objects.create(
            sec_del=self.first_link,
            sender=self.member,
            message="F-Del is requested to report back after the meeting.",
        )

        self.client = APIClient()
        self.client.force_authenticate(user=self.member)

        self.detail_url = (
            f"/api/backnforth/{self.first_link.code}/"
            f"messages/{self.message.id}/"
        )

    def test_author_cannot_edit_persisted_backnforth_post(self):
        response = self.client.patch(
            self.detail_url,
            {"message": "Rewritten version."},
            format="json",
        )

        self.assertEqual(response.status_code, 405)

        self.message.refresh_from_db()
        self.assertEqual(
            self.message.message,
            "F-Del is requested to report back after the meeting.",
        )
        self.assertFalse(self.message.is_edited)

    def test_author_cannot_delete_persisted_backnforth_post(self):
        response = self.client.delete(self.detail_url)

        self.assertEqual(response.status_code, 405)

        self.message.refresh_from_db()
        self.assertFalse(self.message.is_deleted)
