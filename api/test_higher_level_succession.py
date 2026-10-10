from django.contrib.auth.models import User
from django.test import TestCase

from api.models import SecDelMembers, SecDelModel
from moda.models import ModaMembers, ModaModel
from vote.models import Districts


class FirstLinkDelegateHigherLevelSuccessionTests(TestCase):
    def setUp(self):
        self.district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT01",
        )

        self.outgoing_first_link_delegate = User.objects.create_user(
            username="outgoing-first-link-delegate",
            password="testpass",
        )
        self.outgoing_first_link_delegate.users.district = self.district
        self.outgoing_first_link_delegate.users.save()

        self.incoming_first_link_delegate = User.objects.create_user(
            username="incoming-first-link-delegate",
            password="testpass",
        )
        self.incoming_first_link_delegate.users.district = self.district
        self.incoming_first_link_delegate.users.save()

        self.second_link_delegate = User.objects.create_user(
            username="second-link-delegate",
            password="testpass",
        )
        self.second_link_delegate.users.district = self.district
        self.second_link_delegate.users.save()

        self.first_link = SecDelModel.objects.create(
            district=self.district,
        )

        self.outgoing_first_link_membership = (
            SecDelMembers.objects.create(
                user=self.outgoing_first_link_delegate,
                sec_del=self.first_link,
                is_member=True,
                is_delegate=True,
            )
        )

        self.incoming_first_link_membership = (
            SecDelMembers.objects.create(
                user=self.incoming_first_link_delegate,
                sec_del=self.first_link,
                is_member=True,
                is_delegate=False,
            )
        )

        self.incoming_first_link_delegate.users.userType = "U2D1"
        self.incoming_first_link_delegate.users.save(
            update_fields=["userType"]
        )

        self.second_link = ModaModel.objects.create(
            district=self.district,
        )

        self.second_link_delegate_membership = (
            ModaMembers.objects.create(
                user=self.second_link_delegate,
                moda=self.second_link,
                is_member=True,
                is_delegate=True,
            )
        )

        self.outgoing_second_link_membership = (
            ModaMembers.objects.create(
                user=self.outgoing_first_link_delegate,
                moda=self.second_link,
                is_member=True,
                is_delegate=False,
            )
        )

        self.outgoing_first_link_delegate.users.userType = "U3D2"
        self.outgoing_first_link_delegate.users.save(
            update_fields=["userType"]
        )

    def test_replaced_first_link_delegate_loses_second_link_membership(self):
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
                user=self.incoming_first_link_delegate,
                moda=self.second_link,
            ).exists()
        )

        self.outgoing_first_link_delegate.users.refresh_from_db()
        self.incoming_first_link_delegate.users.refresh_from_db()

        self.assertEqual(
            self.outgoing_first_link_delegate.users.userType,
            "U2D1",
        )
        self.assertEqual(
            self.incoming_first_link_delegate.users.userType,
            "U2D2",
        )

        self.second_link_delegate_membership.refresh_from_db()

        self.assertTrue(
            self.second_link_delegate_membership.is_delegate
        )
        self.assertEqual(
            self.second_link_delegate_membership.succession_position,
            0,
        )