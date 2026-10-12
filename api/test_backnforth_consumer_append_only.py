import json
from unittest.mock import AsyncMock

from asgiref.sync import async_to_sync
from django.test import SimpleTestCase

from api.backnforth_consumer import BackNForthChatConsumer


class BackNForthConsumerAppendOnlyTests(SimpleTestCase):
    def test_websocket_edit_command_is_not_supported(self):
        consumer = BackNForthChatConsumer()
        consumer.handle_edit_message = AsyncMock()

        async_to_sync(consumer.receive)(
            json.dumps(
                {
                    "type": "edit_message",
                    "message_id": 123,
                    "message": "Rewritten version.",
                }
            )
        )

        consumer.handle_edit_message.assert_not_awaited()

    def test_websocket_delete_command_is_not_supported(self):
        consumer = BackNForthChatConsumer()
        consumer.handle_delete_message = AsyncMock()

        async_to_sync(consumer.receive)(
            json.dumps(
                {
                    "type": "delete_message",
                    "message_id": 123,
                }
            )
        )

        consumer.handle_delete_message.assert_not_awaited()
