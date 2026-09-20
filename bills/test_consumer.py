from channels.db import database_sync_to_async
from vote.models import Districts, Group, GroupMember, Users
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase, override_settings
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import AccessToken

from bills.models import Bill, BillVote
from api.jwt_middleware import JWTAuthMiddleware
from bills.routing import websocket_urlpatterns


@override_settings(
    CHANNEL_LAYERS={
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        },
    },
)
class BillWebSocketTests(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="bill-test-voter",
            password="local-test-password",
            is_active=True,
        )
        self.access_token = str(AccessToken.for_user(self.user))
        district, _ = Districts.objects.get_or_create(
            code="VT00",
            defaults={"name": "Vermont"},
        )
        Users.objects.update_or_create(
            user=self.user,
            defaults={"district": district},
        )
        self.other_user = User.objects.create_user(
            username="other-bill-voter",
            password="another-local-test-password",
            is_active=True,
        )
        Users.objects.update_or_create(
            user=self.other_user,
            defaults={"district": district},
        )
        circle = Group.objects.create(
            code="TST01",
            district=district,
            invitation_code="1234567890",
            group_type=1,
        )
        GroupMember.objects.create(
            user=self.user,
            group=circle,
            is_member=True,
        )
        GroupMember.objects.create(
            user=self.other_user,
            group=circle,
            is_member=True,
        )
        self.bill = Bill.objects.create(
            congress=119,
            number="6127",
            origin_chamber="House",
            origin_chamber_code="H",
            title="WebSocket test bill",
            bill_type="HR",
            congress_url="https://www.congress.gov/bill/119th-congress/house-bill/6127",
            latest_action_text="Introduced",
            text="Test bill text.",
        )
        BillVote.objects.create(
            bill=self.bill,
            voter=self.user,
            your_vote="Y",
        )
    async def test_connection_without_access_token_is_rejected(self):
        application = JWTAuthMiddleware(
            URLRouter(websocket_urlpatterns)
        )
        communicator = WebsocketCommunicator(
            application,
            "/ws/bill/6127/",
        )

        try:
            connected, _ = await communicator.connect()
            self.assertFalse(
                connected,
                "Bill connections must reject users without an access token.",
            )
        finally:
            await communicator.disconnect()
    async def test_valid_access_token_connects_and_receives_vote_counts(self):
        application = JWTAuthMiddleware(
            URLRouter(websocket_urlpatterns)
        )
        communicator = WebsocketCommunicator(
            application,
            f"/ws/bill/6127/?token={self.access_token}",
        )

        try:
            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            counts = await communicator.receive_json_from()
            self.assertEqual(
                counts,
                {
                    "yea_votes": 1,
                    "nay_votes": 0,
                    "present_votes": 0,
                    "proxy_votes": 0,
                },
            )
        finally:
            await communicator.disconnect()
    async def test_cannot_change_another_voters_vote(self):
        await database_sync_to_async(BillVote.objects.create)(
            bill=self.bill,
            voter=self.other_user,
            your_vote="Y",
        )

        application = JWTAuthMiddleware(
            URLRouter(websocket_urlpatterns)
        )
        communicator = WebsocketCommunicator(
            application,
            f"/ws/bill/6127/?token={self.access_token}",
        )

        try:
            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            # Consume the initial counts before sending the voting message.
            initial_counts = await communicator.receive_json_from()
            self.assertEqual(initial_counts["yea_votes"], 2)

            await communicator.send_json_to(
                {
                    "vote_type": "N",
                    "username": self.other_user.username,
                }
            )
            response = await communicator.receive_json_from()

            @database_sync_to_async
            def saved_votes():
                return dict(
                    BillVote.objects.filter(bill=self.bill).values_list(
                        "voter__username", "your_vote"
                    )
                )

            self.assertEqual(
                await saved_votes(),
                {
                    self.user.username: "Y",
                    self.other_user.username: "Y",
                },
                "A mismatched username must not change either user's vote.",
            )
            self.assertEqual(
                response,
                {"error": "You can only submit your own vote."},
            )
        finally:
            await communicator.disconnect()
    async def test_can_update_own_vote_and_receive_updated_counts(self):
        application = JWTAuthMiddleware(
            URLRouter(websocket_urlpatterns)
        )
        communicator = WebsocketCommunicator(
            application,
            f"/ws/bill/6127/?token={self.access_token}",
        )

        try:
            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            initial_counts = await communicator.receive_json_from()
            self.assertEqual(initial_counts["yea_votes"], 1)

            await communicator.send_json_to(
                {
                    "vote_type": "N",
                    "username": self.user.username,
                }
            )
            updated_counts = await communicator.receive_json_from()

            self.assertEqual(updated_counts["yea_votes"], 0)
            self.assertEqual(updated_counts["nay_votes"], 1)
            self.assertEqual(updated_counts["present_votes"], 0)
            self.assertEqual(updated_counts["proxy_votes"], 0)

            @database_sync_to_async
            def saved_votes():
                return list(
                    BillVote.objects.filter(bill=self.bill).values_list(
                        "voter_id", "your_vote"
                    )
                )

            self.assertEqual(
                await saved_votes(),
                [(self.user.pk, "N")],
            )
        finally:
            await communicator.disconnect()
