from django.contrib.auth.models import User
from django.test import TestCase

from holc.models import HolcMembers, HolcModel
from moda.models import ModaMembers, ModaModel
from vote.models import Districts


class SecondLinkDelegateHigherLevelSuccessionTests(TestCase):
    def setUp(self):
        self.district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT01",
        )

        self.outgoing_second_link_delegate = User.objects.create_user(
            username="outgoing-second-link-delegate",
            password="testpass",
        )
        self.outgoing_second_link_delegate.users.district = self.district
        self.outgoing_second_link_delegate.users.save()

        self.incoming_second_link_delegate = User.objects.create_user(
            username="incoming-second-link-delegate",
            password="testpass",
        )
        self.incoming_second_link_delegate.users.district = self.district
        self.incoming_second_link_delegate.users.save()

        self.holc = User.objects.create_user(
            username="existing-holc",
            password="testpass",
        )
        self.holc.users.district = self.district
        self.holc.users.save()

        self.second_link = ModaModel.objects.create(
            district=self.district,
        )

        self.outgoing_second_link_membership = (
            ModaMembers.objects.create(
                user=self.outgoing_second_link_delegate,
                moda=self.second_link,
                is_member=True,
                is_delegate=True,
            )
        )

        self.incoming_second_link_membership = (
            ModaMembers.objects.create(
                user=self.incoming_second_link_delegate,
                moda=self.second_link,
                is_member=True,
                is_delegate=False,
            )
        )

        self.incoming_second_link_delegate.users.userType = "U3D2"
        self.incoming_second_link_delegate.users.save(
            update_fields=["userType"]
        )

        self.caucus = HolcModel.objects.create(
            district=self.district,
            code=2,
        )

        self.holc_membership = HolcMembers.objects.create(
            user=self.holc,
            holc=self.caucus,
            is_member=True,
            is_delegate=True,
        )

        self.outgoing_caucus_membership = HolcMembers.objects.create(
            user=self.outgoing_second_link_delegate,
            holc=self.caucus,
            is_member=True,
            is_delegate=False,
        )

        self.outgoing_second_link_delegate.users.userType = "U4D3"
        self.outgoing_second_link_delegate.users.save(
            update_fields=["userType"]
        )

    def test_replaced_second_link_delegate_loses_caucus_membership(self):
        self.assertTrue(
            HolcMembers.objects.filter(
                pk=self.outgoing_caucus_membership.pk,
                is_member=True,
            ).exists()
        )

        moved = (
            self.incoming_second_link_membership
            .move_forward_one_position()
        )

        self.assertTrue(moved)

        self.assertFalse(
            HolcMembers.objects.filter(
                pk=self.outgoing_caucus_membership.pk,
            ).exists()
        )

        self.assertFalse(
            HolcMembers.objects.filter(
                user=self.incoming_second_link_delegate,
                holc=self.caucus,
            ).exists()
        )

        self.outgoing_second_link_delegate.users.refresh_from_db()
        self.incoming_second_link_delegate.users.refresh_from_db()

        self.assertEqual(
            self.outgoing_second_link_delegate.users.userType,
            "U3D2",
        )
        self.assertEqual(
            self.incoming_second_link_delegate.users.userType,
            "U4D3",
        )

        self.holc_membership.refresh_from_db()

        self.assertTrue(
            self.holc_membership.is_delegate
        )
        self.assertEqual(
            self.holc_membership.succession_position,
            0,
        )

    def test_caucus_successor_replaces_removed_holc(self):
        successor_second_link = ModaModel.objects.create(
            district=self.district,
        )

        ModaMembers.objects.create(
            user=self.holc,
            moda=successor_second_link,
            is_member=True,
            is_delegate=True,
        )

        # For this scenario, the outgoing Second-Link delegate is also
        # the HoLC, and the existing Caucus member is first in that
        # Caucus's succession line.
        HolcMembers.objects.filter(
            pk=self.outgoing_caucus_membership.pk,
        ).update(
            is_delegate=True,
            succession_position=0,
        )
        HolcMembers.objects.filter(
            pk=self.holc_membership.pk,
        ).update(
            is_delegate=False,
            succession_position=1,
        )

        self.outgoing_second_link_delegate.users.userType = "U4D4"
        self.outgoing_second_link_delegate.users.save(
            update_fields=["userType"]
        )

        self.holc.users.userType = "U4D3"
        self.holc.users.save(
            update_fields=["userType"]
        )

        moved = (
            self.incoming_second_link_membership
            .move_forward_one_position()
        )

        self.assertTrue(moved)

        self.assertFalse(
            HolcMembers.objects.filter(
                pk=self.outgoing_caucus_membership.pk,
            ).exists()
        )

        self.holc_membership.refresh_from_db()
        self.holc.users.refresh_from_db()

        self.assertTrue(
            self.holc_membership.is_delegate
        )
        self.assertEqual(
            self.holc_membership.succession_position,
            0,
        )
        self.assertEqual(
            self.holc.users.userType,
            "U4D4",
        )

    def test_caucus_succession_positions_compact_after_holc_removal(self):
        later_successor = User.objects.create_user(
            username="later-caucus-successor",
            password="testpass",
        )
        later_successor.users.district = self.district
        later_successor.users.save()

        later_successor_second_link = ModaModel.objects.create(
            district=self.district,
        )

        ModaMembers.objects.create(
            user=later_successor,
            moda=later_successor_second_link,
            is_member=True,
            is_delegate=True,
        )

        later_successor_membership = HolcMembers.objects.create(
            user=later_successor,
            holc=self.caucus,
            is_member=True,
            is_delegate=False,
        )

        # Make the outgoing Second-Link delegate the current HoLC.
        # The existing Caucus member is first successor, and the
        # newly added member is second successor.
        HolcMembers.objects.filter(
            pk=self.outgoing_caucus_membership.pk,
        ).update(
            is_delegate=True,
            succession_position=0,
        )
        HolcMembers.objects.filter(
            pk=self.holc_membership.pk,
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
            self.incoming_second_link_membership
            .move_forward_one_position()
        )

        self.assertTrue(moved)

        self.holc_membership.refresh_from_db()
        later_successor_membership.refresh_from_db()

        self.assertEqual(
            self.holc_membership.succession_position,
            0,
        )
        self.assertEqual(
            later_successor_membership.succession_position,
            1,
        )
