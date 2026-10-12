from django.contrib.auth.models import User
from django.test import TestCase

from holc.models import HolcBackNForthChat, HolcMembers, HolcModel
from holc.serializers import HolcBackNForthChatSerializer
from vote.models import Districts


class HolcBackNForthSystemMessageSerializerTests(TestCase):
    def setUp(self):
        self.district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT01",
        )

        self.caucus = HolcModel.objects.create(
            district=self.district,
            code=2,
        )

        self.member = User.objects.create_user(
            username="alice",
            password="testpass",
        )
        self.member.users.legalName = "Alice Member"
        self.member.users.save()

        self.membership = HolcMembers.objects.create(
            user=self.member,
            holc=self.caucus,
            is_member=True,
        )

    def test_reply_to_system_message_serializes_without_crashing(self):
        system_message = HolcBackNForthChat.objects.create(
            holc=self.caucus,
            sender=None,
            is_system=True,
            message="Succession update: something changed.",
        )

        reply = HolcBackNForthChat.objects.create(
            holc=self.caucus,
            sender=self.member,
            is_system=False,
            message="Understood.",
            reply_to=system_message,
        )

        data = HolcBackNForthChatSerializer(reply).data

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
        system_message = HolcBackNForthChat.objects.create(
            holc=self.caucus,
            sender=None,
            is_system=True,
            message="Succession update: something changed.",
        )

        data = HolcBackNForthChatSerializer(system_message).data

        self.assertTrue(data["is_system"])
