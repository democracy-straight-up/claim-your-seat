from django.contrib.auth.models import User
from collections import Counter

from django.core import mail
from django.test import TestCase, override_settings

from api.models import SecDelMembers, SecDelModel
from moda.models import ModaBackNForthChat, ModaMembers, ModaModel
from vote.models import Districts


class SecDelHigherLevelSuccessionTests(TestCase):
    def setUp(self):
        self.district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT01",
        )

        self.outgoing_sec_del = User.objects.create_user(
            username="outgoing-sec-del",
            password="testpass",
        )
        self.outgoing_sec_del.users.district = self.district
        self.outgoing_sec_del.users.save()

        self.incoming_sec_del = User.objects.create_user(
            username="incoming-sec-del",
            password="testpass",
        )
        self.incoming_sec_del.users.district = self.district
        self.incoming_sec_del.users.save()

        self.other_second_link_member = User.objects.create_user(
            username="other-second-link-member",
            password="testpass",
        )
        self.other_second_link_member.users.district = self.district
        self.other_second_link_member.users.save()

        self.first_link = SecDelModel.objects.create(
            district=self.district,
        )

        self.outgoing_first_link_membership = (
            SecDelMembers.objects.create(
                user=self.outgoing_sec_del,
                sec_del=self.first_link,
                is_member=True,
                is_delegate=True,
            )
        )

        self.incoming_first_link_membership = (
            SecDelMembers.objects.create(
                user=self.incoming_sec_del,
                sec_del=self.first_link,
                is_member=True,
                is_delegate=False,
            )
        )

        self.incoming_sec_del.users.userType = "U2D1"
        self.incoming_sec_del.users.save(
            update_fields=["userType"]
        )

        self.second_link = ModaModel.objects.create(
            district=self.district,
        )

        self.other_second_link_membership = (
            ModaMembers.objects.create(
                user=self.other_second_link_member,
                moda=self.second_link,
                is_member=True,
                is_delegate=True,
            )
        )

        self.outgoing_second_link_membership = (
            ModaMembers.objects.create(
                user=self.outgoing_sec_del,
                moda=self.second_link,
                is_member=True,
                is_delegate=False,
            )
        )

        self.outgoing_sec_del.users.userType = "U3D2"
        self.outgoing_sec_del.users.save(
            update_fields=["userType"]
        )

    def test_replaced_sec_del_loses_second_link_membership(self):
        self.assertTrue(
            ModaMembers.objects.filter(
                pk=self.outgoing_second_link_membership.pk,
                is_member=True,
            ).exists()
        )

        moved = (
            self.incoming_first_link_membership
            .move_forward_one_position()
        )

        self.assertTrue(moved)

        self.assertFalse(
            ModaMembers.objects.filter(
                pk=self.outgoing_second_link_membership.pk,
            ).exists()
        )

        self.assertFalse(
            ModaMembers.objects.filter(
                user=self.incoming_sec_del,
                moda=self.second_link,
            ).exists()
        )

        self.outgoing_sec_del.users.refresh_from_db()
        self.incoming_sec_del.users.refresh_from_db()

        self.assertEqual(
            self.outgoing_sec_del.users.userType,
            "U2D1",
        )
        self.assertEqual(
            self.incoming_sec_del.users.userType,
            "U2D2",
        )

        self.other_second_link_membership.refresh_from_db()

        self.assertTrue(
            self.other_second_link_membership.is_delegate
        )
        self.assertEqual(
            self.other_second_link_membership.succession_position,
            0,
        )

    def test_second_link_successor_replaces_removed_delegate(self):
        successor_first_link = SecDelModel.objects.create(
            district=self.district,
        )

        SecDelMembers.objects.create(
            user=self.other_second_link_member,
            sec_del=successor_first_link,
            is_member=True,
            is_delegate=True,
        )

        # For this scenario, the outgoing Sec-Del is also
        # the Caucus Delegate, and the existing Second-Link member
        # is first in that Second Link's succession line.
        ModaMembers.objects.filter(
            pk=self.outgoing_second_link_membership.pk,
        ).update(
            is_delegate=True,
            succession_position=0,
        )
        ModaMembers.objects.filter(
            pk=self.other_second_link_membership.pk,
        ).update(
            is_delegate=False,
            succession_position=1,
        )

        self.outgoing_sec_del.users.userType = "U4D3"
        self.outgoing_sec_del.users.save(
            update_fields=["userType"]
        )

        self.other_second_link_member.users.userType = "U3D2"
        self.other_second_link_member.users.save(
            update_fields=["userType"]
        )

        moved = (
            self.incoming_first_link_membership
            .move_forward_one_position()
        )

        self.assertTrue(moved)

        self.assertFalse(
            ModaMembers.objects.filter(
                pk=self.outgoing_second_link_membership.pk,
            ).exists()
        )

        self.other_second_link_membership.refresh_from_db()
        self.other_second_link_member.users.refresh_from_db()

        self.assertTrue(
            self.other_second_link_membership.is_delegate
        )
        self.assertEqual(
            self.other_second_link_membership.succession_position,
            0,
        )
        self.assertEqual(
            self.other_second_link_member.users.userType,
            "U4D3",
        )

    def test_second_link_succession_positions_compact_after_delegate_removal(self):
        later_successor = User.objects.create_user(
            username="later-second-link-successor",
            password="testpass",
        )
        later_successor.users.district = self.district
        later_successor.users.save()

        later_successor_first_link = SecDelModel.objects.create(
            district=self.district,
        )

        SecDelMembers.objects.create(
            user=later_successor,
            sec_del=later_successor_first_link,
            is_member=True,
            is_delegate=True,
        )

        later_successor_membership = ModaMembers.objects.create(
            user=later_successor,
            moda=self.second_link,
            is_member=True,
            is_delegate=False,
        )

        # Make the outgoing Sec-Del the current Second-Link
        # delegate. The existing Second-Link member is first successor,
        # and the newly added member is second successor.
        ModaMembers.objects.filter(
            pk=self.outgoing_second_link_membership.pk,
        ).update(
            is_delegate=True,
            succession_position=0,
        )
        ModaMembers.objects.filter(
            pk=self.other_second_link_membership.pk,
        ).update(
            is_delegate=False,
            succession_position=1,
        )

        later_successor_membership.refresh_from_db()

        self.assertEqual(
            later_successor_membership.succession_position,
            2,
        )

        moved = (
            self.incoming_first_link_membership
            .move_forward_one_position()
        )

        self.assertTrue(moved)

        self.other_second_link_membership.refresh_from_db()
        later_successor_membership.refresh_from_db()

        self.assertEqual(
            self.other_second_link_membership.succession_position,
            0,
        )
        self.assertEqual(
            later_successor_membership.succession_position,
            1,
        )

    def test_sec_del_loss_posts_second_link_removal(self):
        moved = (
            self.incoming_first_link_membership
            .move_forward_one_position()
        )

        self.assertTrue(moved)

        messages = ModaBackNForthChat.objects.filter(
            moda=self.second_link,
        )

        self.assertEqual(messages.count(), 1)

        message = messages.get()

        self.assertIsNone(message.sender)
        self.assertTrue(message.is_system)
        self.assertEqual(
            message.message,
            (
                "Succession update: outgoing-sec-del was "
                "removed from Second Link after losing the Sec-Del "
                "mandate required for membership."
            ),
        )

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
    )
    def test_caucus_delegate_promotion_posts_and_emails(self):
        self.outgoing_sec_del.email = "outgoing@example.com"
        self.outgoing_sec_del.save(
            update_fields=["email"]
        )

        self.incoming_sec_del.email = (
            "incoming-first-link@example.com"
        )
        self.incoming_sec_del.save(
            update_fields=["email"]
        )

        self.other_second_link_member.email = (
            "incoming-second-link@example.com"
        )
        self.other_second_link_member.save(
            update_fields=["email"]
        )

        successor_first_link = SecDelModel.objects.create(
            district=self.district,
        )

        SecDelMembers.objects.create(
            user=self.other_second_link_member,
            sec_del=successor_first_link,
            is_member=True,
            is_delegate=True,
        )

        ModaMembers.objects.filter(
            pk=self.outgoing_second_link_membership.pk,
        ).update(
            is_delegate=True,
            succession_position=0,
        )
        ModaMembers.objects.filter(
            pk=self.other_second_link_membership.pk,
        ).update(
            is_delegate=False,
            succession_position=1,
        )

        self.outgoing_sec_del.users.userType = "U4D3"
        self.outgoing_sec_del.users.save(
            update_fields=["userType"]
        )

        self.other_second_link_member.users.userType = "U3D2"
        self.other_second_link_member.users.save(
            update_fields=["userType"]
        )

        with self.captureOnCommitCallbacks(execute=True):
            moved = (
                self.incoming_first_link_membership
                .move_forward_one_position()
            )

        self.assertTrue(moved)

        messages = ModaBackNForthChat.objects.filter(
            moda=self.second_link,
        )

        self.assertEqual(messages.count(), 2)

        message_texts = set(
            messages.values_list("message", flat=True)
        )

        self.assertIn(
            (
                "Succession update: outgoing-sec-del was "
                "removed from Second Link after losing the Sec-Del "
                "mandate required for membership."
            ),
            message_texts,
        )

        self.assertIn(
            (
                "Succession update: other-second-link-member became "
                "Caucus Delegate after "
                "outgoing-sec-del was removed. "
                "other-second-link-member moved from position 1 to "
                "position 0."
            ),
            message_texts,
        )

        recipients = Counter(
            recipient
            for email in mail.outbox
            for recipient in email.to
        )

        self.assertEqual(
            recipients,
            Counter(
                {
                    "outgoing@example.com": 2,
                    "incoming-first-link@example.com": 1,
                    "incoming-second-link@example.com": 1,
                }
            ),
        )

    def test_second_link_compaction_posts_exact_position_change(self):
        later_successor = User.objects.create_user(
            username="later-second-link-successor",
            password="testpass",
        )
        later_successor.users.district = self.district
        later_successor.users.save()

        later_successor_first_link = SecDelModel.objects.create(
            district=self.district,
        )

        SecDelMembers.objects.create(
            user=later_successor,
            sec_del=later_successor_first_link,
            is_member=True,
            is_delegate=True,
        )

        later_successor_membership = ModaMembers.objects.create(
            user=later_successor,
            moda=self.second_link,
            is_member=True,
            is_delegate=False,
        )

        ModaMembers.objects.filter(
            pk=self.outgoing_second_link_membership.pk,
        ).update(
            is_delegate=True,
            succession_position=0,
        )
        ModaMembers.objects.filter(
            pk=self.other_second_link_membership.pk,
        ).update(
            is_delegate=False,
            succession_position=1,
        )

        later_successor_membership.refresh_from_db()

        self.assertEqual(
            later_successor_membership.succession_position,
            2,
        )

        moved = (
            self.incoming_first_link_membership
            .move_forward_one_position()
        )

        self.assertTrue(moved)

        messages = ModaBackNForthChat.objects.filter(
            moda=self.second_link,
        )

        self.assertEqual(messages.count(), 3)

        message_texts = set(
            messages.values_list("message", flat=True)
        )

        self.assertIn(
            (
                "Succession update: later-second-link-successor moved "
                "from position 2 to position 1 after "
                "outgoing-sec-del was removed."
            ),
            message_texts,
        )