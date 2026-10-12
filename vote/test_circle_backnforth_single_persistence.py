from channels.db import database_sync_to_async
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import User
from django.test import TransactionTestCase, override_settings
from rest_framework_simplejwt.tokens import AccessToken

from api.jwt_middleware import JWTAuthMiddleware
from live.routing import websocket_urlpatterns
from vote.models import (
    CircleBackNForth,
    Districts,
    Group,
    GroupMember,
    Users,
)


@override_settings(
    CHANNEL_LAYERS={
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        },
    },
)
class CircleBackNForthSinglePersistenceTests(TransactionTestCase):
    def setUp(self):
        self.district, _ = Districts.objects.get_or_create(
            code="VT00",
            defaults={"name": "Vermont"},
        )

        self.sender = User.objects.create_user(
            username="circle_sender",
            password="local-test-password",
            is_active=True,
        )
        Users.objects.update_or_create(
            user=self.sender,
            defaults={"district": self.district},
        )
        self.sender_token = str(AccessToken.for_user(self.sender))

        self.viewer = User.objects.create_user(
            username="circle_viewer",
            password="another-local-test-password",
            is_active=True,
        )
        Users.objects.update_or_create(
            user=self.viewer,
            defaults={"district": self.district},
        )
        self.viewer_token = str(AccessToken.for_user(self.viewer))

        self.circle = Group.objects.create(
            code="CBF02",
            district=self.district,
            invitation_code="0987654321",
            group_type=1,
        )

        GroupMember.objects.create(
            user=self.sender,
            group=self.circle,
            is_member=True,
        )
        GroupMember.objects.create(
            user=self.viewer,
            group=self.circle,
            is_member=True,
        )

    def application(self):
        return JWTAuthMiddleware(
            URLRouter(websocket_urlpatterns)
        )

    async def test_one_entry_is_persisted_once_with_two_connected_members(self):
        sender_communicator = WebsocketCommunicator(
            self.application(),
            (
                f"/ws/{self.circle.code}/{self.sender.username}/"
                f"?token={self.sender_token}"
            ),
        )
        viewer_communicator = WebsocketCommunicator(
            self.application(),
            (
                f"/ws/{self.circle.code}/{self.viewer.username}/"
                f"?token={self.viewer_token}"
            ),
        )

        try:
            sender_connected, _ = await sender_communicator.connect()
            viewer_connected, _ = await viewer_communicator.connect()

            self.assertTrue(sender_connected)
            self.assertTrue(viewer_connected)

            # Consume each connection's initial message-history page.
            await sender_communicator.receive_json_from()
            await viewer_communicator.receive_json_from()

            await sender_communicator.send_json_to(
                {
                    "message": "This Circle entry must be persisted once.",
                }
            )

            # Both connected members should receive the same persisted entry.
            await sender_communicator.receive_json_from()
            await viewer_communicator.receive_json_from()

            @database_sync_to_async
            def persisted_entries():
                return list(
                    CircleBackNForth.objects.filter(
                        circle=self.circle,
                        message="This Circle entry must be persisted once.",
                    ).values_list("sender_id", flat=True)
                )

            sender_ids = await persisted_entries()

            self.assertEqual(
                sender_ids,
                [self.sender.pk],
                "One submitted Circle B&F entry must create exactly one "
                "database row, attributed to the authenticated sender.",
            )
        finally:
            await sender_communicator.disconnect()
            await viewer_communicator.disconnect()
