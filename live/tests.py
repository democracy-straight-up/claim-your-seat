import asyncio

from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import AnonymousUser, User
from django.test import TransactionTestCase, override_settings
from django.db import IntegrityError, transaction
from moda.models import (
    ModaBackNForthChat,
    ModaMembers,
    ModaModel,
    PutFarwardModaMember,
    VoteInModaMember,
    VoteOutModaMember,
)
from vote.models import Districts
from live.consumermoda import ModaConsumer


@override_settings(
    CHANNEL_LAYERS={
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        }
    }
)
class SecondLinkHousekeepingSecurityTests(TransactionTestCase):
    def test_anonymous_user_cannot_connect(self):
        async def scenario():
            communicator = WebsocketCommunicator(
                ModaConsumer.as_asgi(),
                "/moda/12345/anonymous",
            )
            communicator.scope["user"] = AnonymousUser()
            communicator.scope["url_route"] = {
                "kwargs": {
                    "moda_name": "12345",
                    "user_name": "anonymous",
                }
            }

            connected, _ = await communicator.connect()
            self.assertFalse(connected)

        asyncio.run(scenario())

    def test_authenticated_nonmember_cannot_connect(self):
        outsider = User.objects.create_user(
            username="outsider",
            password="test-password",
        )

        async def scenario():
            communicator = WebsocketCommunicator(
                ModaConsumer.as_asgi(),
                "/moda/12345/outsider",
            )
            communicator.scope["user"] = outsider
            communicator.scope["url_route"] = {
                "kwargs": {
                    "moda_name": "12345",
                    "user_name": "outsider",
                }
            }

            connected, _ = await communicator.connect()
            self.assertFalse(connected)

        asyncio.run(scenario())

    def test_accepted_member_can_connect(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )
        second_link = ModaModel.objects.create(district=district)

        member_user = User.objects.create_user(
            username="authorized_member",
            email="authorized_member@example.com",
        )
        member_user.users.district = district
        member_user.users.legalName = "Authorized Member"
        member_user.users.address = "1 Test Street"
        member_user.users.userType = "U3D2"
        member_user.users.save()

        ModaMembers.objects.create(
            user=member_user,
            moda=second_link,
            is_member=True,
        )

        async def scenario():
            communicator = WebsocketCommunicator(
                ModaConsumer.as_asgi(),
                f"/moda/{second_link.code}/{member_user.username}",
            )
            communicator.scope["user"] = member_user
            communicator.scope["url_route"] = {
                "kwargs": {
                    "moda_name": str(second_link.code),
                    "user_name": member_user.username,
                }
            }

            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            initial_message = await communicator.receive_json_from()
            self.assertEqual(initial_message["action"], "init")
            self.assertEqual(len(initial_message["member_list"]), 1)

            await communicator.disconnect()

        asyncio.run(scenario())

    def test_ordinary_member_cannot_vote_as_another_member(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )
        second_link = ModaModel.objects.create(district=district)

        def create_member(username, legal_name):
            user = User.objects.create_user(
                username=username,
                email=f"{username}@example.com",
            )
            user.users.district = district
            user.users.legalName = legal_name
            user.users.address = "1 Test Street"
            user.users.userType = "U3D2"
            user.users.save()

            membership = ModaMembers.objects.create(
                user=user,
                moda=second_link,
                is_member=True,
            )
            return user, membership

        bob, bob_membership = create_member(
            "proxy_bob", "Bob Smith"
        )
        alice, alice_membership = create_member(
            "proxy_alice", "Alice Morgan"
        )
        carlos, carlos_membership = create_member(
            "proxy_carlos", "Carlos Rivera"
        )

        # Alice is an ordinary member, not the delegate.
        self.assertFalse(alice_membership.is_delegate)

        async def scenario():
            communicator = WebsocketCommunicator(
                ModaConsumer.as_asgi(),
                f"/moda/{second_link.code}/{alice.username}",
            )
            communicator.scope["user"] = alice
            communicator.scope["url_route"] = {
                "kwargs": {
                    "moda_name": str(second_link.code),
                    "user_name": alice.username,
                }
            }

            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            # Consume the initial membership listing.
            await communicator.receive_json_from()

            # Alice attempts to cast Bob's expulsion vote.
            await communicator.send_json_to({
                "action": "vote_out",
                "payload": {
                    "voter": bob.username,
                    "member": carlos_membership.pk,
                },
            })

            response = await communicator.receive_json_from()

            self.assertEqual(response["status"], "error")
            self.assertEqual(response["action"], "vote_out")
            self.assertEqual(
                response["message"],
                "Not authorized to cast this vote.",
            )

            await communicator.disconnect()

        asyncio.run(scenario())

        # Bob's vote must not have been recorded.
        self.assertFalse(
            VoteOutModaMember.objects.filter(
                voter=bob,
                candidate=carlos_membership,
            ).exists()
        )
    def test_delegate_can_vote_on_behalf_of_member(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )
        second_link = ModaModel.objects.create(district=district)

        def create_member(username, legal_name):
            user = User.objects.create_user(
                username=username,
                email=f"{username}@example.com",
            )
            user.users.district = district
            user.users.legalName = legal_name
            user.users.address = "1 Test Street"
            user.users.userType = "U3D2"
            user.users.save()

            membership = ModaMembers.objects.create(
                user=user,
                moda=second_link,
                is_member=True,
            )
            return user, membership

        # The first accepted member becomes the delegate.
        alice, alice_membership = create_member(
            "delegate_alice", "Alice Morgan"
        )
        bob, _ = create_member(
            "delegate_bob", "Bob Smith"
        )
        _, carlos_membership = create_member(
            "delegate_carlos", "Carlos Rivera"
        )

        self.assertTrue(alice_membership.is_delegate)

        async def scenario():
            communicator = WebsocketCommunicator(
                ModaConsumer.as_asgi(),
                f"/moda/{second_link.code}/{alice.username}",
            )
            communicator.scope["user"] = alice
            communicator.scope["url_route"] = {
                "kwargs": {
                    "moda_name": str(second_link.code),
                    "user_name": alice.username,
                }
            }

            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            await communicator.receive_json_from()

            # Alice exercises Bob's Housekeeping vote.
            await communicator.send_json_to({
                "action": "vote_out",
                "payload": {
                    "voter": bob.username,
                    "member": carlos_membership.pk,
                },
            })

            response = await communicator.receive_json_from()

            self.assertEqual(
                response["action"]["status"],
                "success",
            )

            await communicator.disconnect()

        asyncio.run(scenario())

        # The vote belongs to Bob's voting position.
        self.assertEqual(
            VoteOutModaMember.objects.filter(
                voter=bob,
                candidate=carlos_membership,
            ).count(),
            1,
        )

        # One vote is insufficient to expel Carlos.
        self.assertTrue(
            ModaMembers.objects.filter(
                pk=carlos_membership.pk,
            ).exists()
        )
        vote = VoteOutModaMember.objects.get(
            voter=bob,
            candidate=carlos_membership,
        )

        self.assertEqual(vote.voter_id, bob.pk)
        self.assertEqual(vote.agent_id, alice.pk)
        announcements = list(
            ModaBackNForthChat.objects.filter(
                moda=second_link,
                is_system=True,
                message__startswith="Housekeeping: ",
            )
        )

        self.assertEqual(len(announcements), 1)
        self.assertIsNone(announcements[0].sender_id)

        self.assertEqual(
            announcements[0].message,
            "Housekeeping: Alice Morgan, acting as Bob Smith's agent, "
            "voted to expel Carlos Rivera. "
            "Current tally: 1 of 2 votes required.",
        )
        # Bob personally withdraws the vote Alice cast for him.
        async def bob_withdraws_vote():
            communicator = WebsocketCommunicator(
                ModaConsumer.as_asgi(),
                f"/moda/{second_link.code}/{bob.username}",
            )
            communicator.scope["user"] = bob
            communicator.scope["url_route"] = {
                "kwargs": {
                    "moda_name": str(second_link.code),
                    "user_name": bob.username,
                }
            }

            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            await communicator.receive_json_from()

            await communicator.send_json_to({
                "action": "undo_vote_out",
                "payload": {
                    "voter": bob.username,
                    "member": carlos_membership.pk,
                },
            })

            response = await communicator.receive_json_from()
            self.assertEqual(
                response["action"]["status"],
                "success",
            )

            await communicator.disconnect()

        asyncio.run(bob_withdraws_vote())

        # Bob's affirmative vote no longer exists.
        self.assertFalse(
            VoteOutModaMember.objects.filter(
                voter=bob,
                candidate=carlos_membership,
            ).exists()
        )

        # Both actions remain visible in Back & Forth.
        announcements = list(
            ModaBackNForthChat.objects.filter(
                moda=second_link,
                is_system=True,
                message__startswith="Housekeeping: ",
            ).order_by("pk")
        )

        self.assertEqual(
            [announcement.message for announcement in announcements],
            [
                "Housekeeping: Alice Morgan, acting as "
                "Bob Smith's agent, voted to expel Carlos Rivera. "
                "Current tally: 1 of 2 votes required.",
                "Housekeeping: Bob Smith withdrew Bob Smith's vote "
                "to expel Carlos Rivera. "
                "Current tally: 0 of 2 votes required.",
            ],
        )
        # Alice reasserts Bob's vote after Bob withdrew it.
        async def alice_reasserts_vote():
            communicator = WebsocketCommunicator(
                ModaConsumer.as_asgi(),
                f"/moda/{second_link.code}/{alice.username}",
            )
            communicator.scope["user"] = alice
            communicator.scope["url_route"] = {
                "kwargs": {
                    "moda_name": str(second_link.code),
                    "user_name": alice.username,
                }
            }

            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            await communicator.receive_json_from()

            await communicator.send_json_to({
                "action": "vote_out",
                "payload": {
                    "voter": bob.username,
                    "member": carlos_membership.pk,
                },
            })

            response = await communicator.receive_json_from()
            self.assertEqual(
                response["action"]["status"],
                "success",
            )

            await communicator.disconnect()

        asyncio.run(alice_reasserts_vote())

        # Bob has exactly one effective affirmative vote.
        votes = VoteOutModaMember.objects.filter(
            voter=bob,
            candidate=carlos_membership,
        )

        self.assertEqual(votes.count(), 1)
        self.assertEqual(votes.get().agent_id, alice.pk)

        # Back & Forth preserves all three actions.
        announcements = list(
            ModaBackNForthChat.objects.filter(
                moda=second_link,
                is_system=True,
                message__startswith="Housekeeping: ",
            ).order_by("pk")
        )

        self.assertEqual(
            [announcement.message for announcement in announcements],
            [
                "Housekeeping: Alice Morgan, acting as "
                "Bob Smith's agent, voted to expel Carlos Rivera. "
                "Current tally: 1 of 2 votes required.",
                "Housekeeping: Bob Smith withdrew Bob Smith's vote "
                "to expel Carlos Rivera. "
                "Current tally: 0 of 2 votes required.",
                "Housekeeping: Alice Morgan, acting as "
                "Bob Smith's agent, voted to expel Carlos Rivera. "
                "Current tally: 1 of 2 votes required.",
            ],
        )

    def test_ordinary_member_cannot_withdraw_another_members_vote(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )
        second_link = ModaModel.objects.create(district=district)

        def create_member(username):
            user = User.objects.create_user(
                username=username,
                email=f"{username}@example.com",
            )
            user.users.district = district
            user.users.legalName = username
            user.users.address = "1 Test Street"
            user.users.userType = "U3D2"
            user.users.save()

            membership = ModaMembers.objects.create(
                user=user,
                moda=second_link,
                is_member=True,
            )
            return user, membership

        # First member becomes the delegate.
        delegate, _ = create_member("withdraw_delegate")
        bob, _ = create_member("withdraw_bob")
        carol, carol_membership = create_member("withdraw_carol")
        _, carlos_membership = create_member("withdraw_carlos")

        self.assertFalse(carol_membership.is_delegate)

        # Bob has cast an affirmative vote against Carlos.
        vote = VoteOutModaMember.objects.create(
            voter=bob,
            agent=bob,
            candidate=carlos_membership,
            moda=second_link,
        )

        async def scenario():
            communicator = WebsocketCommunicator(
                ModaConsumer.as_asgi(),
                f"/moda/{second_link.code}/{carol.username}",
            )
            communicator.scope["user"] = carol
            communicator.scope["url_route"] = {
                "kwargs": {
                    "moda_name": str(second_link.code),
                    "user_name": carol.username,
                }
            }

            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            await communicator.receive_json_from()

            # Carol attempts to withdraw Bob's vote.
            await communicator.send_json_to({
                "action": "undo_vote_out",
                "payload": {
                    "voter": bob.username,
                    "member": carlos_membership.pk,
                },
            })

            response = await communicator.receive_json_from()

            self.assertEqual(response.get("status"), "error")

            await communicator.disconnect()

        asyncio.run(scenario())

        # Bob's affirmative vote must remain intact.
        self.assertTrue(
            VoteOutModaMember.objects.filter(pk=vote.pk).exists()
        )

    def test_delegate_can_withdraw_members_vote(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )
        second_link = ModaModel.objects.create(district=district)

        def create_member(username, legal_name):
            user = User.objects.create_user(
                username=username,
                email=f"{username}@example.com",
            )
            user.users.district = district
            user.users.legalName = legal_name
            user.users.address = "1 Test Street"
            user.users.userType = "U3D2"
            user.users.save()

            membership = ModaMembers.objects.create(
                user=user,
                moda=second_link,
                is_member=True,
            )
            return user, membership

        alice, alice_membership = create_member(
            "withdraw_agent_alice", "Alice Morgan"
        )
        bob, _ = create_member(
            "withdraw_agent_bob", "Bob Smith"
        )
        _, carlos_membership = create_member(
            "withdraw_agent_carlos", "Carlos Rivera"
        )

        self.assertTrue(alice_membership.is_delegate)

        # Bob has voted to expel Carlos.
        vote = VoteOutModaMember.objects.create(
            voter=bob,
            agent=bob,
            candidate=carlos_membership,
            moda=second_link,
        )

        async def scenario():
            communicator = WebsocketCommunicator(
                ModaConsumer.as_asgi(),
                f"/moda/{second_link.code}/{alice.username}",
            )
            communicator.scope["user"] = alice
            communicator.scope["url_route"] = {
                "kwargs": {
                    "moda_name": str(second_link.code),
                    "user_name": alice.username,
                }
            }

            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            await communicator.receive_json_from()

            # Alice withdraws Bob's vote as his agent.
            await communicator.send_json_to({
                "action": "undo_vote_out",
                "payload": {
                    "voter": bob.username,
                    "member": carlos_membership.pk,
                },
            })

            response = await communicator.receive_json_from()
            self.assertEqual(
                response["action"]["status"],
                "success",
            )

            await communicator.disconnect()

        asyncio.run(scenario())

        self.assertFalse(
            VoteOutModaMember.objects.filter(
                pk=vote.pk,
            ).exists()
        )

        # Carlos remains a member.
        self.assertTrue(
            ModaMembers.objects.filter(
                pk=carlos_membership.pk,
            ).exists()
        )
        announcements = list(
            ModaBackNForthChat.objects.filter(
                moda=second_link,
                is_system=True,
                message__startswith="Housekeeping: ",
            )
        )

        self.assertEqual(len(announcements), 1)
        self.assertIsNone(announcements[0].sender_id)

        self.assertEqual(
            announcements[0].message,
            "Housekeeping: Alice Morgan, acting as Bob Smith's agent, "
            "withdrew Bob Smith's vote to expel Carlos Rivera. "
            "Current tally: 0 of 2 votes required.",
        )

    def test_decisive_delegated_vote_announces_removal(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )
        second_link = ModaModel.objects.create(district=district)

        def create_member(username, legal_name):
            user = User.objects.create_user(
                username=username,
                email=f"{username}@example.com",
            )
            user.users.district = district
            user.users.legalName = legal_name
            user.users.address = "1 Test Street"
            user.users.userType = "U3D2"
            user.users.save()

            membership = ModaMembers.objects.create(
                user=user,
                moda=second_link,
                is_member=True,
            )
            return user, membership

        alice, alice_membership = create_member(
            "decisive_alice", "Alice Morgan"
        )
        bob, _ = create_member(
            "decisive_bob", "Bob Smith"
        )
        _, carlos_membership = create_member(
            "decisive_carlos", "Carlos Rivera"
        )

        self.assertTrue(alice_membership.is_delegate)

        # Alice's personal vote already exists.
        # One vote is not enough to expel Carlos.
        VoteOutModaMember.objects.create(
            voter=alice,
            agent=alice,
            candidate=carlos_membership,
            moda=second_link,
        )

        carlos_pk = carlos_membership.pk

        async def scenario():
            communicator = WebsocketCommunicator(
                ModaConsumer.as_asgi(),
                f"/moda/{second_link.code}/{alice.username}",
            )
            communicator.scope["user"] = alice
            communicator.scope["url_route"] = {
                "kwargs": {
                    "moda_name": str(second_link.code),
                    "user_name": alice.username,
                }
            }

            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            await communicator.receive_json_from()

            # Alice casts Bob's deciding vote.
            await communicator.send_json_to({
                "action": "vote_out",
                "payload": {
                    "voter": bob.username,
                    "member": carlos_pk,
                },
            })

            response = await communicator.receive_json_from()
            self.assertEqual(
                response["action"]["status"],
                "success",
            )

            await communicator.disconnect()

        asyncio.run(scenario())

        # Carlos has been expelled.
        self.assertFalse(
            ModaMembers.objects.filter(pk=carlos_pk).exists()
        )

        # Both the vote and its consequence are recorded.
        announcements = list(
            ModaBackNForthChat.objects.filter(
                moda=second_link,
                is_system=True,
                message__startswith="Housekeeping: ",
            ).order_by("pk")
        )

        self.assertEqual(
            [announcement.message for announcement in announcements],
            [
                "Housekeeping: Alice Morgan, acting as "
                "Bob Smith's agent, voted to expel Carlos Rivera. "
                "Current tally: 2 of 2 votes required.",
                "Housekeeping: Carlos Rivera was removed from "
                "the Second Link after receiving the required majority.",
            ],
        )

    def test_ordinary_member_cannot_unilaterally_remove_member(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )
        second_link = ModaModel.objects.create(district=district)

        def create_member(username):
            user = User.objects.create_user(
                username=username,
                email=f"{username}@example.com",
            )
            user.users.district = district
            user.users.legalName = username
            user.users.address = "1 Test Street"
            user.users.userType = "U3D2"
            user.users.save()

            membership = ModaMembers.objects.create(
                user=user,
                moda=second_link,
                is_member=True,
            )
            return user, membership

        delegate, _ = create_member("direct_removal_delegate")
        alice, alice_membership = create_member("direct_removal_alice")
        bob, bob_membership = create_member("direct_removal_bob")

        self.assertFalse(alice_membership.is_delegate)

        async def scenario():
            communicator = WebsocketCommunicator(
                ModaConsumer.as_asgi(),
                f"/moda/{second_link.code}/{alice.username}",
            )
            communicator.scope["user"] = alice
            communicator.scope["url_route"] = {
                "kwargs": {
                    "moda_name": str(second_link.code),
                    "user_name": alice.username,
                }
            }

            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            await communicator.receive_json_from()

            # Ordinary member Alice tries to remove Bob directly.
            await communicator.send_json_to({
                "action": "remove_candidate",
                "remover": alice.username,
                "candidate": bob_membership.pk,
            })

            await communicator.receive_json_from()
            await communicator.disconnect()

        asyncio.run(scenario())

        # Alice must not be able to remove Bob unilaterally.
        self.assertTrue(
            ModaMembers.objects.filter(
                pk=bob_membership.pk,
            ).exists()
        )

    def test_delegate_direct_removal_compacts_succession(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )
        second_link = ModaModel.objects.create(district=district)

        def create_member(username, legal_name):
            user = User.objects.create_user(
                username=username,
                email=f"{username}@example.com",
            )
            user.users.district = district
            user.users.legalName = legal_name
            user.users.address = "1 Test Street"
            user.users.userType = "U3D2"
            user.users.save()

            membership = ModaMembers.objects.create(
                user=user,
                moda=second_link,
                is_member=True,
            )
            return user, membership

        alice, alice_membership = create_member(
            "direct_agent_alice", "Alice Morgan"
        )
        bob, bob_membership = create_member(
            "direct_agent_bob", "Bob Smith"
        )
        carol, carol_membership = create_member(
            "direct_agent_carol", "Carol Jones"
        )

        self.assertTrue(alice_membership.is_delegate)
        self.assertEqual(bob_membership.succession_position, 1)
        self.assertEqual(carol_membership.succession_position, 2)

        async def scenario():
            communicator = WebsocketCommunicator(
                ModaConsumer.as_asgi(),
                f"/moda/{second_link.code}/{alice.username}",
            )
            communicator.scope["user"] = alice
            communicator.scope["url_route"] = {
                "kwargs": {
                    "moda_name": str(second_link.code),
                    "user_name": alice.username,
                }
            }

            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            await communicator.receive_json_from()

            # Alice removes Bob using her delegate authority.
            await communicator.send_json_to({
                "action": "remove_candidate",
                "remover": alice.username,
                "candidate": bob_membership.pk,
            })

            response = await communicator.receive_json_from()
            self.assertEqual(response["status"], "success")

            await communicator.disconnect()

        asyncio.run(scenario())

        self.assertFalse(
            ModaMembers.objects.filter(
                pk=bob_membership.pk,
            ).exists()
        )

        alice_membership.refresh_from_db()
        carol_membership.refresh_from_db()

        self.assertTrue(alice_membership.is_delegate)
        self.assertEqual(alice_membership.succession_position, 0)
        self.assertEqual(carol_membership.succession_position, 1)

        bob.users.refresh_from_db()
        self.assertEqual(bob.users.userType, "U2D2")

        # Housekeeping records the delegate's action.
        housekeeping_messages = list(
            ModaBackNForthChat.objects.filter(
                moda=second_link,
                is_system=True,
                message__startswith="Housekeeping: ",
            ).order_by("pk")
        )

        self.assertEqual(len(housekeeping_messages), 1)
        self.assertIsNone(housekeeping_messages[0].sender_id)

        self.assertEqual(
            housekeeping_messages[0].message,
            "Housekeeping: Alice Morgan, acting on behalf of "
            "Bob Smith, ended Bob Smith's membership "
            "in the Second Link.",
        )

        # Back & Forth also records the succession change.
        succession_messages = list(
            ModaBackNForthChat.objects.filter(
                moda=second_link,
                is_system=True,
                message__startswith="Succession update: ",
            ).order_by("pk")
        )

        self.assertEqual(len(succession_messages), 1)
        self.assertIsNone(succession_messages[0].sender_id)

        self.assertEqual(
            succession_messages[0].message,
            "Succession update: Carol Jones moved from "
            "position 2 to position 1 after "
            "Bob Smith was removed.",
        )

    def test_ordinary_member_cannot_dissolve_second_link(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )
        second_link = ModaModel.objects.create(district=district)

        def create_member(username, legal_name):
            user = User.objects.create_user(
                username=username,
                email=f"{username}@example.com",
            )
            user.users.district = district
            user.users.legalName = legal_name
            user.users.address = "1 Test Street"
            user.users.userType = "U3D2"
            user.users.save()

            membership = ModaMembers.objects.create(
                user=user,
                moda=second_link,
                is_member=True,
            )
            return user, membership

        alice, alice_membership = create_member(
            "dissolve_delegate_alice", "Alice Morgan"
        )
        bob, bob_membership = create_member(
            "dissolve_member_bob", "Bob Smith"
        )

        self.assertTrue(alice_membership.is_delegate)
        self.assertFalse(bob_membership.is_delegate)

        second_link_pk = second_link.pk

        async def scenario():
            communicator = WebsocketCommunicator(
                ModaConsumer.as_asgi(),
                f"/moda/{second_link.code}/{bob.username}",
            )
            communicator.scope["user"] = bob
            communicator.scope["url_route"] = {
                "kwargs": {
                    "moda_name": str(second_link.code),
                    "user_name": bob.username,
                }
            }

            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            await communicator.receive_json_from()

            # Bob attempts to dissolve the group.
            await communicator.send_json_to({
                "action": "dissolve",
                "payload": {
                    "voter": bob.username,
                    "member": bob_membership.pk,
                },
            })

            response = await communicator.receive_json_from()

            self.assertEqual(response["status"], "error")

            await communicator.disconnect()

        asyncio.run(scenario())

        # Unauthorized dissolution must have no effect.
        self.assertTrue(
            ModaModel.objects.filter(pk=second_link_pk).exists()
        )

        self.assertTrue(
            ModaMembers.objects.filter(
                pk=alice_membership.pk,
            ).exists()
        )

        self.assertTrue(
            ModaMembers.objects.filter(
                pk=bob_membership.pk,
            ).exists()
        )

    def test_sole_delegate_can_dissolve_second_link(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )
        second_link = ModaModel.objects.create(
            district=district,
        )

        alice = User.objects.create_user(
            username="sole_dissolution_alice",
            email="sole_dissolution_alice@example.com",
        )
        alice.users.district = district
        alice.users.legalName = "Alice Morgan"
        alice.users.address = "1 Test Street"
        alice.users.userType = "U3D2"
        alice.users.save()

        membership = ModaMembers.objects.create(
            user=alice,
            moda=second_link,
            is_member=True,
        )

        self.assertTrue(membership.is_delegate)

        self.assertEqual(
            ModaMembers.objects.filter(
                moda=second_link,
                is_member=True,
            ).count(),
            1,
        )

        second_link_pk = second_link.pk
        membership_pk = membership.pk

        async def scenario():
            communicator = WebsocketCommunicator(
                ModaConsumer.as_asgi(),
                f"/moda/{second_link.code}/{alice.username}",
            )
            communicator.scope["user"] = alice
            communicator.scope["url_route"] = {
                "kwargs": {
                    "moda_name": str(second_link.code),
                    "user_name": alice.username,
                }
            }

            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            await communicator.receive_json_from()

            await communicator.send_json_to({
                "action": "dissolve",
                "payload": {
                    "voter": alice.username,
                    "member": membership_pk,
                },
            })

            response = await communicator.receive_json_from()

            self.assertEqual(response["status"], "success")
            self.assertEqual(response["action"], "dissolve")

            await communicator.disconnect()

        asyncio.run(scenario())

        # The Second Link no longer exists.
        self.assertFalse(
            ModaModel.objects.filter(
                pk=second_link_pk,
            ).exists()
        )

        # Alice's membership has been removed.
        self.assertFalse(
            ModaMembers.objects.filter(
                pk=membership_pk,
            ).exists()
        )

        # Alice retains her underlying Second Delegate mandate.
        alice.users.refresh_from_db()
        self.assertEqual(alice.users.userType, "U2D2")

    def test_delegate_cannot_dissolve_with_other_members(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )
        second_link = ModaModel.objects.create(
            district=district,
        )

        def create_member(username, legal_name):
            user = User.objects.create_user(
                username=username,
                email=f"{username}@example.com",
            )
            user.users.district = district
            user.users.legalName = legal_name
            user.users.address = "1 Test Street"
            user.users.userType = "U3D2"
            user.users.save()

            membership = ModaMembers.objects.create(
                user=user,
                moda=second_link,
                is_member=True,
            )
            return user, membership

        alice, alice_membership = create_member(
            "blocked_dissolve_alice", "Alice Morgan"
        )
        bob, bob_membership = create_member(
            "blocked_dissolve_bob", "Bob Smith"
        )

        self.assertTrue(alice_membership.is_delegate)

        async def scenario():
            communicator = WebsocketCommunicator(
                ModaConsumer.as_asgi(),
                f"/moda/{second_link.code}/{alice.username}",
            )
            communicator.scope["user"] = alice
            communicator.scope["url_route"] = {
                "kwargs": {
                    "moda_name": str(second_link.code),
                    "user_name": alice.username,
                }
            }

            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            await communicator.receive_json_from()

            await communicator.send_json_to({
                "action": "dissolve",
                "payload": {
                    "voter": alice.username,
                    "member": alice_membership.pk,
                },
            })

            response = await communicator.receive_json_from()

            self.assertEqual(response["status"], "error")
            self.assertEqual(response["action"], "dissolve")
            self.assertEqual(
                response["message"],
                "The Second Link cannot be dissolved "
                "while other accepted members remain.",
            )

            await communicator.disconnect()

        asyncio.run(scenario())

        # The Second Link and both memberships still exist.
        self.assertTrue(
            ModaModel.objects.filter(
                pk=second_link.pk,
            ).exists()
        )
        self.assertTrue(
            ModaMembers.objects.filter(
                pk=alice_membership.pk,
            ).exists()
        )
        self.assertTrue(
            ModaMembers.objects.filter(
                pk=bob_membership.pk,
            ).exists()
        )

        alice_membership.refresh_from_db()
        self.assertTrue(alice_membership.is_delegate)
        self.assertEqual(
            alice_membership.succession_position,
            0,
        )
    def test_member_cannot_vote_out_member_of_another_second_link(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )

        first_group = ModaModel.objects.create(district=district)
        other_group = ModaModel.objects.create(district=district)

        def create_member(username, group):
            user = User.objects.create_user(
                username=username,
                email=f"{username}@example.com",
            )
            user.users.district = district
            user.users.legalName = username
            user.users.address = "1 Test Street"
            user.users.userType = "U3D2"
            user.users.save()

            membership = ModaMembers.objects.create(
                user=user,
                moda=group,
                is_member=True,
            )
            return user, membership

        # Alice belongs only to the first Second Link.
        alice, alice_membership = create_member(
            "cross_group_alice",
            first_group,
        )

        # Carlos belongs to a different Second Link.
        create_member("cross_group_bob", other_group)
        carlos, carlos_membership = create_member(
            "cross_group_carlos",
            other_group,
        )
        create_member("cross_group_carol", other_group)

        self.assertTrue(alice_membership.is_delegate)

        async def scenario():
            communicator = WebsocketCommunicator(
                ModaConsumer.as_asgi(),
                f"/moda/{first_group.code}/{alice.username}",
            )
            communicator.scope["user"] = alice
            communicator.scope["url_route"] = {
                "kwargs": {
                    "moda_name": str(first_group.code),
                    "user_name": alice.username,
                }
            }

            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            await communicator.receive_json_from()

            # Alice attempts to vote out Carlos,
            # who belongs to another Second Link.
            await communicator.send_json_to({
                "action": "vote_out",
                "payload": {
                    "voter": alice.username,
                    "member": carlos_membership.pk,
                },
            })

            response = await communicator.receive_json_from()
            self.assertEqual(response["status"], "error")

            await communicator.disconnect()

        asyncio.run(scenario())

        # No cross-group vote may be recorded.
        self.assertFalse(
            VoteOutModaMember.objects.filter(
                voter=alice,
                candidate=carlos_membership,
            ).exists()
        )

        # Carlos remains an accepted member of his group.
        carlos_membership.refresh_from_db()
        self.assertTrue(carlos_membership.is_member)

    def test_ordinary_member_cannot_cast_another_members_admission_vote(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )
        second_link = ModaModel.objects.create(district=district)

        def create_user(username, legal_name):
            user = User.objects.create_user(
                username=username,
                email=f"{username}@example.com",
            )
            user.users.district = district
            user.users.legalName = legal_name
            user.users.address = "1 Test Street"
            user.users.userType = "U3D2"
            user.users.save()
            return user

        alice = create_user("admission_alice", "Alice Morgan")
        bob = create_user("admission_bob", "Bob Smith")
        carol = create_user("admission_carol", "Carol Jones")
        dana = create_user("admission_dana", "Dana Rivera")

        alice_membership = ModaMembers.objects.create(
            user=alice,
            moda=second_link,
            is_member=True,
        )
        ModaMembers.objects.create(
            user=bob,
            moda=second_link,
            is_member=True,
        )
        carol_membership = ModaMembers.objects.create(
            user=carol,
            moda=second_link,
            is_member=True,
        )
        dana_membership = ModaMembers.objects.create(
            user=dana,
            moda=second_link,
            is_member=False,
        )

        self.assertTrue(alice_membership.is_delegate)
        self.assertFalse(carol_membership.is_delegate)

        async def scenario():
            communicator = WebsocketCommunicator(
                ModaConsumer.as_asgi(),
                f"/moda/{second_link.code}/{carol.username}",
            )
            communicator.scope["user"] = carol
            communicator.scope["url_route"] = {
                "kwargs": {
                    "moda_name": str(second_link.code),
                    "user_name": carol.username,
                }
            }

            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            await communicator.receive_json_from()

            # Carol attempts to vote on Bob's behalf.
            await communicator.send_json_to({
                "action": "vote_in",
                "payload": {
                    "voter": bob.username,
                    "candidate": dana_membership.pk,
                },
            })

            await communicator.receive_json_from()
            await communicator.disconnect()

        asyncio.run(scenario())

        # Carol must not be able to exercise Bob's vote.
        self.assertFalse(
            VoteInModaMember.objects.filter(
                voter=bob,
                candidate=dana_membership,
            ).exists()
        )

        # Dana must remain a candidate.
        dana_membership.refresh_from_db()
        self.assertFalse(dana_membership.is_member)

    def test_delegate_can_cast_members_admission_vote(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )
        second_link = ModaModel.objects.create(district=district)

        def create_user(username):
            user = User.objects.create_user(
                username=username,
                email=f"{username}@example.com",
            )
            user.users.district = district
            user.users.legalName = username
            user.users.address = "1 Test Street"
            user.users.userType = "U3D2"
            user.users.save()
            return user

        alice = create_user("admit_delegate_alice")
        bob = create_user("admit_delegate_bob")
        dana = create_user("admit_candidate_dana")

        alice_membership = ModaMembers.objects.create(
            user=alice,
            moda=second_link,
            is_member=True,
        )
        ModaMembers.objects.create(
            user=bob,
            moda=second_link,
            is_member=True,
        )
        dana_membership = ModaMembers.objects.create(
            user=dana,
            moda=second_link,
            is_member=False,
        )

        self.assertTrue(alice_membership.is_delegate)

        async def scenario():
            communicator = WebsocketCommunicator(
                ModaConsumer.as_asgi(),
                f"/moda/{second_link.code}/{alice.username}",
            )
            communicator.scope["user"] = alice
            communicator.scope["url_route"] = {
                "kwargs": {
                    "moda_name": str(second_link.code),
                    "user_name": alice.username,
                }
            }

            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            await communicator.receive_json_from()

            # Alice exercises Bob's admission vote.
            await communicator.send_json_to({
                "action": "vote_in",
                "payload": {
                    "voter": bob.username,
                    "candidate": dana_membership.pk,
                },
            })

            response = await communicator.receive_json_from()

            self.assertEqual(
                response["action"]["status"],
                "success",
            )

            await communicator.disconnect()

        asyncio.run(scenario())

        # The effective vote belongs to Bob, not Alice.
        self.assertEqual(
            VoteInModaMember.objects.filter(
                voter=bob,
                candidate=dana_membership,
                moda=second_link,
            ).count(),
            1,
        )

        self.assertFalse(
            VoteInModaMember.objects.filter(
                voter=alice,
                candidate=dana_membership,
                moda=second_link,
            ).exists()
        )

        # One affirmative vote does not yet establish a majority.
        dana_membership.refresh_from_db()
        self.assertFalse(dana_membership.is_member)

        # Alice must be recorded as the person who
        # exercised Bob's effective vote.
        effective_vote = VoteInModaMember.objects.get(
            voter=bob,
            candidate=dana_membership,
            moda=second_link,
        )

        self.assertEqual(
            getattr(effective_vote, "agent_id", None),
            alice.pk,
        )

        # The action must also be announced in Back & Forth.
        announcements = list(
            ModaBackNForthChat.objects.filter(
                moda=second_link,
                is_system=True,
                sender__isnull=True,
                message__startswith="Housekeeping: ",
            )
        )

        self.assertEqual(len(announcements), 1)

        announcement = announcements[0]
        self.assertIn(alice.username, announcement.message)
        self.assertIn(bob.username, announcement.message)
        self.assertIn(dana.username, announcement.message)
        self.assertIn("1 of 2", announcement.message)

    def test_delegate_can_withdraw_members_admission_vote(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )
        second_link = ModaModel.objects.create(district=district)

        def create_user(username):
            user = User.objects.create_user(
                username=username,
                email=f"{username}@example.com",
            )
            user.users.district = district
            user.users.legalName = username
            user.users.address = "1 Test Street"
            user.users.userType = "U3D2"
            user.users.save()
            return user

        alice = create_user("withdraw_admit_alice")
        bob = create_user("withdraw_admit_bob")
        dana = create_user("withdraw_admit_dana")

        alice_membership = ModaMembers.objects.create(
            user=alice,
            moda=second_link,
            is_member=True,
        )
        ModaMembers.objects.create(
            user=bob,
            moda=second_link,
            is_member=True,
        )
        dana_membership = ModaMembers.objects.create(
            user=dana,
            moda=second_link,
            is_member=False,
        )

        self.assertTrue(alice_membership.is_delegate)

        async def scenario():
            communicator = WebsocketCommunicator(
                ModaConsumer.as_asgi(),
                f"/moda/{second_link.code}/{alice.username}",
            )
            communicator.scope["user"] = alice
            communicator.scope["url_route"] = {
                "kwargs": {
                    "moda_name": str(second_link.code),
                    "user_name": alice.username,
                }
            }

            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            await communicator.receive_json_from()

            # Alice casts Bob's affirmative admission vote.
            await communicator.send_json_to({
                "action": "vote_in",
                "payload": {
                    "voter": bob.username,
                    "candidate": dana_membership.pk,
                },
            })

            response = await communicator.receive_json_from()
            self.assertEqual(
                response["action"]["status"],
                "success",
            )

            # Alice now withdraws Bob's effective vote.
            await communicator.send_json_to({
                "action": "undo_vote_in",
                "payload": {
                    "voter": bob.username,
                    "candidate": dana_membership.pk,
                },
            })

            # No response is awaited because the withdrawal
            # action has not yet been implemented.
            await communicator.disconnect()

        asyncio.run(scenario())

        # Bob's effective vote must be gone.
        self.assertFalse(
            VoteInModaMember.objects.filter(
                voter=bob,
                candidate=dana_membership,
                moda=second_link,
            ).exists()
        )

        # Dana must still be an applicant.
        dana_membership.refresh_from_db()
        self.assertFalse(dana_membership.is_member)

        # Both actions must appear in Back & Forth.
        announcements = list(
            ModaBackNForthChat.objects.filter(
                moda=second_link,
                is_system=True,
                sender__isnull=True,
                message__startswith="Housekeeping: ",
            ).order_by("pk")
        )

        self.assertEqual(len(announcements), 2)

        withdrawal = announcements[1].message
        self.assertIn(alice.username, withdrawal)
        self.assertIn(bob.username, withdrawal)
        self.assertIn(dana.username, withdrawal)
        self.assertIn("withdrew", withdrawal)
        self.assertIn("0 of 2", withdrawal)

    def test_ordinary_member_cannot_withdraw_anothers_admission_vote(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )
        second_link = ModaModel.objects.create(district=district)

        def create_user(username):
            user = User.objects.create_user(
                username=username,
                email=f"{username}@example.com",
            )
            user.users.district = district
            user.users.legalName = username
            user.users.address = "1 Test Street"
            user.users.userType = "U3D2"
            user.users.save()
            return user

        alice = create_user("undo_security_alice")
        bob = create_user("undo_security_bob")
        carol = create_user("undo_security_carol")
        dana = create_user("undo_security_dana")

        alice_membership = ModaMembers.objects.create(
            user=alice,
            moda=second_link,
            is_member=True,
        )
        ModaMembers.objects.create(
            user=bob,
            moda=second_link,
            is_member=True,
        )
        carol_membership = ModaMembers.objects.create(
            user=carol,
            moda=second_link,
            is_member=True,
        )
        dana_membership = ModaMembers.objects.create(
            user=dana,
            moda=second_link,
            is_member=False,
        )

        self.assertTrue(alice_membership.is_delegate)
        self.assertFalse(carol_membership.is_delegate)

        # Alice has already cast Bob's admission vote.
        vote = VoteInModaMember.objects.create(
            voter=bob,
            candidate=dana_membership,
            moda=second_link,
            agent=alice,
        )

        async def scenario():
            communicator = WebsocketCommunicator(
                ModaConsumer.as_asgi(),
                f"/moda/{second_link.code}/{carol.username}",
            )
            communicator.scope["user"] = carol
            communicator.scope["url_route"] = {
                "kwargs": {
                    "moda_name": str(second_link.code),
                    "user_name": carol.username,
                }
            }

            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            await communicator.receive_json_from()

            # Carol attempts to withdraw Bob's vote.
            await communicator.send_json_to({
                "action": "undo_vote_in",
                "payload": {
                    "voter": bob.username,
                    "candidate": dana_membership.pk,
                },
            })

            await communicator.receive_json_from()
            await communicator.disconnect()

        asyncio.run(scenario())

        # Bob's effective vote must remain unchanged.
        self.assertTrue(
            VoteInModaMember.objects.filter(
                pk=vote.pk,
                voter=bob,
                agent=alice,
            ).exists()
        )

        # Dana remains a candidate.
        dana_membership.refresh_from_db()
        self.assertFalse(dana_membership.is_member)

        # No unauthorized Housekeeping announcement.
        self.assertFalse(
            ModaBackNForthChat.objects.filter(
                moda=second_link,
                is_system=True,
                message__startswith="Housekeeping: ",
            ).exists()
        )

    def test_cannot_withdraw_admission_vote_from_another_second_link(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )

        first_link = ModaModel.objects.create(district=district)
        other_link = ModaModel.objects.create(district=district)

        def create_user(username):
            user = User.objects.create_user(
                username=username,
                email=f"{username}@example.com",
            )
            user.users.district = district
            user.users.legalName = username
            user.users.address = "1 Test Street"
            user.users.userType = "U3D2"
            user.users.save()
            return user

        alice = create_user("cross_undo_alice")
        bob = create_user("cross_undo_bob")
        carol = create_user("cross_undo_carol")
        erin = create_user("cross_undo_erin")
        dana = create_user("cross_undo_dana")

        alice_membership = ModaMembers.objects.create(
            user=alice,
            moda=first_link,
            is_member=True,
        )
        ModaMembers.objects.create(
            user=bob,
            moda=other_link,
            is_member=True,
        )
        ModaMembers.objects.create(
            user=carol,
            moda=other_link,
            is_member=True,
        )
        ModaMembers.objects.create(
            user=erin,
            moda=other_link,
            is_member=True,
        )
        dana_membership = ModaMembers.objects.create(
            user=dana,
            moda=other_link,
            is_member=False,
        )

        self.assertTrue(alice_membership.is_delegate)

        # Bob has an effective admission vote in the other Link.
        vote = VoteInModaMember.objects.create(
            voter=bob,
            candidate=dana_membership,
            moda=other_link,
            agent=bob,
        )
        dana_membership.refresh_from_db()
        self.assertFalse(dana_membership.is_member)
        async def scenario():
            communicator = WebsocketCommunicator(
                ModaConsumer.as_asgi(),
                f"/moda/{first_link.code}/{alice.username}",
            )
            communicator.scope["user"] = alice
            communicator.scope["url_route"] = {
                "kwargs": {
                    "moda_name": str(first_link.code),
                    "user_name": alice.username,
                }
            }

            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            await communicator.receive_json_from()

            # Alice attempts to withdraw a vote in another Link.
            await communicator.send_json_to({
                "action": "undo_vote_in",
                "payload": {
                    "voter": bob.username,
                    "candidate": dana_membership.pk,
                },
            })

            await communicator.receive_json_from()
            await communicator.disconnect()

        asyncio.run(scenario())

        # Bob's vote must remain intact.
        self.assertTrue(
            VoteInModaMember.objects.filter(
                pk=vote.pk,
                voter=bob,
                moda=other_link,
            ).exists()
        )

        # Dana remains an applicant.
        dana_membership.refresh_from_db()
        self.assertFalse(dana_membership.is_member)

        # No Housekeeping announcement may be generated.
        self.assertFalse(
            ModaBackNForthChat.objects.filter(
                moda__in=[first_link, other_link],
                is_system=True,
                message__startswith="Housekeeping: ",
            ).exists()
        )

    def test_ordinary_member_cannot_cast_anothers_replacement_vote(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )
        second_link = ModaModel.objects.create(district=district)

        def create_member(username):
            user = User.objects.create_user(
                username=username,
                email=f"{username}@example.com",
            )
            user.users.district = district
            user.users.legalName = username
            user.users.address = "1 Test Street"
            user.users.userType = "U3D2"
            user.users.save()

            membership = ModaMembers.objects.create(
                user=user,
                moda=second_link,
                is_member=True,
            )
            return user, membership

        alice, alice_membership = create_member("replace_alice")
        bob, bob_membership = create_member("replace_bob")
        carol, carol_membership = create_member("replace_carol")

        self.assertTrue(alice_membership.is_delegate)
        self.assertFalse(carol_membership.is_delegate)

        async def scenario():
            communicator = WebsocketCommunicator(
                ModaConsumer.as_asgi(),
                f"/moda/{second_link.code}/{carol.username}",
            )
            communicator.scope["user"] = carol
            communicator.scope["url_route"] = {
                "kwargs": {
                    "moda_name": str(second_link.code),
                    "user_name": carol.username,
                }
            }

            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            await communicator.receive_json_from()

            # Carol attempts to exercise Bob's vote
            # to make Carol the Caucus Delegate.
            await communicator.send_json_to({
                "action": "putForward",
                "payload": {
                    "voter": bob.username,
                    "member": carol_membership.pk,
                },
            })

            await communicator.receive_json_from()
            await communicator.disconnect()

        asyncio.run(scenario())

        # Bob must not acquire an unauthorized effective vote.
        self.assertFalse(
            PutFarwardModaMember.objects.filter(
                voter=bob,
                candidate=carol_membership,
                moda=second_link,
            ).exists()
        )

        # Alice remains the Caucus Delegate.
        alice_membership.refresh_from_db()
        self.assertTrue(alice_membership.is_delegate)
    def test_delegate_can_cast_members_replacement_vote(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )
        second_link = ModaModel.objects.create(district=district)

        def create_member(username):
            user = User.objects.create_user(
                username=username,
                email=f"{username}@example.com",
            )
            user.users.district = district
            user.users.legalName = username
            user.users.address = "1 Test Street"
            user.users.userType = "U3D2"
            user.users.save()

            membership = ModaMembers.objects.create(
                user=user,
                moda=second_link,
                is_member=True,
            )
            return user, membership

        alice, alice_membership = create_member("forward_delegate_alice")
        bob, bob_membership = create_member("forward_delegate_bob")
        carol, carol_membership = create_member("forward_delegate_carol")

        self.assertTrue(alice_membership.is_delegate)

        async def scenario():
            communicator = WebsocketCommunicator(
                ModaConsumer.as_asgi(),
                f"/moda/{second_link.code}/{alice.username}",
            )
            communicator.scope["user"] = alice
            communicator.scope["url_route"] = {
                "kwargs": {
                    "moda_name": str(second_link.code),
                    "user_name": alice.username,
                }
            }

            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            await communicator.receive_json_from()

            # Alice exercises Bob's vote for Carol.
            await communicator.send_json_to({
                "action": "putForward",
                "payload": {
                    "voter": bob.username,
                    "member": carol_membership.pk,
                },
            })

            await communicator.receive_json_from()
            await communicator.disconnect()

        asyncio.run(scenario())

        # The effective vote belongs to Bob.
        self.assertEqual(
            PutFarwardModaMember.objects.filter(
                voter=bob,
                candidate=carol_membership,
                moda=second_link,
            ).count(),
            1,
        )

        # Alice has not cast her own vote.
        self.assertFalse(
            PutFarwardModaMember.objects.filter(
                voter=alice,
                candidate=carol_membership,
                moda=second_link,
            ).exists()
        )

        # One vote is insufficient to replace Alice.
        alice_membership.refresh_from_db()
        self.assertTrue(alice_membership.is_delegate)
        # Alice must be recorded as Bob's voting agent.
        effective_vote = PutFarwardModaMember.objects.get(
            voter=bob,
            candidate=carol_membership,
            moda=second_link,
        )

        self.assertEqual(
            getattr(effective_vote, "agent_id", None),
            alice.pk,
        )

        # Back & Forth must announce the action.
        announcements = list(
            ModaBackNForthChat.objects.filter(
                moda=second_link,
                is_system=True,
                sender__isnull=True,
                message__startswith="Housekeeping: ",
            )
        )

        self.assertEqual(len(announcements), 1)

        announcement = announcements[0].message

        self.assertIn(alice.username, announcement)
        self.assertIn(bob.username, announcement)
        self.assertIn(carol.username, announcement)
        self.assertIn("1 of 2", announcement)

    def test_ordinary_member_cannot_withdraw_anothers_replacement_vote(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )
        second_link = ModaModel.objects.create(district=district)

        def create_member(username):
            user = User.objects.create_user(
                username=username,
                email=f"{username}@example.com",
            )
            user.users.district = district
            user.users.legalName = username
            user.users.address = "1 Test Street"
            user.users.userType = "U3D2"
            user.users.save()

            membership = ModaMembers.objects.create(
                user=user,
                moda=second_link,
                is_member=True,
            )
            return user, membership

        alice, alice_membership = create_member("undo_forward_alice")
        bob, bob_membership = create_member("undo_forward_bob")
        carol, carol_membership = create_member("undo_forward_carol")

        self.assertTrue(alice_membership.is_delegate)
        self.assertFalse(carol_membership.is_delegate)

        # Alice has already exercised Bob's vote for Carol.
        vote = PutFarwardModaMember.objects.create(
            voter=bob,
            candidate=carol_membership,
            moda=second_link,
            agent=alice,
        )

        async def scenario():
            communicator = WebsocketCommunicator(
                ModaConsumer.as_asgi(),
                f"/moda/{second_link.code}/{carol.username}",
            )
            communicator.scope["user"] = carol
            communicator.scope["url_route"] = {
                "kwargs": {
                    "moda_name": str(second_link.code),
                    "user_name": carol.username,
                }
            }

            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            await communicator.receive_json_from()

            # Carol attempts to withdraw Bob's vote.
            await communicator.send_json_to({
                "action": "undo_putForward",
                "payload": {
                    "voter": bob.username,
                    "member": carol_membership.pk,
                },
            })

            response = await communicator.receive_json_from()
            await communicator.disconnect()

            return response

        response = asyncio.run(scenario())

        # Bob's effective vote must survive the attempt.
        self.assertTrue(
            PutFarwardModaMember.objects.filter(
                pk=vote.pk,
                voter=bob,
                agent=alice,
                moda=second_link,
            ).exists()
        )

        self.assertEqual(response["status"], "error")

        # Alice remains the serving delegate.
        alice_membership.refresh_from_db()
        self.assertTrue(alice_membership.is_delegate)

        # Unauthorized action must generate no announcement.
        self.assertFalse(
            ModaBackNForthChat.objects.filter(
                moda=second_link,
                is_system=True,
                message__startswith="Housekeeping: ",
            ).exists()
        )
        # Alice, the serving delegate, now withdraws Bob's vote.
        async def authorized_withdrawal():
            communicator = WebsocketCommunicator(
                ModaConsumer.as_asgi(),
                f"/moda/{second_link.code}/{alice.username}",
            )
            communicator.scope["user"] = alice
            communicator.scope["url_route"] = {
                "kwargs": {
                    "moda_name": str(second_link.code),
                    "user_name": alice.username,
                }
            }

            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            await communicator.receive_json_from()

            await communicator.send_json_to({
                "action": "undo_putForward",
                "payload": {
                    "voter": bob.username,
                    "member": carol_membership.pk,
                },
            })

            response = await communicator.receive_json_from()
            await communicator.disconnect()
            return response

        response = asyncio.run(authorized_withdrawal())

        self.assertEqual(
            response["action"]["status"],
            "success",
        )

        # Bob's effective vote has been withdrawn.
        self.assertFalse(
            PutFarwardModaMember.objects.filter(
                pk=vote.pk,
            ).exists()
        )

        # Alice remains the serving delegate.
        alice_membership.refresh_from_db()
        self.assertTrue(alice_membership.is_delegate)

        # Back & Forth records the authorized withdrawal.
        announcements = list(
            ModaBackNForthChat.objects.filter(
                moda=second_link,
                is_system=True,
                sender__isnull=True,
                message__startswith="Housekeeping: ",
            )
        )

        self.assertEqual(len(announcements), 1)

        message = announcements[0].message
        self.assertIn(alice.username, message)
        self.assertIn(bob.username, message)
        self.assertIn(carol.username, message)
        self.assertIn("withdrew", message)
        self.assertIn("0 of 2", message)

    def test_cannot_cast_replacement_vote_for_another_second_link(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )

        first_link = ModaModel.objects.create(district=district)
        other_link = ModaModel.objects.create(district=district)

        def create_member(username, group):
            user = User.objects.create_user(
                username=username,
                email=f"{username}@example.com",
            )
            user.users.district = district
            user.users.legalName = username
            user.users.address = "1 Test Street"
            user.users.userType = "U3D2"
            user.users.save()

            membership = ModaMembers.objects.create(
                user=user,
                moda=group,
                is_member=True,
            )
            return user, membership

        alice, alice_membership = create_member(
            "cross_forward_alice", first_link
        )
        create_member("cross_forward_bob", first_link)
        create_member("cross_forward_erin", first_link)

        create_member("cross_forward_dana", other_link)
        carol, carol_membership = create_member(
            "cross_forward_carol", other_link
        )
        create_member("cross_forward_frank", other_link)

        self.assertTrue(alice_membership.is_delegate)
        self.assertFalse(carol_membership.is_delegate)

        async def scenario():
            communicator = WebsocketCommunicator(
                ModaConsumer.as_asgi(),
                f"/moda/{first_link.code}/{alice.username}",
            )
            communicator.scope["user"] = alice
            communicator.scope["url_route"] = {
                "kwargs": {
                    "moda_name": str(first_link.code),
                    "user_name": alice.username,
                }
            }

            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            await communicator.receive_json_from()

            # Alice targets Carol's membership in another Link.
            await communicator.send_json_to({
                "action": "putForward",
                "payload": {
                    "voter": alice.username,
                    "member": carol_membership.pk,
                },
            })

            response = await communicator.receive_json_from()
            await communicator.disconnect()
            return response

        response = asyncio.run(scenario())

        self.assertEqual(response["status"], "error")

        # No cross-group replacement vote was recorded.
        self.assertFalse(
            PutFarwardModaMember.objects.filter(
                voter=alice,
                candidate=carol_membership,
            ).exists()
        )

        # Neither group's serving delegate changes.
        alice_membership.refresh_from_db()
        self.assertTrue(alice_membership.is_delegate)

        carol_membership.refresh_from_db()
        self.assertFalse(carol_membership.is_delegate)

        # No unauthorized Housekeeping announcement.
        self.assertFalse(
            ModaBackNForthChat.objects.filter(
                moda__in=[first_link, other_link],
                is_system=True,
                message__startswith="Housekeeping: ",
            ).exists()
        )
    def test_cannot_withdraw_replacement_vote_from_another_second_link(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )

        first_link = ModaModel.objects.create(district=district)
        other_link = ModaModel.objects.create(district=district)

        def create_member(username, group):
            user = User.objects.create_user(
                username=username,
                email=f"{username}@example.com",
            )
            user.users.district = district
            user.users.legalName = username
            user.users.address = "1 Test Street"
            user.users.userType = "U3D2"
            user.users.save()

            membership = ModaMembers.objects.create(
                user=user,
                moda=group,
                is_member=True,
            )
            return user, membership

        alice, alice_membership = create_member(
            "cross_withdraw_alice", first_link
        )

        bob, bob_membership = create_member(
            "cross_withdraw_bob", other_link
        )
        carol, carol_membership = create_member(
            "cross_withdraw_carol", other_link
        )
        create_member("cross_withdraw_erin", other_link)

        self.assertTrue(alice_membership.is_delegate)
        self.assertTrue(bob_membership.is_delegate)

        # Bob has voted for Carol in the other Second Link.
        vote = PutFarwardModaMember.objects.create(
            voter=bob,
            candidate=carol_membership,
            moda=other_link,
            agent=bob,
        )

        self.assertFalse(carol_membership.is_delegate)

        async def scenario():
            communicator = WebsocketCommunicator(
                ModaConsumer.as_asgi(),
                f"/moda/{first_link.code}/{alice.username}",
            )
            communicator.scope["user"] = alice
            communicator.scope["url_route"] = {
                "kwargs": {
                    "moda_name": str(first_link.code),
                    "user_name": alice.username,
                }
            }

            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            await communicator.receive_json_from()

            # Alice attempts to withdraw Bob's vote
            # in a different Second Link.
            await communicator.send_json_to({
                "action": "undo_putForward",
                "payload": {
                    "voter": bob.username,
                    "member": carol_membership.pk,
                },
            })

            response = await communicator.receive_json_from()
            await communicator.disconnect()
            return response

        response = asyncio.run(scenario())

        self.assertEqual(response["status"], "error")

        # Bob's vote must remain intact.
        self.assertTrue(
            PutFarwardModaMember.objects.filter(
                pk=vote.pk,
                voter=bob,
                agent=bob,
                moda=other_link,
            ).exists()
        )

        # Neither group's delegate changes.
        alice_membership.refresh_from_db()
        bob_membership.refresh_from_db()
        self.assertTrue(alice_membership.is_delegate)
        self.assertTrue(bob_membership.is_delegate)

        # No unauthorized announcement.
        self.assertFalse(
            ModaBackNForthChat.objects.filter(
                moda__in=[first_link, other_link],
                is_system=True,
                message__startswith="Housekeeping: ",
            ).exists()
        )

    def test_housekeeping_votes_have_database_uniqueness(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )
        second_link = ModaModel.objects.create(district=district)

        members = []

        # Five accepted members ensure that duplicate votes
        # cannot accidentally trigger a majority transition.
        for index in range(5):
            username = f"unique_vote_member_{index}"
            user = User.objects.create_user(
                username=username,
                email=f"{username}@example.com",
            )
            user.users.district = district
            user.users.legalName = username
            user.users.address = "1 Test Street"
            user.users.userType = "U3D2"
            user.users.save()

            membership = ModaMembers.objects.create(
                user=user,
                moda=second_link,
                is_member=True,
            )
            members.append(membership)

        voter = members[0].user

        applicant = User.objects.create_user(
            username="unique_vote_applicant",
            email="unique_vote_applicant@example.com",
        )
        applicant.users.district = district
        applicant.users.legalName = "Unique Vote Applicant"
        applicant.users.address = "1 Test Street"
        applicant.users.userType = "U3D2"
        applicant.users.save()

        applicant_membership = ModaMembers.objects.create(
            user=applicant,
            moda=second_link,
            is_member=False,
        )

        vote_cases = [
            (VoteInModaMember, applicant_membership),
            (VoteOutModaMember, members[1]),
            (PutFarwardModaMember, members[2]),
        ]

        for model, candidate in vote_cases:
            with self.subTest(model=model.__name__):
                vote_fields = {
                    "voter": voter,
                    "candidate": candidate,
                    "moda": second_link,
                    "agent": voter,
                }

                # First affirmative vote is legitimate.
                model.objects.create(**vote_fields)

                # A second identical effective vote must
                # be rejected by the database itself.
                with self.assertRaises(IntegrityError):
                    with transaction.atomic():
                        model.objects.create(**vote_fields)

                self.assertEqual(
                    model.objects.filter(
                        voter=voter,
                        candidate=candidate,
                        moda=second_link,
                    ).count(),
                    1,
                )