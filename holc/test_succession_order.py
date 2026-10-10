from django.contrib.auth.models import User
from django.test import TestCase

from holc.models import HolcMembers, HolcModel
from vote.models import Districts


class CaucusSuccessionOrderTests(TestCase):
    def setUp(self):
        self.district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT01",
        )

        self.founder = User.objects.create_user(
            username="caucus-succession-founder",
            password="testpass",
        )
        self.founder.users.district = self.district
        self.founder.users.save()

        self.first_applicant = User.objects.create_user(
            username="caucus-first-applicant",
            password="testpass",
        )
        self.first_applicant.users.district = self.district
        self.first_applicant.users.save()

        self.second_applicant = User.objects.create_user(
            username="caucus-second-applicant",
            password="testpass",
        )
        self.second_applicant.users.district = self.district
        self.second_applicant.users.save()

        self.caucus = HolcModel.objects.create(
            district=self.district,
            code=2,
        )

        self.founder_membership = HolcMembers.objects.create(
            user=self.founder,
            holc=self.caucus,
            is_member=True,
            is_delegate=True,
        )

        self.first_application = HolcMembers.objects.create(
            user=self.first_applicant,
            holc=self.caucus,
            is_member=False,
            is_delegate=False,
        )

        self.second_application = HolcMembers.objects.create(
            user=self.second_applicant,
            holc=self.caucus,
            is_member=False,
            is_delegate=False,
        )

    def test_succession_order_follows_acceptance_order(self):
        self.assertEqual(
            self.founder_membership.succession_position,
            0,
        )
        self.assertIsNone(
            self.first_application.succession_position,
        )
        self.assertIsNone(
            self.second_application.succession_position,
        )

        self.second_application.is_member = True
        self.second_application.save()

        self.first_application.is_member = True
        self.first_application.save()

        self.founder_membership.refresh_from_db()
        self.first_application.refresh_from_db()
        self.second_application.refresh_from_db()

        self.assertEqual(
            self.founder_membership.succession_position,
            0,
        )
        self.assertEqual(
            self.second_application.succession_position,
            1,
        )
        self.assertEqual(
            self.first_application.succession_position,
            2,
        )

    def test_member_can_move_forward_one_succession_position(self):
        self.first_application.is_member = True
        self.first_application.save()

        self.second_application.is_member = True
        self.second_application.save()

        self.assertEqual(
            self.founder_membership.succession_position,
            0,
        )
        self.assertEqual(
            self.first_application.succession_position,
            1,
        )
        self.assertEqual(
            self.second_application.succession_position,
            2,
        )

        moved = self.second_application.move_forward_one_position()

        self.assertTrue(moved)

        self.founder_membership.refresh_from_db()
        self.first_application.refresh_from_db()
        self.second_application.refresh_from_db()

        self.assertEqual(
            self.founder_membership.succession_position,
            0,
        )
        self.assertEqual(
            self.second_application.succession_position,
            1,
        )
        self.assertEqual(
            self.first_application.succession_position,
            2,
        )

        self.assertTrue(self.founder_membership.is_delegate)
        self.assertFalse(self.first_application.is_delegate)
        self.assertFalse(self.second_application.is_delegate)

    def test_first_successor_can_replace_holc(self):
        self.first_application.is_member = True
        self.first_application.save()

        self.assertEqual(
            self.founder_membership.succession_position,
            0,
        )
        self.assertEqual(
            self.first_application.succession_position,
            1,
        )
        self.assertTrue(self.founder_membership.is_delegate)
        self.assertFalse(self.first_application.is_delegate)

        moved = self.first_application.move_forward_one_position()

        self.assertTrue(moved)

        self.founder_membership.refresh_from_db()
        self.first_application.refresh_from_db()
        self.founder.users.refresh_from_db()
        self.first_applicant.users.refresh_from_db()

        self.assertEqual(
            self.first_application.succession_position,
            0,
        )
        self.assertEqual(
            self.founder_membership.succession_position,
            1,
        )

        self.assertTrue(self.first_application.is_delegate)
        self.assertFalse(self.founder_membership.is_delegate)

        self.assertEqual(
            self.first_applicant.users.userType,
            "U4D4",
        )
        self.assertEqual(
            self.founder.users.userType,
            "U4D3",
        )

    def test_pending_applicant_cannot_move_forward(self):
        self.assertFalse(self.first_application.is_member)
        self.assertIsNone(self.first_application.succession_position)

        moved = self.first_application.move_forward_one_position()

        self.assertFalse(moved)

        self.first_application.refresh_from_db()
        self.founder_membership.refresh_from_db()

        self.assertIsNone(self.first_application.succession_position)
        self.assertEqual(
            self.founder_membership.succession_position,
            0,
        )
        self.assertTrue(self.founder_membership.is_delegate)

    def test_holc_cannot_move_forward(self):
        self.assertEqual(
            self.founder_membership.succession_position,
            0,
        )
        self.assertTrue(self.founder_membership.is_delegate)

        moved = self.founder_membership.move_forward_one_position()

        self.assertFalse(moved)

        self.founder_membership.refresh_from_db()

        self.assertEqual(
            self.founder_membership.succession_position,
            0,
        )
        self.assertTrue(self.founder_membership.is_delegate)
