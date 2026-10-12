from django.contrib.auth.models import User
from django.test import TestCase

from api.models import BackNForthChat, SecDelMembers, SecDelModel
from api.sec_del_ser import BackNForthChatSerializer
from vote.models import Districts


class BackNForthSystemMessageSerializerTests(TestCase):
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
        self.membership = SecDelMembers.objects.create(
            user=self.member,
            sec_del=self.first_link,
            is_member=True,
        )
    def test_reply_to_system_message_serializes_without_crashing(self):
        system_message = BackNForthChat.objects.create(
            sec_del=self.first_link,
            sender=None,
            is_system=True,
            message="Succession update: something changed.",
        )

        reply = BackNForthChat.objects.create(
            sec_del=self.first_link,
            sender=self.member,
            is_system=False,
            message="Understood.",
            reply_to=system_message,
        )

        data = BackNForthChatSerializer(reply).data

        self.assertEqual(
            data["reply_to_message"],
            {
                "id": system_message.id,
                "message": "Succession update: something changed.",
                "sender": None,
                "sender_name": "System",
            },
        )

    def test_system_message_serialization_exposes_is_system(self):
        system_message = BackNForthChat.objects.create(
            sec_del=self.first_link,
            sender=None,
            is_system=True,
            message="Succession update: something changed.",
        )

        data = BackNForthChatSerializer(system_message).data

        self.assertTrue(data["is_system"])
