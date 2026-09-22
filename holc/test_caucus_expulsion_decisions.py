from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from holc.views import HolcMembersViewSet
from holc.models import CaucusExpulsionVote, HolcMembers, HolcModel
from holc.transitions import cast_caucus_expulsion_vote
from moda.models import ModaMembers, ModaModel
from vote.models import Districts


class CaucusExpulsionDecisionTests(TestCase):
    def test_majority_expels_eligible_delegate_to_general(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )

        target = User.objects.create_user(
            username="expulsion-target",
            email="expulsion-target@example.com",
        )
        target.users.district = district
        target.users.legalName = "Expulsion Target"
        target.users.address = "1 Test Street"
        target.users.userType = "U2D2"
        target.users.save()

        second_link = ModaModel.objects.create(
            district=district,
            status=True,
        )
        ModaMembers.objects.create(
            user=target,
            moda=second_link,
            is_member=True,
        )

        general_holc = User.objects.create_user(
            username="expulsion-general-holc",
            email="expulsion-general-holc@example.com",
        )
        general_holc.users.district = district
        general_holc.users.legalName = "General HoLC"
        general_holc.users.address = "2 Test Street"
        general_holc.users.userType = "U4D3"
        general_holc.users.save()

        general = HolcModel.objects.create(
            district=district,
            code=1,
        )
        HolcMembers.objects.create(
            user=general_holc,
            holc=general,
            is_member=True,
        )

        ordinary = HolcModel.objects.create(district=district)
        voters = []

        for number in range(2):
            voter = User.objects.create_user(
                username=f"expulsion-voter-{number}",
                email=f"expulsion-voter-{number}@example.com",
            )
            voter.users.district = district
            voter.users.legalName = f"Expulsion Voter {number}"
            voter.users.address = "3 Test Street"
            voter.users.userType = "U4D3"
            voter.users.save()

            membership = HolcMembers.objects.create(
                user=voter,
                holc=ordinary,
                is_member=True,
            )

            if number > 0:
                membership.is_delegate = False
                membership.save(update_fields=["is_delegate"])

            voters.append(voter)

        target_membership = HolcMembers.objects.create(
            user=target,
            holc=ordinary,
            is_member=True,
            is_delegate=False,
        )

        # Three accepted members require two votes for a majority.
        cast_caucus_expulsion_vote(
            voter=voters[0],
            target_membership=target_membership,
        )

        self.assertTrue(
            HolcMembers.objects.filter(
                pk=target_membership.pk,
                is_member=True,
            ).exists()
        )

        self.assertEqual(
            CaucusExpulsionVote.objects.filter(
                target_user=target,
                caucus=ordinary,
            ).count(),
            1,
        )

        result = cast_caucus_expulsion_vote(
            voter=voters[1],
            target_membership=target_membership,
        )

        self.assertEqual(result.holc, general)
        self.assertTrue(result.is_member)
        self.assertFalse(result.is_delegate)

        self.assertFalse(
            HolcMembers.objects.filter(
                pk=target_membership.pk,
            ).exists()
        )

        self.assertTrue(
            HolcMembers.objects.filter(
                user=target,
                holc=general,
                is_member=True,
                is_delegate=False,
            ).exists()
        )

        # Expulsion votes remain as an audit record after the ordinary
        # Caucus membership itself has been removed.
        self.assertEqual(
            CaucusExpulsionVote.objects.filter(
                target_user=target,
                caucus=ordinary,
            ).count(),
            2,
        )

        self.assertTrue(
            ModaMembers.objects.filter(
                user=target,
                moda=second_link,
                is_member=True,
                is_delegate=True,
                moda__status=True,
            ).exists()
        )

        target.users.refresh_from_db()
        self.assertEqual(target.users.userType, "U4D3")
        
    def test_accepted_member_can_cast_expulsion_vote_through_api(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )

        voter = User.objects.create_user(
            username="api-expulsion-voter",
            email="api-expulsion-voter@example.com",
        )
        voter.users.district = district
        voter.users.legalName = "API Expulsion Voter"
        voter.users.address = "1 Test Street"
        voter.users.userType = "U4D3"
        voter.users.save()

        target = User.objects.create_user(
            username="api-expulsion-target",
            email="api-expulsion-target@example.com",
        )
        target.users.district = district
        target.users.legalName = "API Expulsion Target"
        target.users.address = "2 Test Street"
        target.users.userType = "U4D3"
        target.users.save()

        ordinary = HolcModel.objects.create(district=district)

        HolcMembers.objects.create(
            user=voter,
            holc=ordinary,
            is_member=True,
        )

        target_membership = HolcMembers.objects.create(
            user=target,
            holc=ordinary,
            is_member=True,
            is_delegate=False,
        )

        request = APIRequestFactory().post(
            f"/holc-members/{target_membership.pk}/vote_expulsion/",
            {},
            format="json",
        )
        force_authenticate(request, user=voter)

        response = HolcMembersViewSet.as_view(
            {"post": "vote_expulsion"}
        )(
            request,
            pk=target_membership.pk,
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            CaucusExpulsionVote.objects.filter(
                voter=voter,
                target_user=target,
                caucus=ordinary,
                target_membership_id=target_membership.pk,
            ).count(),
            1,
        )

        target_membership.refresh_from_db()
        self.assertTrue(target_membership.is_member)

    def test_api_majority_vote_completes_expulsion_to_general(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )

        target = User.objects.create_user(
            username="api-expulsion-majority-target",
            email="api-expulsion-majority-target@example.com",
        )
        target.users.district = district
        target.users.legalName = "API Expulsion Majority Target"
        target.users.address = "1 Test Street"
        target.users.userType = "U2D2"
        target.users.save()

        second_link = ModaModel.objects.create(
            district=district,
            status=True,
        )
        ModaMembers.objects.create(
            user=target,
            moda=second_link,
            is_member=True,
        )

        general_holc = User.objects.create_user(
            username="api-expulsion-general-holc",
            email="api-expulsion-general-holc@example.com",
        )
        general_holc.users.district = district
        general_holc.users.legalName = "General HoLC"
        general_holc.users.address = "2 Test Street"
        general_holc.users.userType = "U4D3"
        general_holc.users.save()

        general = HolcModel.objects.create(
            district=district,
            code=1,
        )
        HolcMembers.objects.create(
            user=general_holc,
            holc=general,
            is_member=True,
        )

        ordinary = HolcModel.objects.create(district=district)
        voters = []

        for number in range(2):
            voter = User.objects.create_user(
                username=f"api-expulsion-majority-voter-{number}",
                email=f"api-expulsion-majority-voter-{number}@example.com",
            )
            voter.users.district = district
            voter.users.legalName = (
                f"API Expulsion Majority Voter {number}"
            )
            voter.users.address = "3 Test Street"
            voter.users.userType = "U4D3"
            voter.users.save()

            membership = HolcMembers.objects.create(
                user=voter,
                holc=ordinary,
                is_member=True,
            )

            if number > 0:
                membership.is_delegate = False
                membership.save(update_fields=["is_delegate"])

            voters.append(voter)

        target_membership = HolcMembers.objects.create(
            user=target,
            holc=ordinary,
            is_member=True,
            is_delegate=False,
        )
        target_membership_id = target_membership.pk

        first_request = APIRequestFactory().post(
            f"/holc-members/{target_membership_id}/vote_expulsion/",
            {},
            format="json",
        )
        force_authenticate(first_request, user=voters[0])

        first_response = HolcMembersViewSet.as_view(
            {"post": "vote_expulsion"}
        )(
            first_request,
            pk=target_membership_id,
        )

        self.assertEqual(first_response.status_code, 200)

        self.assertTrue(
            HolcMembers.objects.filter(
                pk=target_membership_id,
                is_member=True,
            ).exists()
        )

        second_request = APIRequestFactory().post(
            f"/holc-members/{target_membership_id}/vote_expulsion/",
            {},
            format="json",
        )
        force_authenticate(second_request, user=voters[1])

        second_response = HolcMembersViewSet.as_view(
            {"post": "vote_expulsion"}
        )(
            second_request,
            pk=target_membership_id,
        )

        self.assertEqual(second_response.status_code, 200)

        self.assertFalse(
            HolcMembers.objects.filter(
                pk=target_membership_id,
            ).exists()
        )

        self.assertTrue(
            HolcMembers.objects.filter(
                user=target,
                holc=general,
                is_member=True,
                is_delegate=False,
            ).exists()
        )

        self.assertEqual(
            CaucusExpulsionVote.objects.filter(
                target_user=target,
                caucus=ordinary,
                target_membership_id=target_membership_id,
            ).count(),
            2,
        )

        self.assertTrue(
            ModaMembers.objects.filter(
                user=target,
                moda=second_link,
                is_member=True,
                is_delegate=True,
                moda__status=True,
            ).exists()
        )

        target.users.refresh_from_db()
        self.assertEqual(target.users.userType, "U4D3")

    def test_holc_cannot_be_targeted_by_ordinary_expulsion(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )

        holc_user = User.objects.create_user(
            username="expulsion-protected-holc",
            email="expulsion-protected-holc@example.com",
        )
        holc_user.users.district = district
        holc_user.users.legalName = "Protected HoLC"
        holc_user.users.address = "1 Test Street"
        holc_user.users.userType = "U4D3"
        holc_user.users.save()

        voter = User.objects.create_user(
            username="holc-expulsion-voter",
            email="holc-expulsion-voter@example.com",
        )
        voter.users.district = district
        voter.users.legalName = "HoLC Expulsion Voter"
        voter.users.address = "2 Test Street"
        voter.users.userType = "U4D3"
        voter.users.save()

        ordinary = HolcModel.objects.create(district=district)

        holc_membership = HolcMembers.objects.create(
            user=holc_user,
            holc=ordinary,
            is_member=True,
        )

        self.assertTrue(holc_membership.is_delegate)

        voter_membership = HolcMembers.objects.create(
            user=voter,
            holc=ordinary,
            is_member=True,
        )
        voter_membership.is_delegate = False
        voter_membership.save(update_fields=["is_delegate"])

        with self.assertRaises(ValidationError):
            cast_caucus_expulsion_vote(
                voter=voter,
                target_membership=holc_membership,
            )

        self.assertEqual(
            CaucusExpulsionVote.objects.filter(
                target_user=holc_user,
                caucus=ordinary,
                target_membership_id=holc_membership.pk,
            ).count(),
            0,
        )

        holc_membership.refresh_from_db()
        self.assertTrue(holc_membership.is_member)
        self.assertTrue(holc_membership.is_delegate)

    def test_general_caucus_cannot_use_ordinary_expulsion(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )

        general_holc = User.objects.create_user(
            username="general-expulsion-holc",
            email="general-expulsion-holc@example.com",
        )
        general_holc.users.district = district
        general_holc.users.legalName = "General Expulsion HoLC"
        general_holc.users.address = "1 Test Street"
        general_holc.users.userType = "U4D3"
        general_holc.users.save()

        target = User.objects.create_user(
            username="general-expulsion-target",
            email="general-expulsion-target@example.com",
        )
        target.users.district = district
        target.users.legalName = "General Expulsion Target"
        target.users.address = "2 Test Street"
        target.users.userType = "U4D3"
        target.users.save()

        general = HolcModel.objects.create(
            district=district,
            code=1,
        )

        HolcMembers.objects.create(
            user=general_holc,
            holc=general,
            is_member=True,
        )

        target_membership = HolcMembers.objects.create(
            user=target,
            holc=general,
            is_member=True,
            is_delegate=False,
        )

        with self.assertRaises(ValidationError):
            cast_caucus_expulsion_vote(
                voter=general_holc,
                target_membership=target_membership,
            )

        self.assertEqual(
            CaucusExpulsionVote.objects.filter(
                target_user=target,
                caucus=general,
                target_membership_id=target_membership.pk,
            ).count(),
            0,
        )

        target_membership.refresh_from_db()
        self.assertTrue(target_membership.is_member)
        self.assertFalse(target_membership.is_delegate)

    def test_outsider_cannot_vote_on_caucus_expulsion(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )

        holc_user = User.objects.create_user(
            username="outsider-expulsion-holc",
            email="outsider-expulsion-holc@example.com",
        )
        holc_user.users.district = district
        holc_user.users.legalName = "Outsider Expulsion HoLC"
        holc_user.users.address = "1 Test Street"
        holc_user.users.userType = "U4D3"
        holc_user.users.save()

        target = User.objects.create_user(
            username="outsider-expulsion-target",
            email="outsider-expulsion-target@example.com",
        )
        target.users.district = district
        target.users.legalName = "Outsider Expulsion Target"
        target.users.address = "2 Test Street"
        target.users.userType = "U4D3"
        target.users.save()

        outsider = User.objects.create_user(
            username="expulsion-outsider",
            email="expulsion-outsider@example.com",
        )

        ordinary = HolcModel.objects.create(district=district)

        HolcMembers.objects.create(
            user=holc_user,
            holc=ordinary,
            is_member=True,
        )

        target_membership = HolcMembers.objects.create(
            user=target,
            holc=ordinary,
            is_member=True,
            is_delegate=False,
        )

        with self.assertRaises(ValidationError):
            cast_caucus_expulsion_vote(
                voter=outsider,
                target_membership=target_membership,
            )

        self.assertEqual(
            CaucusExpulsionVote.objects.filter(
                voter=outsider,
                target_user=target,
                caucus=ordinary,
                target_membership_id=target_membership.pk,
            ).count(),
            0,
        )

        target_membership.refresh_from_db()
        self.assertTrue(target_membership.is_member)

    def test_member_cannot_vote_twice_on_same_expulsion(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )

        voter = User.objects.create_user(
            username="duplicate-expulsion-voter",
            email="duplicate-expulsion-voter@example.com",
        )
        voter.users.district = district
        voter.users.legalName = "Duplicate Expulsion Voter"
        voter.users.address = "1 Test Street"
        voter.users.userType = "U4D3"
        voter.users.save()

        second_member = User.objects.create_user(
            username="duplicate-expulsion-second-member",
            email="duplicate-expulsion-second-member@example.com",
        )
        second_member.users.district = district
        second_member.users.legalName = "Second Expulsion Member"
        second_member.users.address = "2 Test Street"
        second_member.users.userType = "U4D3"
        second_member.users.save()

        target = User.objects.create_user(
            username="duplicate-expulsion-target",
            email="duplicate-expulsion-target@example.com",
        )
        target.users.district = district
        target.users.legalName = "Duplicate Expulsion Target"
        target.users.address = "3 Test Street"
        target.users.userType = "U4D3"
        target.users.save()

        ordinary = HolcModel.objects.create(district=district)

        HolcMembers.objects.create(
            user=voter,
            holc=ordinary,
            is_member=True,
        )

        second_membership = HolcMembers.objects.create(
            user=second_member,
            holc=ordinary,
            is_member=True,
        )
        second_membership.is_delegate = False
        second_membership.save(update_fields=["is_delegate"])

        target_membership = HolcMembers.objects.create(
            user=target,
            holc=ordinary,
            is_member=True,
            is_delegate=False,
        )

        cast_caucus_expulsion_vote(
            voter=voter,
            target_membership=target_membership,
        )

        with self.assertRaises(ValidationError):
            cast_caucus_expulsion_vote(
                voter=voter,
                target_membership=target_membership,
            )

        self.assertEqual(
            CaucusExpulsionVote.objects.filter(
                voter=voter,
                caucus=ordinary,
                target_membership_id=target_membership.pk,
            ).count(),
            1,
        )

        target_membership.refresh_from_db()
        self.assertTrue(target_membership.is_member)

    def test_departed_member_vote_does_not_count_toward_expulsion_majority(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )

        ordinary = HolcModel.objects.create(district=district)
        members = []

        for number in range(3):
            user = User.objects.create_user(
                username=f"expulsion-current-member-{number}",
                email=f"expulsion-current-member-{number}@example.com",
            )
            user.users.district = district
            user.users.legalName = f"Expulsion Current Member {number}"
            user.users.address = "1 Test Street"
            user.users.userType = "U4D3"
            user.users.save()

            membership = HolcMembers.objects.create(
                user=user,
                holc=ordinary,
                is_member=True,
            )

            if number > 0:
                membership.is_delegate = False
                membership.save(update_fields=["is_delegate"])

            members.append(membership)

        target = User.objects.create_user(
            username="expulsion-current-majority-target",
            email="expulsion-current-majority-target@example.com",
        )
        target.users.district = district
        target.users.legalName = "Expulsion Current Majority Target"
        target.users.address = "2 Test Street"
        target.users.userType = "U4D3"
        target.users.save()

        target_membership = HolcMembers.objects.create(
            user=target,
            holc=ordinary,
            is_member=True,
            is_delegate=False,
        )

        cast_caucus_expulsion_vote(
            voter=members[1].user,
            target_membership=target_membership,
        )

        # Preserve the historical vote, but remove this voter from the
        # current accepted membership used to calculate the live majority.
        members[1].is_member = False
        members[1].save(update_fields=["is_member"])

        result = cast_caucus_expulsion_vote(
            voter=members[2].user,
            target_membership=target_membership,
        )

        self.assertEqual(result.pk, target_membership.pk)

        target_membership.refresh_from_db()
        self.assertTrue(target_membership.is_member)

        self.assertEqual(
            CaucusExpulsionVote.objects.filter(
                caucus=ordinary,
                target_membership_id=target_membership.pk,
            ).count(),
            2,
        )
