from django.contrib.auth.models import User
from django.test import TestCase

from api.models import SecDelMembers, SecDelModel
from vote.models import Districts, Group, GroupMember


class CircleDelegateHigherLevelSuccessionTests(TestCase):
    def setUp(self):
        self.district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT01",
        )

        self.first_link_delegate = User.objects.create_user(
            username="first-link-delegate",
            password="testpass",
        )
        self.first_link_delegate.users.district = self.district
        self.first_link_delegate.users.save()

        self.outgoing_circle_delegate = User.objects.create_user(
            username="outgoing-circle-delegate",
            password="testpass",
        )
        self.outgoing_circle_delegate.users.district = self.district
        self.outgoing_circle_delegate.users.save()

        self.incoming_circle_delegate = User.objects.create_user(
            username="incoming-circle-delegate",
            password="testpass",
        )
        self.incoming_circle_delegate.users.district = self.district
        self.incoming_circle_delegate.users.save()

        self.circle = Group.objects.create(
            code="CAS01",
            district=self.district,
            invitation_code="CASCADE",
            group_type=0,
            parent_group=None,
        )

        self.outgoing_circle_membership = GroupMember.objects.create(
            user=self.outgoing_circle_delegate,
            group=self.circle,
            is_member=True,
            is_delegate=True,
        )

        self.incoming_circle_membership = GroupMember.objects.create(
            user=self.incoming_circle_delegate,
            group=self.circle,
            is_member=True,
            is_delegate=False,
        )

        self.first_link = SecDelModel.objects.create(
            district=self.district,
        )

        self.first_link_delegate_membership = SecDelMembers.objects.create(
            user=self.first_link_delegate,
            sec_del=self.first_link,
            is_member=True,
            is_delegate=True,
        )

        self.outgoing_first_link_membership = SecDelMembers.objects.create(
            user=self.outgoing_circle_delegate,
            sec_del=self.first_link,
            is_member=True,
            is_delegate=False,
        )

        self.outgoing_circle_delegate.users.userType = "U2D1"
        self.outgoing_circle_delegate.users.save(
            update_fields=["userType"]
        )

    def test_replaced_circle_delegate_loses_first_link_membership(self):
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
                user=self.incoming_circle_delegate,
                sec_del=self.first_link,
            ).exists()
        )

        self.outgoing_circle_delegate.users.refresh_from_db()
        self.incoming_circle_delegate.users.refresh_from_db()

        self.assertEqual(
            self.outgoing_circle_delegate.users.userType,
            "U1D0",
        )
        self.assertEqual(
            self.incoming_circle_delegate.users.userType,
            "U1D1",
        )

        self.first_link_delegate_membership.refresh_from_db()

        self.assertTrue(
            self.first_link_delegate_membership.is_delegate
        )
        self.assertEqual(
            self.first_link_delegate_membership.succession_position,
            0,
        )

    def test_first_link_successor_replaces_removed_delegate(self):
        successor_circle = Group.objects.create(
            code="CAS02",
            district=self.district,
            invitation_code="SUCCESSOR",
            group_type=0,
            parent_group=None,
        )

        GroupMember.objects.create(
            user=self.first_link_delegate,
            group=successor_circle,
            is_member=True,
            is_delegate=True,
        )

        # For this scenario, the outgoing Circle delegate is also the
        # First-Link delegate, and the other accepted member is first
        # in that First Link's succession line.
        SecDelMembers.objects.filter(
            pk=self.outgoing_first_link_membership.pk,
        ).update(
            is_delegate=True,
            succession_position=0,
        )
        SecDelMembers.objects.filter(
            pk=self.first_link_delegate_membership.pk,
        ).update(
            is_delegate=False,
            succession_position=1,
        )

        self.outgoing_circle_delegate.users.userType = "U2D2"
        self.outgoing_circle_delegate.users.save(
            update_fields=["userType"]
        )

        self.first_link_delegate.users.userType = "U2D1"
        self.first_link_delegate.users.save(
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

        self.first_link_delegate_membership.refresh_from_db()
        self.first_link_delegate.users.refresh_from_db()

        self.assertTrue(
            self.first_link_delegate_membership.is_delegate
        )
        self.assertEqual(
            self.first_link_delegate_membership.succession_position,
            0,
        )
        self.assertEqual(
            self.first_link_delegate.users.userType,
            "U2D2",
        )

    def test_first_link_succession_positions_compact_after_delegate_removal(self):
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

        # Make the outgoing Circle delegate the current First-Link
        # delegate. The existing First-Link member is first successor,
        # and the newly added member is second successor.
        SecDelMembers.objects.filter(
            pk=self.outgoing_first_link_membership.pk,
        ).update(
            is_delegate=True,
            succession_position=0,
        )
        SecDelMembers.objects.filter(
            pk=self.first_link_delegate_membership.pk,
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

        self.first_link_delegate_membership.refresh_from_db()
        later_successor_membership.refresh_from_db()

        self.assertEqual(
            self.first_link_delegate_membership.succession_position,
            0,
        )
        self.assertEqual(
            later_successor_membership.succession_position,
            1,
        )
