from asgiref.sync import async_to_sync
from django.contrib.auth.models import User
from django.test import TransactionTestCase

from moda.backnforth_consumer import ModaBackNForthChatConsumer
from moda.models import ModaBackNForthChat, ModaMembers, ModaModel
from vote.models import Districts


class ModaBackNForthConsumerSystemMessageTests(TransactionTestCase):
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

    def test_websocket_reply_to_system_message_serializes_safely(self):
        system_message = ModaBackNForthChat.objects.create(
            moda=self.second_link,
            sender=None,
            is_system=True,
            message="Succession update: something changed.",
        )

        consumer = ModaBackNForthChatConsumer()
        consumer.scope = {"user": self.member}
        consumer.moda_code = self.second_link.code

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