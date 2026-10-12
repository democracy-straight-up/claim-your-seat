from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from holc.models import HolcBackNForthChat, HolcMembers, HolcModel
from vote.models import Districts


class HolcBackNForthAppendOnlyTests(TestCase):
    def setUp(self):
        self.district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT01",
        )

        self.caucus = HolcModel.objects.create(
            code=1,
            district=self.district,
        )

        self.member = User.objects.create_user(
            username="alice",
            password="testpass",
        )
        self.member.users.legalName = "Alice Member"
        self.member.users.save()

        HolcMembers.objects.create(
            user=self.member,
            holc=self.caucus,
            is_member=True,
        )

        self.message = HolcBackNForthChat.objects.create(
            holc=self.caucus,
            sender=self.member,
            message="HoLC is requested to report back after the meeting.",
        )

        self.client = APIClient()
        self.client.force_authenticate(user=self.member)

        self.detail_url = reverse(
            "holc-backnforth-detail",
            kwargs={
                "holc_code": self.caucus.code,
                "pk": self.message.id,
            },
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
            "HoLC is requested to report back after the meeting.",
        )
        self.assertFalse(self.message.is_edited)

    def test_author_cannot_delete_persisted_backnforth_post(self):
        response = self.client.delete(self.detail_url)

        self.assertEqual(response.status_code, 405)

        self.message.refresh_from_db()
        self.assertFalse(self.message.is_deleted)
