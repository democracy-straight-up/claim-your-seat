from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from holc.models import HolcMembers, HolcModel, PutForwardHolcMember
from holc.views import HolcMembersViewSet
from moda.models import ModaMembers, ModaModel
from vote.models import Districts


class HolcReplacementDecisionTests(TestCase):
    def test_departed_member_vote_does_not_count_toward_holc_majority(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )

        caucus = HolcModel.objects.create(district=district)
        memberships = []

        for number in range(4):
            user = User.objects.create_user(
                username=f"holc-replacement-member-{number}",
                email=f"holc-replacement-member-{number}@example.com",
            )
            user.users.district = district
            user.users.legalName = f"HoLC Replacement Member {number}"
            user.users.address = "1 Test Street"
            user.users.userType = "U4D3"
            user.users.save()

            membership = HolcMembers.objects.create(
                user=user,
                holc=caucus,
                is_member=True,
            )

            if number > 0:
                membership.is_delegate = False
                membership.save(update_fields=["is_delegate"])

            memberships.append(membership)

        incumbent = memberships[0]
        candidate = memberships[1]
        departing_voter = memberships[2]
        current_voter = memberships[3]

        second_link = ModaModel.objects.create(
            district=district,
            status=True,
        )
        ModaMembers.objects.create(
            user=candidate.user,
            moda=second_link,
            is_member=True,
        )

        self.assertTrue(incumbent.is_delegate)
        self.assertFalse(candidate.is_delegate)

        PutForwardHolcMember.objects.create(
            voter=departing_voter.user,
            candidate=candidate,
            holc=caucus,
        )

        # Preserve the historical vote, but remove this voter from the
        # accepted membership used to calculate the live majority.
        departing_voter.is_member = False
        departing_voter.save(update_fields=["is_member"])

        # Three current accepted members require two current votes.
        PutForwardHolcMember.objects.create(
            voter=current_voter.user,
            candidate=candidate,
            holc=caucus,
        )

        incumbent.refresh_from_db()
        candidate.refresh_from_db()

        self.assertTrue(incumbent.is_delegate)
        self.assertFalse(candidate.is_delegate)

        self.assertEqual(
            PutForwardHolcMember.objects.filter(
                candidate=candidate,
            ).count(),
            2,
        )

    def test_member_cannot_cast_multiple_holc_votes_for_same_candidate(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )

        caucus = HolcModel.objects.create(district=district)
        memberships = []

        for number in range(3):
            user = User.objects.create_user(
                username=f"holc-duplicate-vote-member-{number}",
                email=f"holc-duplicate-vote-member-{number}@example.com",
            )
            user.users.district = district
            user.users.legalName = f"HoLC Duplicate Vote Member {number}"
            user.users.address = "1 Test Street"
            user.users.userType = "U4D3"
            user.users.save()

            membership = HolcMembers.objects.create(
                user=user,
                holc=caucus,
                is_member=True,
            )

            if number > 0:
                membership.is_delegate = False
                membership.save(update_fields=["is_delegate"])

            memberships.append(membership)

        incumbent = memberships[0]
        candidate = memberships[1]
        voter = memberships[2]

        self.assertTrue(incumbent.is_delegate)
        self.assertFalse(candidate.is_delegate)

        PutForwardHolcMember.objects.create(
            voter=voter.user,
            candidate=candidate,
            holc=caucus,
        )

        PutForwardHolcMember.objects.create(
            voter=voter.user,
            candidate=candidate,
            holc=caucus,
        )

        incumbent.refresh_from_db()
        candidate.refresh_from_db()

        self.assertTrue(incumbent.is_delegate)
        self.assertFalse(candidate.is_delegate)

        self.assertEqual(
            PutForwardHolcMember.objects.filter(
                voter=voter.user,
                candidate=candidate,
                holc=caucus,
            ).count(),
            1,
        )

    def test_pending_applicant_cannot_become_holc(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )

        caucus = HolcModel.objects.create(district=district)

        incumbent_user = User.objects.create_user(
            username="pending-holc-incumbent",
            email="pending-holc-incumbent@example.com",
        )
        incumbent_user.users.district = district
        incumbent_user.users.legalName = "Pending HoLC Incumbent"
        incumbent_user.users.address = "1 Test Street"
        incumbent_user.users.userType = "U4D3"
        incumbent_user.users.save()

        incumbent = HolcMembers.objects.create(
            user=incumbent_user,
            holc=caucus,
            is_member=True,
        )

        voter_user = User.objects.create_user(
            username="pending-holc-voter",
            email="pending-holc-voter@example.com",
        )
        voter_user.users.district = district
        voter_user.users.legalName = "Pending HoLC Voter"
        voter_user.users.address = "2 Test Street"
        voter_user.users.userType = "U4D3"
        voter_user.users.save()

        voter_membership = HolcMembers.objects.create(
            user=voter_user,
            holc=caucus,
            is_member=True,
        )
        voter_membership.is_delegate = False
        voter_membership.save(update_fields=["is_delegate"])

        applicant_user = User.objects.create_user(
            username="pending-holc-applicant",
            email="pending-holc-applicant@example.com",
        )
        applicant_user.users.district = district
        applicant_user.users.legalName = "Pending HoLC Applicant"
        applicant_user.users.address = "3 Test Street"
        applicant_user.users.userType = "U4D3"
        applicant_user.users.save()

        pending_membership = HolcMembers.objects.create(
            user=applicant_user,
            holc=caucus,
            is_member=False,
            is_delegate=False,
        )

        PutForwardHolcMember.objects.create(
            voter=incumbent.user,
            candidate=pending_membership,
            holc=caucus,
        )

        PutForwardHolcMember.objects.create(
            voter=voter_user,
            candidate=pending_membership,
            holc=caucus,
        )

        incumbent.refresh_from_db()
        pending_membership.refresh_from_db()
        applicant_user.users.refresh_from_db()

        self.assertTrue(incumbent.is_delegate)
        self.assertFalse(pending_membership.is_delegate)
        self.assertFalse(pending_membership.is_member)
        self.assertEqual(applicant_user.users.userType, "U4D3")

    def test_outsider_cannot_cast_holc_replacement_vote(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )

        caucus = HolcModel.objects.create(district=district)

        incumbent_user = User.objects.create_user(
            username="holc-outsider-incumbent",
            email="holc-outsider-incumbent@example.com",
        )
        incumbent_user.users.district = district
        incumbent_user.users.legalName = "HoLC Outsider Incumbent"
        incumbent_user.users.address = "1 Test Street"
        incumbent_user.users.userType = "U4D3"
        incumbent_user.users.save()

        incumbent = HolcMembers.objects.create(
            user=incumbent_user,
            holc=caucus,
            is_member=True,
        )

        candidate_user = User.objects.create_user(
            username="holc-outsider-candidate",
            email="holc-outsider-candidate@example.com",
        )
        candidate_user.users.district = district
        candidate_user.users.legalName = "HoLC Outsider Candidate"
        candidate_user.users.address = "2 Test Street"
        candidate_user.users.userType = "U4D3"
        candidate_user.users.save()

        candidate = HolcMembers.objects.create(
            user=candidate_user,
            holc=caucus,
            is_member=True,
        )
        candidate.is_delegate = False
        candidate.save(update_fields=["is_delegate"])

        outsider = User.objects.create_user(
            username="holc-replacement-outsider",
            email="holc-replacement-outsider@example.com",
        )

        PutForwardHolcMember.objects.create(
            voter=outsider,
            candidate=candidate,
            holc=caucus,
        )

        self.assertEqual(
            PutForwardHolcMember.objects.filter(
                voter=outsider,
                candidate=candidate,
                holc=caucus,
            ).count(),
            0,
        )

        incumbent.refresh_from_db()
        candidate.refresh_from_db()

        self.assertTrue(incumbent.is_delegate)
        self.assertFalse(candidate.is_delegate)

    def test_holc_vote_must_match_candidate_caucus(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )

        first_caucus = HolcModel.objects.create(district=district)
        second_caucus = HolcModel.objects.create(district=district)

        voter_user = User.objects.create_user(
            username="holc-mismatch-voter",
            email="holc-mismatch-voter@example.com",
        )
        voter_user.users.district = district
        voter_user.users.legalName = "HoLC Mismatch Voter"
        voter_user.users.address = "1 Test Street"
        voter_user.users.userType = "U4D3"
        voter_user.users.save()

        candidate_user = User.objects.create_user(
            username="holc-mismatch-candidate",
            email="holc-mismatch-candidate@example.com",
        )
        candidate_user.users.district = district
        candidate_user.users.legalName = "HoLC Mismatch Candidate"
        candidate_user.users.address = "2 Test Street"
        candidate_user.users.userType = "U4D3"
        candidate_user.users.save()

        HolcMembers.objects.create(
            user=voter_user,
            holc=first_caucus,
            is_member=True,
        )

        candidate = HolcMembers.objects.create(
            user=candidate_user,
            holc=first_caucus,
            is_member=True,
        )
        candidate.is_delegate = False
        candidate.save(update_fields=["is_delegate"])

        PutForwardHolcMember.objects.create(
            voter=voter_user,
            candidate=candidate,
            holc=second_caucus,
        )

        self.assertEqual(
            PutForwardHolcMember.objects.filter(
                voter=voter_user,
                candidate=candidate,
                holc=second_caucus,
            ).count(),
            0,
        )

    def test_member_without_active_second_link_mandate_cannot_become_holc(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )

        caucus = HolcModel.objects.create(district=district)
        memberships = []

        for number in range(3):
            user = User.objects.create_user(
                username=f"holc-ineligible-candidate-member-{number}",
                email=f"holc-ineligible-candidate-member-{number}@example.com",
            )
            user.users.district = district
            user.users.legalName = (
                f"HoLC Ineligible Candidate Member {number}"
            )
            user.users.address = "1 Test Street"
            user.users.userType = "U4D3"
            user.users.save()

            membership = HolcMembers.objects.create(
                user=user,
                holc=caucus,
                is_member=True,
            )

            if number > 0:
                membership.is_delegate = False
                membership.save(update_fields=["is_delegate"])

            memberships.append(membership)

        incumbent = memberships[0]
        candidate = memberships[1]
        voter = memberships[2]

        self.assertTrue(incumbent.is_delegate)
        self.assertFalse(candidate.is_delegate)

        # Candidate has an accepted Caucus membership but deliberately
        # has no active Second Link delegate mandate.
        PutForwardHolcMember.objects.create(
            voter=incumbent.user,
            candidate=candidate,
            holc=caucus,
        )

        PutForwardHolcMember.objects.create(
            voter=voter.user,
            candidate=candidate,
            holc=caucus,
        )

        incumbent.refresh_from_db()
        candidate.refresh_from_db()
        candidate.user.users.refresh_from_db()

        self.assertTrue(incumbent.is_delegate)
        self.assertFalse(candidate.is_delegate)
        self.assertEqual(candidate.user.users.userType, "U4D3")

    def test_accepted_member_can_cast_holc_replacement_vote_through_api(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )

        caucus = HolcModel.objects.create(district=district)

        incumbent_user = User.objects.create_user(
            username="api-holc-incumbent",
            email="api-holc-incumbent@example.com",
        )
        incumbent_user.users.district = district
        incumbent_user.users.legalName = "API HoLC Incumbent"
        incumbent_user.users.address = "1 Test Street"
        incumbent_user.users.userType = "U4D3"
        incumbent_user.users.save()

        HolcMembers.objects.create(
            user=incumbent_user,
            holc=caucus,
            is_member=True,
        )

        candidate_user = User.objects.create_user(
            username="api-holc-candidate",
            email="api-holc-candidate@example.com",
        )
        candidate_user.users.district = district
        candidate_user.users.legalName = "API HoLC Candidate"
        candidate_user.users.address = "2 Test Street"
        candidate_user.users.userType = "U4D3"
        candidate_user.users.save()

        second_link = ModaModel.objects.create(
            district=district,
            status=True,
        )
        ModaMembers.objects.create(
            user=candidate_user,
            moda=second_link,
            is_member=True,
        )

        candidate = HolcMembers.objects.create(
            user=candidate_user,
            holc=caucus,
            is_member=True,
        )
        candidate.is_delegate = False
        candidate.save(update_fields=["is_delegate"])

        voter_user = User.objects.create_user(
            username="api-holc-voter",
            email="api-holc-voter@example.com",
        )
        voter_user.users.district = district
        voter_user.users.legalName = "API HoLC Voter"
        voter_user.users.address = "3 Test Street"
        voter_user.users.userType = "U4D3"
        voter_user.users.save()

        voter_membership = HolcMembers.objects.create(
            user=voter_user,
            holc=caucus,
            is_member=True,
        )
        voter_membership.is_delegate = False
        voter_membership.save(update_fields=["is_delegate"])

        request = APIRequestFactory().post(
            f"/holc-members/{candidate.pk}/vote_holc_replacement/",
            {},
            format="json",
        )
        force_authenticate(request, user=voter_user)

        response = HolcMembersViewSet.as_view(
            {"post": "vote_holc_replacement"}
        )(
            request,
            pk=candidate.pk,
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            PutForwardHolcMember.objects.filter(
                voter=voter_user,
                candidate=candidate,
                holc=caucus,
            ).count(),
            1,
        )

    def test_api_rejects_candidate_without_active_second_link_mandate(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )

        caucus = HolcModel.objects.create(district=district)

        voter_user = User.objects.create_user(
            username="api-ineligible-holc-voter",
            email="api-ineligible-holc-voter@example.com",
        )
        voter_user.users.district = district
        voter_user.users.legalName = "API Ineligible HoLC Voter"
        voter_user.users.address = "1 Test Street"
        voter_user.users.userType = "U4D3"
        voter_user.users.save()

        HolcMembers.objects.create(
            user=voter_user,
            holc=caucus,
            is_member=True,
        )

        candidate_user = User.objects.create_user(
            username="api-ineligible-holc-candidate",
            email="api-ineligible-holc-candidate@example.com",
        )
        candidate_user.users.district = district
        candidate_user.users.legalName = "API Ineligible HoLC Candidate"
        candidate_user.users.address = "2 Test Street"
        candidate_user.users.userType = "U4D3"
        candidate_user.users.save()

        candidate = HolcMembers.objects.create(
            user=candidate_user,
            holc=caucus,
            is_member=True,
        )
        candidate.is_delegate = False
        candidate.save(update_fields=["is_delegate"])

        request = APIRequestFactory().post(
            f"/holc-members/{candidate.pk}/vote_holc_replacement/",
            {},
            format="json",
        )
        force_authenticate(request, user=voter_user)

        response = HolcMembersViewSet.as_view(
            {"post": "vote_holc_replacement"}
        )(
            request,
            pk=candidate.pk,
        )

        self.assertEqual(response.status_code, 400)

        self.assertEqual(
            PutForwardHolcMember.objects.filter(
                voter=voter_user,
                candidate=candidate,
                holc=caucus,
            ).count(),
            0,
        )

    def test_api_majority_replaces_holc(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )

        caucus = HolcModel.objects.create(district=district)

        incumbent_user = User.objects.create_user(
            username="api-majority-holc-incumbent",
            email="api-majority-holc-incumbent@example.com",
        )
        incumbent_user.users.district = district
        incumbent_user.users.legalName = "API Majority HoLC Incumbent"
        incumbent_user.users.address = "1 Test Street"
        incumbent_user.users.userType = "U4D3"
        incumbent_user.users.save()

        incumbent = HolcMembers.objects.create(
            user=incumbent_user,
            holc=caucus,
            is_member=True,
        )

        candidate_user = User.objects.create_user(
            username="api-majority-holc-candidate",
            email="api-majority-holc-candidate@example.com",
        )
        candidate_user.users.district = district
        candidate_user.users.legalName = "API Majority HoLC Candidate"
        candidate_user.users.address = "2 Test Street"
        candidate_user.users.userType = "U4D3"
        candidate_user.users.save()

        second_link = ModaModel.objects.create(
            district=district,
            status=True,
        )
        ModaMembers.objects.create(
            user=candidate_user,
            moda=second_link,
            is_member=True,
        )

        candidate = HolcMembers.objects.create(
            user=candidate_user,
            holc=caucus,
            is_member=True,
        )
        candidate.is_delegate = False
        candidate.save(update_fields=["is_delegate"])

        voter_user = User.objects.create_user(
            username="api-majority-holc-voter",
            email="api-majority-holc-voter@example.com",
        )
        voter_user.users.district = district
        voter_user.users.legalName = "API Majority HoLC Voter"
        voter_user.users.address = "3 Test Street"
        voter_user.users.userType = "U4D3"
        voter_user.users.save()

        voter_membership = HolcMembers.objects.create(
            user=voter_user,
            holc=caucus,
            is_member=True,
        )
        voter_membership.is_delegate = False
        voter_membership.save(update_fields=["is_delegate"])

        # Three accepted members require two votes for a majority.
        first_request = APIRequestFactory().post(
            f"/holc-members/{candidate.pk}/vote_holc_replacement/",
            {},
            format="json",
        )
        force_authenticate(first_request, user=incumbent_user)

        first_response = HolcMembersViewSet.as_view(
            {"post": "vote_holc_replacement"}
        )(
            first_request,
            pk=candidate.pk,
        )

        self.assertEqual(first_response.status_code, 200)

        incumbent.refresh_from_db()
        candidate.refresh_from_db()

        self.assertTrue(incumbent.is_delegate)
        self.assertFalse(candidate.is_delegate)

        second_request = APIRequestFactory().post(
            f"/holc-members/{candidate.pk}/vote_holc_replacement/",
            {},
            format="json",
        )
        force_authenticate(second_request, user=voter_user)

        second_response = HolcMembersViewSet.as_view(
            {"post": "vote_holc_replacement"}
        )(
            second_request,
            pk=candidate.pk,
        )

        self.assertEqual(second_response.status_code, 200)

        incumbent.refresh_from_db()
        candidate.refresh_from_db()
        incumbent_user.users.refresh_from_db()
        candidate_user.users.refresh_from_db()

        self.assertTrue(incumbent.is_member)
        self.assertFalse(incumbent.is_delegate)
        self.assertEqual(incumbent_user.users.userType, "U4D3")

        self.assertTrue(candidate.is_member)
        self.assertTrue(candidate.is_delegate)
        self.assertEqual(candidate_user.users.userType, "U4D4")

        self.assertEqual(
            HolcMembers.objects.filter(
                holc=caucus,
                is_member=True,
                is_delegate=True,
            ).count(),
            1,
        )

    def test_incumbent_holc_cannot_be_replacement_candidate(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )

        caucus = HolcModel.objects.create(district=district)

        incumbent_user = User.objects.create_user(
            username="incumbent-replacement-candidate",
            email="incumbent-replacement-candidate@example.com",
        )
        incumbent_user.users.district = district
        incumbent_user.users.legalName = "Incumbent Replacement Candidate"
        incumbent_user.users.address = "1 Test Street"
        incumbent_user.users.userType = "U4D3"
        incumbent_user.users.save()

        incumbent = HolcMembers.objects.create(
            user=incumbent_user,
            holc=caucus,
            is_member=True,
        )

        voter_user = User.objects.create_user(
            username="incumbent-replacement-voter",
            email="incumbent-replacement-voter@example.com",
        )
        voter_user.users.district = district
        voter_user.users.legalName = "Incumbent Replacement Voter"
        voter_user.users.address = "2 Test Street"
        voter_user.users.userType = "U4D3"
        voter_user.users.save()

        voter_membership = HolcMembers.objects.create(
            user=voter_user,
            holc=caucus,
            is_member=True,
        )
        voter_membership.is_delegate = False
        voter_membership.save(update_fields=["is_delegate"])

        PutForwardHolcMember.objects.create(
            voter=voter_user,
            candidate=incumbent,
            holc=caucus,
        )

        self.assertEqual(
            PutForwardHolcMember.objects.filter(
                voter=voter_user,
                candidate=incumbent,
                holc=caucus,
            ).count(),
            0,
        )

        incumbent.refresh_from_db()
        self.assertTrue(incumbent.is_delegate)

    def test_api_rejects_incumbent_holc_as_replacement_candidate(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )

        caucus = HolcModel.objects.create(district=district)

        incumbent_user = User.objects.create_user(
            username="api-incumbent-replacement-candidate",
            email="api-incumbent-replacement-candidate@example.com",
        )
        incumbent_user.users.district = district
        incumbent_user.users.legalName = "API Incumbent Replacement Candidate"
        incumbent_user.users.address = "1 Test Street"
        incumbent_user.users.userType = "U4D3"
        incumbent_user.users.save()

        second_link = ModaModel.objects.create(
            district=district,
            status=True,
        )
        ModaMembers.objects.create(
            user=incumbent_user,
            moda=second_link,
            is_member=True,
        )

        incumbent = HolcMembers.objects.create(
            user=incumbent_user,
            holc=caucus,
            is_member=True,
        )

        voter_user = User.objects.create_user(
            username="api-incumbent-replacement-voter",
            email="api-incumbent-replacement-voter@example.com",
        )
        voter_user.users.district = district
        voter_user.users.legalName = "API Incumbent Replacement Voter"
        voter_user.users.address = "2 Test Street"
        voter_user.users.userType = "U4D3"
        voter_user.users.save()

        voter_membership = HolcMembers.objects.create(
            user=voter_user,
            holc=caucus,
            is_member=True,
        )
        voter_membership.is_delegate = False
        voter_membership.save(update_fields=["is_delegate"])

        request = APIRequestFactory().post(
            f"/holc-members/{incumbent.pk}/vote_holc_replacement/",
            {},
            format="json",
        )
        force_authenticate(request, user=voter_user)

        response = HolcMembersViewSet.as_view(
            {"post": "vote_holc_replacement"}
        )(
            request,
            pk=incumbent.pk,
        )

        self.assertEqual(response.status_code, 400)

        self.assertEqual(
            PutForwardHolcMember.objects.filter(
                voter=voter_user,
                candidate=incumbent,
                holc=caucus,
            ).count(),
            0,
        )