from django.contrib.auth.models import User
from django.test import TestCase

from holc.models import HolcMembers, HolcModel
from vote.models import Districts


class CaucusActivityTests(TestCase):
    def test_caucus_is_active_with_one_accepted_member(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )
        caucus = HolcModel.objects.create(district=district)

        founder = User.objects.create_user(
            username="caucus-founder",
            email="founder@example.com",
        )
        founder.users.district = district
        founder.users.legalName = "Test Founder"
        founder.users.address = "1 Test Street"
        founder.users.userType = "U4D3"
        founder.users.save()

        HolcMembers.objects.create(
            user=founder,
            holc=caucus,
            is_member=True,
        )

        self.assertEqual(caucus.member_count, 1)
        self.assertTrue(caucus.is_active)

        caucus.refresh_from_db()
        self.assertTrue(caucus.status)
    def test_caucus_accepts_fourteen_members_and_remains_active(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )
        caucus = HolcModel.objects.create(district=district)

        for number in range(14):
            user = User.objects.create_user(
                username=f"caucus-member-{number}",
                email=f"member{number}@example.com",
            )
            user.users.district = district
            user.users.legalName = f"Test Member {number}"
            user.users.address = "1 Test Street"
            user.users.userType = "U4D3"
            user.users.save()

            HolcMembers.objects.create(
                user=user,
                holc=caucus,
                is_member=True,
            )

        self.assertEqual(caucus.member_count, 14)
        self.assertTrue(caucus.is_active)

        caucus.refresh_from_db()
        self.assertTrue(caucus.status)
    def test_empty_caucus_clears_active_status(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )
        caucus = HolcModel.objects.create(
            district=district,
            status=True,
        )

        self.assertEqual(caucus.member_count, 0)
        self.assertFalse(caucus.is_active)

        caucus.refresh_from_db()
        self.assertFalse(caucus.status)