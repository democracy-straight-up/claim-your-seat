from asgiref.sync import async_to_sync
from django.contrib.auth.models import User
from django.test import TransactionTestCase

from api.backnforth_consumer import BackNForthChatConsumer
from api.models import BackNForthChat, SecDelMembers, SecDelModel
from vote.models import Districts


class BackNForthConsumerSystemMessageTests(TransactionTestCase):
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

    def test_websocket_reply_to_system_message_serializes_safely(self):
        system_message = BackNForthChat.objects.create(
            sec_del=self.first_link,
            sender=None,
            is_system=True,
            message="Succession update: something changed.",
        )

        consumer = BackNForthChatConsumer()
        consumer.scope = {"user": self.member}
        consumer.sec_del_code = self.first_link.code

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

    def test_recent_system_message_serializes_safely(self):
        system_message = BackNForthChat.objects.create(
            sec_del=self.first_link,
            sender=None,
            is_system=True,
            message="Succession update: something changed.",
        )

        consumer = BackNForthChatConsumer()
        consumer.scope = {"user": self.member}
        consumer.sec_del_code = self.first_link.code

        messages = async_to_sync(consumer.get_recent_messages)()

        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["id"], system_message.id)
        self.assertIsNone(messages[0]["sender"])
        self.assertEqual(messages[0]["sender_name"], "System")
        self.assertTrue(messages[0]["is_system"])

    def test_recent_reply_to_system_message_serializes_safely(self):
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

        consumer = BackNForthChatConsumer()
        consumer.scope = {"user": self.member}
        consumer.sec_del_code = self.first_link.code

        messages = async_to_sync(consumer.get_recent_messages)()

        reply_data = next(
            message
            for message in messages
            if message["id"] == reply.id
        )

        self.assertEqual(
            reply_data["reply_to_message"],
            {
                "id": system_message.id,
                "message": "Succession update: something changed.",
                "sender": None,
                "sender_name": "System",
            },
        )