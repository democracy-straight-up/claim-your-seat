from asgiref.sync import async_to_sync
from django.contrib.auth.models import User
from django.test import TransactionTestCase

from holc.backnforth_consumer import HolcBackNForthChatConsumer
from holc.models import HolcBackNForthChat, HolcMembers, HolcModel
from vote.models import Districts


class HolcBackNForthConsumerSystemMessageTests(TransactionTestCase):
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

        self.membership = HolcMembers.objects.create(
            user=self.member,
            holc=self.caucus,
            is_member=True,
        )

    def test_websocket_reply_to_system_message_serializes_safely(self):
        system_message = HolcBackNForthChat.objects.create(
            holc=self.caucus,
            sender=None,
            is_system=True,
            message="Succession update: something changed.",
        )

        consumer = HolcBackNForthChatConsumer()
        consumer.scope = {"user": self.member}
        consumer.holc_code = self.caucus.code

        message_data = async_to_sync(consumer.save_message)(
            "Understood.",
            system_message.id,
        )

        self.assertIsNotNone(message_data)
        self.assertEqual(
            message_data["reply_to_message"],
            {
                "id": system_message.id,
                "message": "Succession update: something changed.",
                "sender": None,
                "sender_name": "System",
            },
        )
