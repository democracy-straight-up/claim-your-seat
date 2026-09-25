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
