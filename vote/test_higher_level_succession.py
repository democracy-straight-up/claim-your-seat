from django.contrib.auth.models import User
from collections import Counter

from django.core import mail
from django.test import TestCase, override_settings

from api.models import BackNForthChat, SecDelMembers, SecDelModel
from vote.models import Districts, Group, GroupMember


class FDelHigherLevelSuccessionTests(TestCase):
    def setUp(self):
        self.district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT01",
        )

        self.other_first_link_member = User.objects.create_user(
            username="other-first-link-member",
            password="testpass",
        )
        self.other_first_link_member.users.district = self.district
        self.other_first_link_member.users.save()

        self.outgoing_f_del = User.objects.create_user(
            username="outgoing-f-del",
            password="testpass",
        )
        self.outgoing_f_del.users.district = self.district
        self.outgoing_f_del.users.save()

        self.incoming_f_del = User.objects.create_user(
            username="incoming-f-del",
            password="testpass",
        )
        self.incoming_f_del.users.district = self.district
        self.incoming_f_del.users.save()

        self.circle = Group.objects.create(
            code="CAS01",
            district=self.district,
            invitation_code="CASCADE",
            group_type=0,
            parent_group=None,
        )

        self.outgoing_circle_membership = GroupMember.objects.create(
            user=self.outgoing_f_del,
            group=self.circle,
            is_member=True,
            is_delegate=True,
        )

        self.incoming_circle_membership = GroupMember.objects.create(
            user=self.incoming_f_del,
            group=self.circle,
            is_member=True,
            is_delegate=False,
        )

        self.first_link = SecDelModel.objects.create(
            district=self.district,
        )

        self.other_first_link_membership = SecDelMembers.objects.create(
            user=self.other_first_link_member,
            sec_del=self.first_link,
            is_member=True,
            is_delegate=True,
        )

        self.outgoing_first_link_membership = SecDelMembers.objects.create(
            user=self.outgoing_f_del,
            sec_del=self.first_link,
            is_member=True,
            is_delegate=False,
        )

        self.outgoing_f_del.users.userType = "U2D1"
        self.outgoing_f_del.users.save(
            update_fields=["userType"]
        )

    def test_replaced_f_del_loses_first_link_membership(self):
        self.assertTrue(
            SecDelMembers.objects.filter(
                pk=self.outgoing_first_link_membership.pk,
                is_member=True,
            ).exists()
        )

        moved = (
            self.incoming_circle_membership.move_forward_one_position()
        )

        self.assertTrue(moved)

        self.assertFalse(
            SecDelMembers.objects.filter(
                pk=self.outgoing_first_link_membership.pk,
            ).exists()
        )

        self.assertFalse(
            SecDelMembers.objects.filter(
                user=self.incoming_f_del,
                sec_del=self.first_link,
            ).exists()
        )

        self.outgoing_f_del.users.refresh_from_db()
        self.incoming_f_del.users.refresh_from_db()

        self.assertEqual(
            self.outgoing_f_del.users.userType,
            "U1D0",
        )
        self.assertEqual(
            self.incoming_f_del.users.userType,
            "U1D1",
        )

        self.other_first_link_membership.refresh_from_db()

        self.assertTrue(
            self.other_first_link_membership.is_delegate
        )
        self.assertEqual(
            self.other_first_link_membership.succession_position,
            0,
        )

    def test_first_link_successor_becomes_sec_del_after_removal(self):
        successor_circle = Group.objects.create(
            code="CAS02",
            district=self.district,
            invitation_code="SUCCESSOR",
            group_type=0,
            parent_group=None,
        )

        GroupMember.objects.create(
            user=self.other_first_link_member,
            group=successor_circle,
            is_member=True,
            is_delegate=True,
        )

        # For this scenario, the outgoing F-Del is also the
        # Sec-Del, and the other First Link Member is first
        # in that First Link's succession line.
        SecDelMembers.objects.filter(
            pk=self.outgoing_first_link_membership.pk,
        ).update(
            is_delegate=True,
            succession_position=0,
        )
        SecDelMembers.objects.filter(
            pk=self.other_first_link_membership.pk,
        ).update(
            is_delegate=False,
            succession_position=1,
        )

        self.outgoing_f_del.users.userType = "U2D2"
        self.outgoing_f_del.users.save(
            update_fields=["userType"]
        )

        self.other_first_link_member.users.userType = "U2D1"
        self.other_first_link_member.users.save(
            update_fields=["userType"]
        )

        moved = (
            self.incoming_circle_membership.move_forward_one_position()
        )

        self.assertTrue(moved)

        self.assertFalse(
            SecDelMembers.objects.filter(
                pk=self.outgoing_first_link_membership.pk,
            ).exists()
        )

        self.other_first_link_membership.refresh_from_db()
        self.other_first_link_member.users.refresh_from_db()

        self.assertTrue(
            self.other_first_link_membership.is_delegate
        )
        self.assertEqual(
            self.other_first_link_membership.succession_position,
            0,
        )
        self.assertEqual(
            self.other_first_link_member.users.userType,
            "U2D2",
        )

    def test_first_link_succession_positions_compact_after_sec_del_removal(self):
        later_successor = User.objects.create_user(
            username="later-first-link-successor",
            password="testpass",
        )
        later_successor.users.district = self.district
        later_successor.users.save()

        later_successor_circle = Group.objects.create(
            code="CAS03",
            district=self.district,
            invitation_code="LATER",
            group_type=0,
            parent_group=None,
        )

        GroupMember.objects.create(
            user=later_successor,
            group=later_successor_circle,
            is_member=True,
            is_delegate=True,
        )

        later_successor_membership = SecDelMembers.objects.create(
            user=later_successor,
            sec_del=self.first_link,
            is_member=True,
            is_delegate=False,
        )

        # Make the outgoing F-Del the current Sec-Del.
        # The other First-Link member is first successor,
        # and the newly added First-Link member is second successor.
        SecDelMembers.objects.filter(
            pk=self.outgoing_first_link_membership.pk,
        ).update(
            is_delegate=True,
            succession_position=0,
        )
        SecDelMembers.objects.filter(
            pk=self.other_first_link_membership.pk,
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
            self.incoming_circle_membership.move_forward_one_position()
        )

        self.assertTrue(moved)

        self.other_first_link_membership.refresh_from_db()
        later_successor_membership.refresh_from_db()

        self.assertEqual(
            self.other_first_link_membership.succession_position,
            0,
        )
        self.assertEqual(
            later_successor_membership.succession_position,
            1,
        )

    def test_f_del_loss_posts_first_link_removal(self):
        moved = (
            self.incoming_circle_membership.move_forward_one_position()
        )

        self.assertTrue(moved)

        messages = BackNForthChat.objects.filter(
            sec_del=self.first_link,
        )

        self.assertEqual(messages.count(), 1)

        message = messages.get()

        self.assertIsNone(message.sender)
        self.assertTrue(message.is_system)
        self.assertEqual(
            message.message,
            (
                "Succession update: outgoing-f-del was "
                "removed from First Link after losing the F-Del "
                "mandate required for membership."
            ),
        )

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
    )
    def test_sec_del_promotion_posts_and_emails(self):
        self.outgoing_f_del.email = "outgoing@example.com"
        self.outgoing_f_del.save(update_fields=["email"])

        self.incoming_f_del.email = "incoming-circle@example.com"
        self.incoming_f_del.save(update_fields=["email"])

        self.other_first_link_member.email = "incoming-first-link@example.com"
        self.other_first_link_member.save(update_fields=["email"])

        successor_circle = Group.objects.create(
            code="CAS04",
            district=self.district,
            invitation_code="NOTIFY-SUCCESSOR",
            group_type=0,
            parent_group=None,
        )

        GroupMember.objects.create(
            user=self.other_first_link_member,
            group=successor_circle,
            is_member=True,
            is_delegate=True,
        )

        SecDelMembers.objects.filter(
            pk=self.outgoing_first_link_membership.pk,
        ).update(
            is_delegate=True,
            succession_position=0,
        )
        SecDelMembers.objects.filter(
            pk=self.other_first_link_membership.pk,
        ).update(
            is_delegate=False,
            succession_position=1,
        )

        self.outgoing_f_del.users.userType = "U2D2"
        self.outgoing_f_del.users.save(
            update_fields=["userType"]
        )

        self.other_first_link_member.users.userType = "U2D1"
        self.other_first_link_member.users.save(
            update_fields=["userType"]
        )

        with self.captureOnCommitCallbacks(execute=True):
            moved = (
                self.incoming_circle_membership
                .move_forward_one_position()
            )

        self.assertTrue(moved)

        messages = BackNForthChat.objects.filter(
            sec_del=self.first_link,
        )

        self.assertEqual(messages.count(), 2)

        message_texts = set(
            messages.values_list("message", flat=True)
        )

        self.assertIn(
            (
                "Succession update: outgoing-f-del was "
                "removed from First Link after losing the "
                "F-Del mandate required for membership."
            ),
            message_texts,
        )

        self.assertIn(
            (
                "Succession update: other-first-link-member became "
                "Sec-Del after outgoing-f-del "
                "was removed. other-first-link-member moved from "
                "position 1 to position 0."
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
                    "incoming-circle@example.com": 1,
                    "incoming-first-link@example.com": 1,
                }
            ),
        )

    def test_first_link_compaction_posts_exact_position_change(self):
        later_successor = User.objects.create_user(
            username="later-first-link-successor",
            password="testpass",
        )
        later_successor.users.district = self.district
        later_successor.users.save()

        later_successor_circle = Group.objects.create(
            code="CAS05",
            district=self.district,
            invitation_code="NOTIFY-COMPACTION",
            group_type=0,
            parent_group=None,
        )

        GroupMember.objects.create(
            user=later_successor,
            group=later_successor_circle,
            is_member=True,
            is_delegate=True,
        )

        later_successor_membership = SecDelMembers.objects.create(
            user=later_successor,
            sec_del=self.first_link,
            is_member=True,
            is_delegate=False,
        )

        SecDelMembers.objects.filter(
            pk=self.outgoing_first_link_membership.pk,
        ).update(
            is_delegate=True,
            succession_position=0,
        )
        SecDelMembers.objects.filter(
            pk=self.other_first_link_membership.pk,
        ).update(
            is_delegate=False,
            succession_position=1,
        )

        moved = (
            self.incoming_circle_membership
            .move_forward_one_position()
        )

        self.assertTrue(moved)

        messages = BackNForthChat.objects.filter(
            sec_del=self.first_link,
        )

        self.assertEqual(messages.count(), 3)

        message_texts = set(
            messages.values_list("message", flat=True)
        )

        self.assertIn(
            (
                "Succession update: later-first-link-successor moved "
                "from position 2 to position 1 after "
                "outgoing-f-del was removed."
            ),
            message_texts,
        )

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
    )
    def test_removed_sec_del_without_successor_leaves_vacancy(
        self,
    ):
        self.outgoing_f_del.email = "outgoing@example.com"
        self.outgoing_f_del.save(
            update_fields=["email"]
        )

        self.incoming_f_del.email = "incoming@example.com"
        self.incoming_f_del.save(
            update_fields=["email"]
        )

        SecDelMembers.objects.filter(
            pk=self.other_first_link_membership.pk,
        ).delete()

        SecDelMembers.objects.filter(
            pk=self.outgoing_first_link_membership.pk,
        ).update(
            is_delegate=True,
            succession_position=0,
        )

        self.outgoing_f_del.users.userType = "U2D2"
        self.outgoing_f_del.users.save(
            update_fields=["userType"]
        )

        with self.captureOnCommitCallbacks(execute=True):
            moved = (
                self.incoming_circle_membership
                .move_forward_one_position()
            )

        self.assertTrue(moved)

        self.assertFalse(
            SecDelMembers.objects.filter(
                sec_del=self.first_link,
                is_member=True,
            ).exists()
        )

        messages = BackNForthChat.objects.filter(
            sec_del=self.first_link,
        )

        self.assertEqual(messages.count(), 2)

        message_texts = set(
            messages.values_list("message", flat=True)
        )

        self.assertIn(
            (
                "Succession update: Sec-Del position "
                "became vacant after outgoing-f-del was "
                "removed; no accepted successor is available."
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
                    "incoming@example.com": 1,
                }
            ),
        )