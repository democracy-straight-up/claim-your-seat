from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase
from api.models import SecDelMembers, SecDelModel
from vote.models import (
    CircleBackNForth,
    CircleMember_vote_out,
    Districts,
    Group,
    GroupMember,
)


class CircleDirectRemovalSuccessionTests(TestCase):
    def setUp(self):
        self.district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )

        self.circle = Group.objects.create(
            code="C1001",
            district=self.district,
            invitation_code="1234567890",
            group_type=1,
        )

        self.delegate_user = self.create_user(
            "removal_delegate",
            "Removal Delegate",
        )
        self.removed_user = self.create_user(
            "removal_member",
            "Removal Member",
        )
        self.successor_user = self.create_user(
            "removal_successor",
            "Removal Successor",
        )

        self.delegate = GroupMember.objects.create(
            user=self.delegate_user,
            group=self.circle,
            is_member=True,
        )
        self.removed_member = GroupMember.objects.create(
            user=self.removed_user,
            group=self.circle,
            is_member=True,
        )
        self.successor = GroupMember.objects.create(
            user=self.successor_user,
            group=self.circle,
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
        user.users.userType = "U1D0"
        user.users.save()
        return user

    def test_removing_non_delegate_compacts_circle_succession_line(self):
        self.assertEqual(self.delegate.succession_position, 0)
        self.assertEqual(self.removed_member.succession_position, 1)
        self.assertEqual(self.successor.succession_position, 2)

        CircleMember_vote_out.objects.create(
            voter=self.delegate_user,
            candidate=self.removed_member,
            group=self.circle,
        )
        CircleMember_vote_out.objects.create(
            voter=self.successor_user,
            candidate=self.removed_member,
            group=self.circle,
        )

        self.assertFalse(
            GroupMember.objects.filter(
                pk=self.removed_member.pk
            ).exists()
        )

        self.delegate.refresh_from_db()
        self.successor.refresh_from_db()

        self.assertTrue(self.delegate.is_delegate)
        self.assertEqual(self.delegate.succession_position, 0)

        self.assertFalse(self.successor.is_delegate)
        self.assertEqual(self.successor.succession_position, 1)

    def test_removing_non_delegate_records_compaction_in_circle_back_and_forth(
        self,
    ):
        CircleMember_vote_out.objects.create(
            voter=self.delegate_user,
            candidate=self.removed_member,
            group=self.circle,
        )
        CircleMember_vote_out.objects.create(
            voter=self.successor_user,
            candidate=self.removed_member,
            group=self.circle,
        )

        system_message = CircleBackNForth.objects.get(
            circle=self.circle,
            is_system=True,
        )

        self.assertIsNone(system_message.sender)
        self.assertEqual(
            system_message.message,
            (
                "Succession update: Removal Successor moved from "
                "position 2 to position 1 after Removal Member was "
                "removed."
            ),
        )

    def test_removing_first_delegate_promotes_position_one(self):
        CircleMember_vote_out.objects.create(
            voter=self.removed_user,
            candidate=self.delegate,
            group=self.circle,
        )
        CircleMember_vote_out.objects.create(
            voter=self.successor_user,
            candidate=self.delegate,
            group=self.circle,
        )

        self.assertFalse(
            GroupMember.objects.filter(
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
            "U1D1",
        )

        self.assertFalse(self.successor.is_delegate)
        self.assertEqual(
            self.successor.succession_position,
            1,
        )

        self.assertEqual(
            GroupMember.objects.filter(
                group=self.circle,
                is_member=True,
                is_delegate=True,
            ).count(),
            1,
        )

    def test_removing_first_delegate_removes_dependent_first_link_membership(
        self,
    ):
        first_link = SecDelModel.objects.create(
            district=self.district,
        )

        first_link_founder_user = self.create_user(
            "first_link_founder",
            "First Link Founder",
        )

        SecDelMembers.objects.create(
            user=first_link_founder_user,
            sec_del=first_link,
            is_member=True,
        )

        dependent_membership = SecDelMembers.objects.create(
            user=self.delegate_user,
            sec_del=first_link,
            is_member=True,
        )

        self.assertTrue(
            SecDelMembers.objects.filter(
                pk=dependent_membership.pk
            ).exists()
        )

        CircleMember_vote_out.objects.create(
            voter=self.removed_user,
            candidate=self.delegate,
            group=self.circle,
        )
        CircleMember_vote_out.objects.create(
            voter=self.successor_user,
            candidate=self.delegate,
            group=self.circle,
        )

        self.assertFalse(
            SecDelMembers.objects.filter(
                pk=dependent_membership.pk
            ).exists()
        )

    def test_removing_first_delegate_notifies_circle_and_officeholders(self):
        with self.captureOnCommitCallbacks(execute=True):
            CircleMember_vote_out.objects.create(
                voter=self.removed_user,
                candidate=self.delegate,
                group=self.circle,
            )
            CircleMember_vote_out.objects.create(
                voter=self.successor_user,
                candidate=self.delegate,
                group=self.circle,
            )

        promotion_message = CircleBackNForth.objects.get(
            circle=self.circle,
            is_system=True,
            message__contains="became F-Del",
        )

        self.assertIsNone(promotion_message.sender)
        self.assertEqual(
            promotion_message.message,
            (
                "Succession update: Removal Member became F-Del after "
                "Removal Delegate was removed. Removal Member moved "
                "from position 1 to position 0."
            ),
        )

        email_recipients = {
            recipient
            for message in mail.outbox
            for recipient in message.to
        }

        self.assertIn(
            self.delegate_user.email,
            email_recipients,
        )
        self.assertIn(
            self.removed_user.email,
            email_recipients,
        )