from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from holc.models import CaucusAdmissionVote, HolcMembers, HolcModel
from holc.transitions import cast_caucus_admission_vote
from holc.views import HolcMembersViewSet
from moda.models import ModaMembers, ModaModel
from vote.models import Districts


class CaucusAdmissionDecisionTests(TestCase):
    def test_majority_accepts_pending_delegate(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )

        applicant = User.objects.create_user(
            username="majority-applicant",
            email="majority-applicant@example.com",
        )
        applicant.users.district = district
        applicant.users.legalName = "Majority Applicant"
        applicant.users.address = "1 Test Street"
        applicant.users.userType = "U2D2"
        applicant.users.save()

        second_link = ModaModel.objects.create(
            district=district,
            status=True,
        )
        ModaMembers.objects.create(
            user=applicant,
            moda=second_link,
            is_member=True,
        )

        general_holc = User.objects.create_user(
            username="majority-general-holc",
            email="majority-general-holc@example.com",
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
        HolcMembers.objects.create(
            user=applicant,
            holc=general,
            is_member=True,
            is_delegate=False,
        )

        destination = HolcModel.objects.create(district=district)
        voters = []

        for number in range(3):
            voter = User.objects.create_user(
                username=f"admission-voter-{number}",
                email=f"admission-voter-{number}@example.com",
            )
            voter.users.district = district
            voter.users.legalName = f"Admission Voter {number}"
            voter.users.address = "3 Test Street"
            voter.users.userType = "U4D3"
            voter.users.save()

            membership = HolcMembers.objects.create(
                user=voter,
                holc=destination,
                is_member=True,
            )

            if number > 0:
                membership.is_delegate = False
                membership.save(update_fields=["is_delegate"])

            voters.append(voter)

        pending_membership = HolcMembers.objects.create(
            user=applicant,
            holc=destination,
        )

        # Three accepted members require two votes for a majority.
        first_result = cast_caucus_admission_vote(
            voter=voters[0],
            pending_membership=pending_membership,
        )

        self.assertFalse(first_result.is_member)
        self.assertEqual(
            CaucusAdmissionVote.objects.filter(
                application=pending_membership,
            ).count(),
            1,
        )

        second_result = cast_caucus_admission_vote(
            voter=voters[1],
            pending_membership=pending_membership,
        )

        second_result.refresh_from_db()

        self.assertTrue(second_result.is_member)
        self.assertFalse(second_result.is_delegate)

        self.assertFalse(
            HolcMembers.objects.filter(
                user=applicant,
                holc=general,
                is_member=True,
            ).exists()
        )

        self.assertEqual(
            HolcMembers.objects.filter(
                user=applicant,
                is_member=True,
            ).count(),
            1,
        )

        applicant.users.refresh_from_db()
        self.assertEqual(applicant.users.userType, "U4D3")

        self.assertEqual(
            CaucusAdmissionVote.objects.filter(
                application=pending_membership,
            ).count(),
            2,
        )

    def test_outsider_cannot_vote_on_caucus_application(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )

        applicant = User.objects.create_user(
            username="outsider-vote-applicant",
            email="outsider-vote-applicant@example.com",
        )
        applicant.users.district = district
        applicant.users.legalName = "Outsider Vote Applicant"
        applicant.users.address = "1 Test Street"
        applicant.users.userType = "U4D3"
        applicant.users.save()

        destination_holc = User.objects.create_user(
            username="outsider-vote-holc",
            email="outsider-vote-holc@example.com",
        )
        destination_holc.users.district = district
        destination_holc.users.legalName = "Destination HoLC"
        destination_holc.users.address = "2 Test Street"
        destination_holc.users.userType = "U4D3"
        destination_holc.users.save()

        destination = HolcModel.objects.create(district=district)
        HolcMembers.objects.create(
            user=destination_holc,
            holc=destination,
            is_member=True,
        )

        pending_membership = HolcMembers.objects.create(
            user=applicant,
            holc=destination,
        )

        outsider = User.objects.create_user(
            username="caucus-outsider",
            email="caucus-outsider@example.com",
        )

        with self.assertRaises(ValidationError):
            cast_caucus_admission_vote(
                voter=outsider,
                pending_membership=pending_membership,
            )

        self.assertEqual(
            CaucusAdmissionVote.objects.filter(
                application=pending_membership,
            ).count(),
            0,
        )

        pending_membership.refresh_from_db()
        self.assertFalse(pending_membership.is_member)

    def test_member_cannot_vote_twice_on_same_application(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )

        applicant = User.objects.create_user(
            username="duplicate-vote-applicant",
            email="duplicate-vote-applicant@example.com",
        )
        applicant.users.district = district
        applicant.users.legalName = "Duplicate Vote Applicant"
        applicant.users.address = "1 Test Street"
        applicant.users.userType = "U4D3"
        applicant.users.save()

        voter = User.objects.create_user(
            username="duplicate-vote-member",
            email="duplicate-vote-member@example.com",
        )
        voter.users.district = district
        voter.users.legalName = "Duplicate Vote Member"
        voter.users.address = "2 Test Street"
        voter.users.userType = "U4D3"
        voter.users.save()

        second_member = User.objects.create_user(
            username="second-admission-member",
            email="second-admission-member@example.com",
        )
        second_member.users.district = district
        second_member.users.legalName = "Second Admission Member"
        second_member.users.address = "3 Test Street"
        second_member.users.userType = "U4D3"
        second_member.users.save()

        destination = HolcModel.objects.create(district=district)

        HolcMembers.objects.create(
            user=voter,
            holc=destination,
            is_member=True,
        )

        second_membership = HolcMembers.objects.create(
            user=second_member,
            holc=destination,
            is_member=True,
        )
        second_membership.is_delegate = False
        second_membership.save(update_fields=["is_delegate"])

        pending_membership = HolcMembers.objects.create(
            user=applicant,
            holc=destination,
        )

        first_result = cast_caucus_admission_vote(
            voter=voter,
            pending_membership=pending_membership,
        )

        self.assertFalse(first_result.is_member)

        with self.assertRaises(ValidationError):
            cast_caucus_admission_vote(
                voter=voter,
                pending_membership=pending_membership,
            )

        self.assertEqual(
            CaucusAdmissionVote.objects.filter(
                voter=voter,
                application=pending_membership,
            ).count(),
            1,
        )

        pending_membership.refresh_from_db()
        self.assertFalse(pending_membership.is_member)

    def test_accepted_member_can_cast_admission_vote_through_api(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )

        voter = User.objects.create_user(
            username="api-admission-voter",
            email="api-admission-voter@example.com",
        )
        voter.users.district = district
        voter.users.legalName = "API Admission Voter"
        voter.users.address = "1 Test Street"
        voter.users.userType = "U4D3"
        voter.users.save()

        second_member = User.objects.create_user(
            username="api-second-member",
            email="api-second-member@example.com",
        )
        second_member.users.district = district
        second_member.users.legalName = "API Second Member"
        second_member.users.address = "2 Test Street"
        second_member.users.userType = "U4D3"
        second_member.users.save()

        applicant = User.objects.create_user(
            username="api-admission-applicant",
            email="api-admission-applicant@example.com",
        )
        applicant.users.district = district
        applicant.users.legalName = "API Admission Applicant"
        applicant.users.address = "3 Test Street"
        applicant.users.userType = "U4D3"
        applicant.users.save()

        destination = HolcModel.objects.create(district=district)

        HolcMembers.objects.create(
            user=voter,
            holc=destination,
            is_member=True,
        )

        second_membership = HolcMembers.objects.create(
            user=second_member,
            holc=destination,
            is_member=True,
        )
        second_membership.is_delegate = False
        second_membership.save(update_fields=["is_delegate"])

        pending_membership = HolcMembers.objects.create(
            user=applicant,
            holc=destination,
        )

        request = APIRequestFactory().post(
            f"/holc-members/{pending_membership.pk}/vote_admission/",
            {},
            format="json",
        )
        force_authenticate(request, user=voter)

        response = HolcMembersViewSet.as_view(
            {"post": "vote_admission"}
        )(
            request,
            pk=pending_membership.pk,
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            CaucusAdmissionVote.objects.filter(
                voter=voter,
                application=pending_membership,
            ).count(),
            1,
        )

        pending_membership.refresh_from_db()
        self.assertFalse(pending_membership.is_member)

    def test_api_majority_vote_completes_caucus_transfer(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )

        applicant = User.objects.create_user(
            username="api-majority-applicant",
            email="api-majority-applicant@example.com",
        )
        applicant.users.district = district
        applicant.users.legalName = "API Majority Applicant"
        applicant.users.address = "1 Test Street"
        applicant.users.userType = "U2D2"
        applicant.users.save()

        second_link = ModaModel.objects.create(
            district=district,
            status=True,
        )
        ModaMembers.objects.create(
            user=applicant,
            moda=second_link,
            is_member=True,
        )

        general_holc = User.objects.create_user(
            username="api-majority-general-holc",
            email="api-majority-general-holc@example.com",
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
        HolcMembers.objects.create(
            user=applicant,
            holc=general,
            is_member=True,
            is_delegate=False,
        )

        destination = HolcModel.objects.create(district=district)
        voters = []

        for number in range(3):
            voter = User.objects.create_user(
                username=f"api-majority-voter-{number}",
                email=f"api-majority-voter-{number}@example.com",
            )
            voter.users.district = district
            voter.users.legalName = f"API Majority Voter {number}"
            voter.users.address = "3 Test Street"
            voter.users.userType = "U4D3"
            voter.users.save()

            membership = HolcMembers.objects.create(
                user=voter,
                holc=destination,
                is_member=True,
            )

            if number > 0:
                membership.is_delegate = False
                membership.save(update_fields=["is_delegate"])

            voters.append(voter)

        pending_membership = HolcMembers.objects.create(
            user=applicant,
            holc=destination,
        )

        first_request = APIRequestFactory().post(
            f"/holc-members/{pending_membership.pk}/vote_admission/",
            {},
            format="json",
        )
        force_authenticate(first_request, user=voters[0])

        first_response = HolcMembersViewSet.as_view(
            {"post": "vote_admission"}
        )(
            first_request,
            pk=pending_membership.pk,
        )

        self.assertEqual(first_response.status_code, 200)

        pending_membership.refresh_from_db()
        self.assertFalse(pending_membership.is_member)

        second_request = APIRequestFactory().post(
            f"/holc-members/{pending_membership.pk}/vote_admission/",
            {},
            format="json",
        )
        force_authenticate(second_request, user=voters[1])

        second_response = HolcMembersViewSet.as_view(
            {"post": "vote_admission"}
        )(
            second_request,
            pk=pending_membership.pk,
        )

        self.assertEqual(second_response.status_code, 200)

        pending_membership.refresh_from_db()
        self.assertTrue(pending_membership.is_member)
        self.assertFalse(pending_membership.is_delegate)

        self.assertFalse(
            HolcMembers.objects.filter(
                user=applicant,
                holc=general,
                is_member=True,
            ).exists()
        )

        self.assertEqual(
            HolcMembers.objects.filter(
                user=applicant,
                is_member=True,
            ).count(),
            1,
        )

        self.assertEqual(
            CaucusAdmissionVote.objects.filter(
                application=pending_membership,
            ).count(),
            2,
        )

        self.assertTrue(
            ModaMembers.objects.filter(
                user=applicant,
                moda=second_link,
                is_member=True,
                is_delegate=True,
                moda__status=True,
            ).exists()
        )

        applicant.users.refresh_from_db()
        self.assertEqual(applicant.users.userType, "U4D3")

    def test_departed_member_vote_does_not_count_toward_current_majority(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )

        destination = HolcModel.objects.create(district=district)
        members = []

        for number in range(3):
            user = User.objects.create_user(
                username=f"current-majority-member-{number}",
                email=f"current-majority-member-{number}@example.com",
            )
            user.users.district = district
            user.users.legalName = f"Current Majority Member {number}"
            user.users.address = "1 Test Street"
            user.users.userType = "U4D3"
            user.users.save()

            membership = HolcMembers.objects.create(
                user=user,
                holc=destination,
                is_member=True,
            )

            if number > 0:
                membership.is_delegate = False
                membership.save(update_fields=["is_delegate"])

            members.append(membership)

        applicant = User.objects.create_user(
            username="current-majority-applicant",
            email="current-majority-applicant@example.com",
        )
        applicant.users.district = district
        applicant.users.legalName = "Current Majority Applicant"
        applicant.users.address = "2 Test Street"
        applicant.users.userType = "U4D3"
        applicant.users.save()

        pending_membership = HolcMembers.objects.create(
            user=applicant,
            holc=destination,
        )

        cast_caucus_admission_vote(
            voter=members[1].user,
            pending_membership=pending_membership,
        )

        # Simulate this voter ceasing to be an accepted member before
        # another member casts the deciding vote.
        members[1].is_member = False
        members[1].save(update_fields=["is_member"])

        result = cast_caucus_admission_vote(
            voter=members[2].user,
            pending_membership=pending_membership,
        )

        self.assertFalse(result.is_member)

        self.assertEqual(
            CaucusAdmissionVote.objects.filter(
                application=pending_membership,
            ).count(),
            2,
        )
