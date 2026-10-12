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
class CircleBackNForthSecurityTests(TransactionTestCase):
    def setUp(self):
        self.district, _ = Districts.objects.get_or_create(
            code="VT00",
            defaults={"name": "Vermont"},
        )

        self.member = User.objects.create_user(
            username="circle-member",
            password="local-test-password",
            is_active=True,
        )
        Users.objects.update_or_create(
            user=self.member,
            defaults={"district": self.district},
        )
        self.member_token = str(AccessToken.for_user(self.member))

        self.outsider = User.objects.create_user(
            username="circle-outsider",
            password="another-local-test-password",
            is_active=True,
        )
        Users.objects.update_or_create(
            user=self.outsider,
            defaults={"district": self.district},
        )
        self.outsider_token = str(AccessToken.for_user(self.outsider))

        self.circle = Group.objects.create(
            code="CBF01",
            district=self.district,
            invitation_code="1234567890",
            group_type=1,
        )

        GroupMember.objects.create(
            user=self.member,
            group=self.circle,
            is_member=True,
        )

    def application(self):
        return JWTAuthMiddleware(
            URLRouter(websocket_urlpatterns)
        )

    async def test_connection_without_access_token_is_rejected(self):
        communicator = WebsocketCommunicator(
            self.application(),
            f"/ws/{self.circle.code}/{self.member.username}/",
        )

        try:
            connected, _ = await communicator.connect()

            self.assertFalse(
                connected,
                "Circle B&F connections must reject unauthenticated users.",
            )
        finally:
            await communicator.disconnect()

    async def test_nonmember_with_valid_token_is_rejected(self):
        communicator = WebsocketCommunicator(
            self.application(),
            (
                f"/ws/{self.circle.code}/{self.outsider.username}/"
                f"?token={self.outsider_token}"
            ),
        )

        try:
            connected, _ = await communicator.connect()

            self.assertFalse(
                connected,
                "Circle B&F connections must reject users who are not "
                "accepted members of the Circle.",
            )
        finally:
            await communicator.disconnect()

    async def test_message_sender_is_authenticated_user_not_payload_username(self):
        communicator = WebsocketCommunicator(
            self.application(),
            (
                f"/ws/{self.circle.code}/{self.member.username}/"
                f"?token={self.member_token}"
            ),
        )

        try:
            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            # Consume the initial message-history page.
            await communicator.receive_json_from()

            await communicator.send_json_to(
                {
                    "sender": self.outsider.username,
                    "message": "This entry must belong to the signed-in member.",
                }
            )

            await communicator.receive_json_from()

            @database_sync_to_async
            def saved_sender_id():
                return CircleBackNForth.objects.get(
                    circle=self.circle,
                    message=(
                        "This entry must belong to the signed-in member."
                    ),
                ).sender_id

            self.assertEqual(
                await saved_sender_id(),
                self.member.pk,
                "Circle B&F must derive authorship from the authenticated "
                "WebSocket user, never from a client-supplied username.",
            )
        finally:
            await communicator.disconnect()
