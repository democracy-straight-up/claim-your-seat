from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase
from moda.models import ModaMembers, ModaModel
from api.models import (
    BackNForthChat,
    SecDelMembers,
    SecDelModel,
    VoteOutSecDelMember,
)
from vote.models import Districts


class FirstLinkDirectRemovalSuccessionTests(TestCase):
    def setUp(self):
        self.district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )

        self.first_link = SecDelModel.objects.create(
            district=self.district,
        )

        self.delegate_user = self.create_user(
            "removal_sec_del",
            "Removal Sec-Del",
        )
        self.removed_user = self.create_user(
            "removal_first_link_member",
            "Removal First Link Member",
        )
        self.successor_user = self.create_user(
            "removal_first_link_successor",
            "Removal First Link Successor",
        )

        self.delegate = SecDelMembers.objects.create(
            user=self.delegate_user,
            sec_del=self.first_link,
            is_member=True,
        )
        self.removed_member = SecDelMembers.objects.create(
            user=self.removed_user,
            sec_del=self.first_link,
            is_member=True,
        )
        self.successor = SecDelMembers.objects.create(
            user=self.successor_user,
            sec_del=self.first_link,
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
        user.users.userType = "U2D1"
        user.users.save()
        return user

    def test_removing_non_delegate_compacts_first_link_succession_line(self):
        self.assertEqual(self.delegate.succession_position, 0)
        self.assertEqual(self.removed_member.succession_position, 1)
        self.assertEqual(self.successor.succession_position, 2)

        VoteOutSecDelMember.objects.create(
            voter=self.delegate_user,
            candidate=self.removed_member,
            sec_del=self.first_link,
        )
        VoteOutSecDelMember.objects.create(
            voter=self.successor_user,
            candidate=self.removed_member,
            sec_del=self.first_link,
        )

        self.assertFalse(
            SecDelMembers.objects.filter(
                pk=self.removed_member.pk
            ).exists()
        )

        self.delegate.refresh_from_db()
        self.successor.refresh_from_db()

        self.assertTrue(self.delegate.is_delegate)
        self.assertEqual(self.delegate.succession_position, 0)

        self.assertFalse(self.successor.is_delegate)
        self.assertEqual(self.successor.succession_position, 1)

    def test_removing_non_delegate_records_compaction_in_first_link_back_and_forth(
        self,
    ):
        VoteOutSecDelMember.objects.create(
            voter=self.delegate_user,
            candidate=self.removed_member,
            sec_del=self.first_link,
        )
        VoteOutSecDelMember.objects.create(
            voter=self.successor_user,
            candidate=self.removed_member,
            sec_del=self.first_link,
        )

        system_message = BackNForthChat.objects.get(
            sec_del=self.first_link,
            is_system=True,
        )

        self.assertIsNone(system_message.sender)
        self.assertEqual(
            system_message.message,
            (
                "Succession update: Removal First Link Successor moved "
                "from position 2 to position 1 after Removal First Link "
                "Member was removed."
            ),
        )

    def test_removing_second_delegate_promotes_position_one(self):
        VoteOutSecDelMember.objects.create(
            voter=self.removed_user,
            candidate=self.delegate,
            sec_del=self.first_link,
        )
        VoteOutSecDelMember.objects.create(
            voter=self.successor_user,
            candidate=self.delegate,
            sec_del=self.first_link,
        )

        self.assertFalse(
            SecDelMembers.objects.filter(
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
            "U2D2",
        )

        self.assertFalse(self.successor.is_delegate)
        self.assertEqual(
            self.successor.succession_position,
            1,
        )

        self.assertEqual(
            SecDelMembers.objects.filter(
                sec_del=self.first_link,
                is_member=True,
                is_delegate=True,
            ).count(),
            1,
        )

    def test_removing_second_delegate_removes_dependent_second_link_membership(
        self,
    ):
        second_link = ModaModel.objects.create(
            district=self.district,
        )

        second_link_founder_user = self.create_user(
            "second_link_founder",
            "Second Link Founder",
        )

        ModaMembers.objects.create(
            user=second_link_founder_user,
            moda=second_link,
            is_member=True,
        )

        dependent_membership = ModaMembers.objects.create(
            user=self.delegate_user,
            moda=second_link,
            is_member=True,
        )

        self.assertTrue(
            ModaMembers.objects.filter(
                pk=dependent_membership.pk
            ).exists()
        )

        VoteOutSecDelMember.objects.create(
            voter=self.removed_user,
            candidate=self.delegate,
            sec_del=self.first_link,
        )
        VoteOutSecDelMember.objects.create(
            voter=self.successor_user,
            candidate=self.delegate,
            sec_del=self.first_link,
        )

        self.assertFalse(
            ModaMembers.objects.filter(
                pk=dependent_membership.pk
            ).exists()
        )

    def test_removing_second_delegate_notifies_first_link_and_officeholders(
        self,
    ):
        with self.captureOnCommitCallbacks(execute=True):
            VoteOutSecDelMember.objects.create(
                voter=self.removed_user,
                candidate=self.delegate,
                sec_del=self.first_link,
            )
            VoteOutSecDelMember.objects.create(
                voter=self.successor_user,
                candidate=self.delegate,
                sec_del=self.first_link,
            )

        promotion_message = BackNForthChat.objects.get(
            sec_del=self.first_link,
            is_system=True,
            message__contains="became Sec-Del",
        )

        self.assertIsNone(promotion_message.sender)
        self.assertEqual(
            promotion_message.message,
            (
                "Succession update: Removal First Link Member became "
                "Sec-Del after Removal Sec-Del was removed. Removal "
                "First Link Member moved from position 1 to position 0."
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