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
