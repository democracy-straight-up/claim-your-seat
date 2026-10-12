from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from moda.models import ModaBackNForthChat, ModaMembers, ModaModel
from vote.models import Districts


class ModaBackNForthAppendOnlyTests(TestCase):
    def setUp(self):
        self.district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT01",
        )

        self.second_link = ModaModel.objects.create(
            district=self.district,
        )

        self.member = User.objects.create_user(
            username="alice",
            password="testpass",
        )
        self.member.users.legalName = "Alice Member"
        self.member.users.save()

        ModaMembers.objects.create(
            user=self.member,
            moda=self.second_link,
            is_member=True,
        )

        self.message = ModaBackNForthChat.objects.create(
            moda=self.second_link,
            sender=self.member,
            message="Sec-Del is requested to report back after the meeting.",
        )

        self.client = APIClient()
        self.client.force_authenticate(user=self.member)

        self.detail_url = reverse(
            "moda-backnforth-message-detail",
            kwargs={
                "moda_code": self.second_link.code,
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
            "Sec-Del is requested to report back after the meeting.",
        )
        self.assertFalse(self.message.is_edited)

    def test_author_cannot_delete_persisted_backnforth_post(self):
        response = self.client.delete(self.detail_url)

        self.assertEqual(response.status_code, 405)

        self.message.refresh_from_db()
        self.assertFalse(self.message.is_deleted)
