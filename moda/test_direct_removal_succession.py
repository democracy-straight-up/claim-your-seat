from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from holc.models import HolcMembers, HolcModel
from moda.models import (
    ModaBackNForthChat,
    ModaMembers,
    ModaModel,
    VoteOutModaMember,
)
from vote.models import Districts


class SecondLinkDirectRemovalSuccessionTests(TestCase):
    def setUp(self):
        self.district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )

        self.second_link = ModaModel.objects.create(
            district=self.district,
        )

        self.delegate_user = self.create_user(
            "removal_caucus_delegate",
            "Removal Caucus Delegate",
        )
        self.removed_user = self.create_user(
            "removal_second_link_member",
            "Removal Second Link Member",
        )
        self.successor_user = self.create_user(
            "removal_second_link_successor",
            "Removal Second Link Successor",
        )

        self.delegate = ModaMembers.objects.create(
            user=self.delegate_user,
            moda=self.second_link,
            is_member=True,
        )
        self.removed_member = ModaMembers.objects.create(
            user=self.removed_user,
            moda=self.second_link,
            is_member=True,
        )
        self.successor = ModaMembers.objects.create(
            user=self.successor_user,
            moda=self.second_link,
            is_member=True,
        )

    def create_user(self, username, legal_name):
        user = User.objects.create_user(
            username=username,
            email=f"{username}@example.com",
        )
        user.users.district = self.district
        user.users.legalName = legal_name
        user.users.address = "1 Test Street"
        user.users.userType = "U3D2"
        user.users.save()
        return user

    def test_removing_non_delegate_compacts_second_link_succession_line(self):
        self.assertEqual(self.delegate.succession_position, 0)
        self.assertEqual(self.removed_member.succession_position, 1)
        self.assertEqual(self.successor.succession_position, 2)

        VoteOutModaMember.objects.create(
            voter=self.delegate_user,
            candidate=self.removed_member,
            moda=self.second_link,
        )
        VoteOutModaMember.objects.create(
            voter=self.successor_user,
            candidate=self.removed_member,
            moda=self.second_link,
        )

        self.assertFalse(
            ModaMembers.objects.filter(
                pk=self.removed_member.pk
            ).exists()
        )

        self.delegate.refresh_from_db()
        self.successor.refresh_from_db()

        self.assertTrue(self.delegate.is_delegate)
        self.assertEqual(self.delegate.succession_position, 0)

        self.assertFalse(self.successor.is_delegate)
        self.assertEqual(self.successor.succession_position, 1)

    def test_removing_non_delegate_records_compaction_in_second_link_back_and_forth(
        self,
    ):
        VoteOutModaMember.objects.create(
            voter=self.delegate_user,
            candidate=self.removed_member,
            moda=self.second_link,
        )
        VoteOutModaMember.objects.create(
            voter=self.successor_user,
            candidate=self.removed_member,
            moda=self.second_link,
        )

        system_message = ModaBackNForthChat.objects.get(
            moda=self.second_link,
            is_system=True,
        )

        self.assertIsNone(system_message.sender)
        self.assertEqual(
            system_message.message,
            (
                "Succession update: Removal Second Link Successor moved "
                "from position 2 to position 1 after Removal Second Link "
                "Member was removed."
            ),
        )

    def test_removing_caucus_delegate_promotes_position_one(self):
        VoteOutModaMember.objects.create(
            voter=self.removed_user,
            candidate=self.delegate,
            moda=self.second_link,
        )
        VoteOutModaMember.objects.create(
            voter=self.successor_user,
            candidate=self.delegate,
            moda=self.second_link,
        )

        self.assertFalse(
            ModaMembers.objects.filter(
                pk=self.delegate.pk
            ).exists()
        )

        self.removed_member.refresh_from_db()
        self.successor.refresh_from_db()
        self.removed_user.users.refresh_from_db()

        self.assertTrue(self.removed_member.is_delegate)
        self.assertEqual(
            self.removed_member.succession_position,
            0,
        )
        self.assertEqual(
            self.removed_user.users.userType,
            "U4D3",
        )

        self.assertFalse(self.successor.is_delegate)
        self.assertEqual(
            self.successor.succession_position,
            1,
        )

        self.assertEqual(
            ModaMembers.objects.filter(
                moda=self.second_link,
                is_member=True,
                is_delegate=True,
            ).count(),
            1,
        )

    def test_removing_caucus_delegate_removes_dependent_caucus_membership(
        self,
    ):
        caucus = HolcModel.objects.create(
            district=self.district,
        )

        caucus_founder_user = self.create_user(
            "caucus_founder",
            "Caucus Founder",
        )

        HolcMembers.objects.create(
            user=caucus_founder_user,
            holc=caucus,
            is_member=True,
        )

        dependent_membership = HolcMembers.objects.create(
            user=self.delegate_user,
            holc=caucus,
            is_member=True,
        )

        self.assertTrue(
            HolcMembers.objects.filter(
                pk=dependent_membership.pk
            ).exists()
        )

        VoteOutModaMember.objects.create(
            voter=self.removed_user,
            candidate=self.delegate,
            moda=self.second_link,
        )
        VoteOutModaMember.objects.create(
            voter=self.successor_user,
            candidate=self.delegate,
            moda=self.second_link,
        )

        self.assertFalse(
            HolcMembers.objects.filter(
                pk=dependent_membership.pk
            ).exists()
        )

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
    )
    def test_removing_caucus_delegate_posts_promotion_and_sends_emails(
        self,
    ):
        with self.captureOnCommitCallbacks(execute=True):
            VoteOutModaMember.objects.create(
                voter=self.removed_user,
                candidate=self.delegate,
                moda=self.second_link,
            )
            VoteOutModaMember.objects.create(
                voter=self.successor_user,
                candidate=self.delegate,
                moda=self.second_link,
            )

        self.removed_member.refresh_from_db()

        self.assertTrue(self.removed_member.is_delegate)
        self.assertEqual(
            self.removed_member.succession_position,
            0,
        )

        messages = ModaBackNForthChat.objects.filter(
            moda=self.second_link,
            is_system=True,
        )

        promotion_messages = [
            message
            for message in messages
            if (
                "Removal Second Link Member became Caucus Delegate"
                in message.message
                and "Removal Caucus Delegate" in message.message
            )
        ]

        self.assertEqual(len(promotion_messages), 1)
        self.assertIsNone(promotion_messages[0].sender)
        self.assertNotIn(
            "position None",
            promotion_messages[0].message,
        )
        recipients = {
            recipient
            for email in mail.outbox
            for recipient in email.to
        }

        self.assertEqual(
            recipients,
            {
                "removal_caucus_delegate@example.com",
                "removal_second_link_member@example.com",
            },
        )
        outgoing_emails = [
            email
            for email in mail.outbox
            if "removal_caucus_delegate@example.com" in email.to
        ]

        self.assertEqual(len(outgoing_emails), 1)
        self.assertIn(
            "you were removed from",
            outgoing_emails[0].body,
        )
        self.assertNotIn(
            "position None",
            outgoing_emails[0].body,
        )
        self.assertNotIn(
            "lower-level",
            outgoing_emails[0].body,
        )