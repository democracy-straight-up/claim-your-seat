from django.contrib.auth.models import User
from django.test import TestCase
from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError

from holc.models import HolcMembers, HolcModel
from moda.models import ModaMembers, ModaModel
from vote.models import Districts



class SecondLinkRoleTests(TestCase):
    def test_founder_gets_caucus_delegate_role_before_activation(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )
        founder = User.objects.create_user(
            username="second-link-founder",
            email="founder@example.com",
        )
        founder.users.district = district
        founder.users.legalName = "Test Founder"
        founder.users.address = "1 Test Street"
        founder.users.userType = "U2D2"
        founder.users.save()

        second_link = ModaModel.objects.create(district=district)
        membership = ModaMembers.objects.create(
            user=founder,
            moda=second_link,
            is_member=True,
        )

        membership.refresh_from_db()
        founder.users.refresh_from_db()

        self.assertTrue(membership.is_member)
        self.assertTrue(membership.is_delegate)
        self.assertEqual(second_link.member_count, 1)
        self.assertFalse(second_link.is_active)
        self.assertFalse(
            HolcMembers.objects.filter(user=founder).exists()
        )
        self.assertEqual(founder.users.userType, "U4D3")
    def test_second_link_activates_only_with_six_accepted_members(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )
        second_link = ModaModel.objects.create(district=district)
        memberships = []

        for number in range(6):
            user = User.objects.create_user(
                username=f"link-member-{number}",
                email=f"member{number}@example.com",
            )
            user.users.district = district
            user.users.legalName = f"Test Member {number}"
            user.users.address = "1 Test Street"
            user.users.userType = "U2D2"
            user.users.save()

            memberships.append(
                ModaMembers.objects.create(
                    user=user,
                    moda=second_link,
                    is_member=number < 5,
                )
            )

        # Five accepted members and one pending candidate.
        self.assertEqual(second_link.member_count, 5)
        self.assertFalse(second_link.is_active)
        second_link.refresh_from_db()
        self.assertFalse(second_link.status)
        self.assertFalse(
            HolcMembers.objects.filter(
                user=memberships[0].user
            ).exists()
        )

        # Accept the sixth member.
        candidate = memberships[5]
        candidate.is_member = True
        candidate.save()

        self.assertEqual(second_link.member_count, 6)
        self.assertTrue(second_link.is_active)
        second_link.refresh_from_db()
        self.assertTrue(second_link.status)
    def test_activation_assigns_delegate_to_general_caucus(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )

        # An ordinary Caucus must not receive the delegate automatically.
        ordinary_caucus = HolcModel.objects.create(
            district=district,
            code=2,
        )
        second_link = ModaModel.objects.create(district=district)
        founder = None

        for number in range(6):
            user = User.objects.create_user(
                username=f"general-member-{number}",
                email=f"general{number}@example.com",
            )
            user.users.district = district
            user.users.legalName = f"Test Member {number}"
            user.users.address = "1 Test Street"
            user.users.userType = "U2D2"
            user.users.save()

            ModaMembers.objects.create(
                user=user,
                moda=second_link,
                is_member=True,
            )

            if number == 0:
                founder = user

        # Evaluating is_active currently triggers activation processing.
        self.assertTrue(second_link.is_active)

        membership = HolcMembers.objects.get(user=founder)
        self.assertEqual(membership.holc.district_id, district.pk)
        self.assertEqual(membership.holc.code, 1)
        self.assertTrue(membership.is_member)

        # The first General Caucus member becomes its HoLC.
        self.assertTrue(membership.is_delegate)
        founder.users.refresh_from_db()
        self.assertEqual(founder.users.userType, "U4D4")
        self.assertFalse(
            ordinary_caucus.holcmembers_set.filter(user=founder).exists()
        )
    def test_each_district_can_have_its_own_general_caucus(self):
        vermont = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )
        tennessee = Districts.objects.create(
            name="Tennessee First",
            code="TN01",
        )

        vermont_general = HolcModel.objects.create(
            district=vermont,
            code=1,
        )
        tennessee_general = HolcModel.objects.create(
            district=tennessee,
            code=1,
        )

        vermont_general.refresh_from_db()
        tennessee_general.refresh_from_db()

        self.assertNotEqual(vermont_general.pk, tennessee_general.pk)
        self.assertEqual(vermont_general.code, 1)
        self.assertEqual(tennessee_general.code, 1)
        self.assertEqual(vermont_general.district_id, vermont.pk)
        self.assertEqual(tennessee_general.district_id, tennessee.pk)
    def test_database_rejects_duplicate_caucus_number_in_same_district(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )
        HolcModel.objects.create(district=district, code=1)

        # bulk_create bypasses save() and its model validation.
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                HolcModel.objects.bulk_create([
                    HolcModel(district=district, code=1),
                ])

        self.assertEqual(
            HolcModel.objects.filter(district=district, code=1).count(),
            1,
        )
    def test_ordinary_caucus_numbering_starts_at_two(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )

        first_caucus = HolcModel.objects.create(district=district)
        second_caucus = HolcModel.objects.create(district=district)

        first_caucus.refresh_from_db()
        second_caucus.refresh_from_db()

        self.assertEqual(first_caucus.code, 2)
        self.assertEqual(second_caucus.code, 3)
        self.assertFalse(
            HolcModel.objects.filter(district=district, code=1).exists()
        )
    def test_deleted_caucus_number_stays_retired_before_ninety_nine(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )
        first_caucus = HolcModel.objects.create(district=district)
        self.assertEqual(first_caucus.code, 2)

        # Delete the record directly to test numbering independently
        # of the membership and dissolution workflow.
        HolcModel.objects.filter(pk=first_caucus.pk).delete()

        self.assertFalse(
            HolcModel.objects.filter(district=district).exists()
        )

        next_caucus = HolcModel.objects.create(district=district)
        self.assertEqual(next_caucus.code, 3)
    def test_retired_numbers_are_reused_only_after_ninety_nine(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )
        caucuses = {}

        for expected_code in range(2, 99):
            caucus = HolcModel.objects.create(district=district)
            self.assertEqual(caucus.code, expected_code)
            caucuses[expected_code] = caucus.pk

        # Retire two numbers before reaching 99.
        HolcModel.objects.filter(
            pk__in=[caucuses[2], caucuses[4]],
        ).delete()

        last_new_number = HolcModel.objects.create(district=district)
        self.assertEqual(last_new_number.code, 99)

        # Reuse the lowest available numbers, skipping occupied 03.
        first_reused = HolcModel.objects.create(district=district)
        second_reused = HolcModel.objects.create(district=district)

        self.assertEqual(first_reused.code, 2)
        self.assertEqual(second_reused.code, 4)
        self.assertNotEqual(first_reused.pk, caucuses[2])
        self.assertNotEqual(second_reused.pk, caucuses[4])

        # General Caucus 01 remains reserved.
        self.assertFalse(
            HolcModel.objects.filter(district=district, code=1).exists()
        )
    def test_ordinary_caucus_numbering_is_independent_per_district(self):
        vermont = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )
        tennessee = Districts.objects.create(
            name="Tennessee First",
            code="TN01",
        )

        vermont_first = HolcModel.objects.create(district=vermont)
        vermont_second = HolcModel.objects.create(district=vermont)
        tennessee_first = HolcModel.objects.create(district=tennessee)
        tennessee_second = HolcModel.objects.create(district=tennessee)

        self.assertEqual(
            [vermont_first.code, vermont_second.code],
            [2, 3],
        )
        self.assertEqual(
            [tennessee_first.code, tennessee_second.code],
            [2, 3],
        )

    def test_creation_is_blocked_when_all_ordinary_numbers_are_occupied(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )

        for expected_code in range(2, 100):
            caucus = HolcModel.objects.create(district=district)
            self.assertEqual(caucus.code, expected_code)

        with self.assertRaisesMessage(
            ValidationError,
            "All ordinary Caucus numbers (02–99) "
            "are currently in use in this district.",
        ):
            HolcModel.objects.create(district=district)

        self.assertEqual(
            HolcModel.objects.filter(district=district).count(),
            98,
        )
        self.assertFalse(
            HolcModel.objects.filter(district=district, code=1).exists()
        )
    def test_explicit_code_cannot_reuse_retired_number_before_ninety_nine(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )
        original = HolcModel.objects.create(district=district)
        self.assertEqual(original.code, 2)

        HolcModel.objects.filter(pk=original.pk).delete()

        with self.assertRaises(ValidationError):
            HolcModel.objects.create(
                district=district,
                code=2,
            )

        self.assertFalse(
            HolcModel.objects.filter(district=district, code=2).exists()
        )

        next_caucus = HolcModel.objects.create(district=district)
        self.assertEqual(next_caucus.code, 3)
    def test_existing_caucus_cannot_take_a_retired_number(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )
        first = HolcModel.objects.create(district=district)
        second = HolcModel.objects.create(district=district)

        self.assertEqual(first.code, 2)
        self.assertEqual(second.code, 3)

        HolcModel.objects.filter(pk=first.pk).delete()

        second.code = 2
        with self.assertRaises(ValidationError):
            second.save()

        second.refresh_from_db()
        self.assertEqual(second.code, 3)
    def test_existing_caucus_cannot_change_district(self):
        vermont = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )
        tennessee = Districts.objects.create(
            name="Tennessee First",
            code="TN01",
        )
        caucus = HolcModel.objects.create(district=vermont)

        caucus.district = tennessee
        with self.assertRaises(ValidationError):
            caucus.save()

        caucus.refresh_from_db()
        self.assertEqual(caucus.district_id, vermont.pk)
        self.assertEqual(caucus.code, 2)