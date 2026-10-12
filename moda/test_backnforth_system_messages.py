from django.contrib.auth.models import User
from django.test import TestCase

from moda.models import ModaBackNForthChat, ModaMembers, ModaModel
from moda.serializers import ModaBackNForthChatSerializer
from vote.models import Districts


class ModaBackNForthSystemMessageSerializerTests(TestCase):
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

        self.membership = ModaMembers.objects.create(
            user=self.member,
            moda=self.second_link,
            is_member=True,
        )

    def test_reply_to_system_message_serializes_without_crashing(self):
        system_message = ModaBackNForthChat.objects.create(
            moda=self.second_link,
            sender=None,
            is_system=True,
            message="Succession update: something changed.",
        )

        reply = ModaBackNForthChat.objects.create(
            moda=self.second_link,
            sender=self.member,
            is_system=False,
            message="Understood.",
            reply_to=system_message,
        )

        data = ModaBackNForthChatSerializer(reply).data

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
        system_message = ModaBackNForthChat.objects.create(
            moda=self.second_link,
            sender=None,
            is_system=True,
            message="Succession update: something changed.",
        )

        data = ModaBackNForthChatSerializer(system_message).data

        self.assertTrue(data["is_system"])
