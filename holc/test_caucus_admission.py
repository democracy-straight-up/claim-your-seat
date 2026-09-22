from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate
from moda.models import ModaMembers, ModaModel
from holc.models import HolcMembers, HolcModel
from holc.views import HolcViewSet, HolcMembersViewSet
from holc.transitions import (
    accept_eligible_delegate_into_caucus,
    expel_eligible_delegate_to_general,
)
from vote.models import Districts


class CaucusCreationTests(TestCase):
    def test_ordinary_member_cannot_create_caucus(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )
        user = User.objects.create_user(
            username="ordinary-member",
            email="ordinary@example.com",
        )
        user.users.district = district
        user.users.legalName = "Ordinary Member"
        user.users.address = "1 Test Street"
        user.users.userType = "U1D0"
        user.users.save()

        request = APIRequestFactory().post(
            "/holc/",
            {"user": user.username, "district": district.code},
            format="json",
        )
        force_authenticate(request, user=user)
        response = HolcViewSet.as_view({"post": "create"})(request)

        self.assertEqual(response.status_code, 403)
        self.assertFalse(HolcModel.objects.exists())
        self.assertFalse(HolcMembers.objects.filter(user=user).exists())

        user.users.refresh_from_db()
        self.assertEqual(user.users.userType, "U1D0")

    def test_caucus_delegate_cannot_create_for_another_user(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )

        delegate = User.objects.create_user(
            username="caucus-delegate",
            email="delegate@example.com",
        )
        other_user = User.objects.create_user(
            username="other-member",
            email="other@example.com",
        )

        for user, role in (
            (delegate, "U4D3"),
            (other_user, "U1D0"),
        ):
            user.users.district = district
            user.users.legalName = user.username
            user.users.address = "1 Test Street"
            user.users.userType = role
            user.users.save()

        request = APIRequestFactory().post(
            "/holc/",
            {"user": other_user.username, "district": district.code},
            format="json",
        )
        force_authenticate(request, user=delegate)
        response = HolcViewSet.as_view({"post": "create"})(request)

        self.assertEqual(response.status_code, 403)
        self.assertFalse(HolcModel.objects.exists())
        self.assertFalse(HolcMembers.objects.exists())

        other_user.users.refresh_from_db()
        self.assertEqual(other_user.users.userType, "U1D0")

        delegate.users.refresh_from_db()
        self.assertEqual(delegate.users.userType, "U4D3")

    def test_eligible_delegate_creates_caucus_and_transfers_membership(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )
        delegates = []

        # Activate two Second Links through the existing model behavior.
        for link_number in range(2):
            second_link = ModaModel.objects.create(district=district)

            for member_number in range(6):
                username = f"link-{link_number}-member-{member_number}"
                user = User.objects.create_user(
                    username=username,
                    email=f"{username}@example.com",
                )
                user.users.district = district
                user.users.legalName = username
                user.users.address = "1 Test Street"
                user.users.userType = "U2D2"
                user.users.save()

                ModaMembers.objects.create(
                    user=user,
                    moda=second_link,
                    is_member=True,
                )

                if member_number == 0:
                    delegates.append(user)

            self.assertTrue(second_link.is_active)

        general = HolcModel.objects.get(district=district, code=1)
        general_holc, creator = delegates
        creator.users.refresh_from_db()

        # Confirm the creator is eligible and is not already a HoLC.
        self.assertEqual(creator.users.userType, "U4D3")
        self.assertTrue(
            HolcMembers.objects.filter(
                user=creator,
                holc=general,
                is_member=True,
                is_delegate=False,
            ).exists()
        )

        request = APIRequestFactory().post(
            "/holc/",
            {"user": creator.username, "district": district.code},
            format="json",
        )
        force_authenticate(request, user=creator)
        response = HolcViewSet.as_view({"post": "create"})(request)

        # Preserve the endpoint's existing successful-response status.
        self.assertEqual(response.status_code, 200)

        new_caucus = HolcModel.objects.get(district=district, code=2)
        self.assertEqual(HolcModel.objects.count(), 2)
        self.assertEqual(new_caucus.member_count, 1)
        self.assertTrue(new_caucus.is_active)

        self.assertTrue(
            HolcMembers.objects.filter(
                user=creator,
                holc=new_caucus,
                is_member=True,
                is_delegate=True,
            ).exists()
        )
        self.assertFalse(
            HolcMembers.objects.filter(
                user=creator,
                holc=general,
                is_member=True,
            ).exists()
        )
        self.assertEqual(
            HolcMembers.objects.filter(
                user=creator, is_member=True
            ).count(),
            1,
        )

        creator.users.refresh_from_db()
        self.assertEqual(creator.users.userType, "U4D4")

        # Creating a Caucus preserves the creator's Second Link mandate.
        self.assertTrue(
            ModaMembers.objects.filter(
                user=creator,
                is_member=True,
                is_delegate=True,
            ).exists()
        )

        # The General Caucus retains its existing HoLC.
        self.assertTrue(
            HolcMembers.objects.filter(
                user=general_holc,
                holc=general,
                is_member=True,
                is_delegate=True,
            ).exists()
        )

    def test_creation_failure_preserves_existing_caucus_membership(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )
        delegates = []

        # Create two active Second Links so General Caucus has an
        # existing HoLC and the second delegate remains U4D3.
        for link_number in range(2):
            second_link = ModaModel.objects.create(district=district)

            for member_number in range(6):
                username = (
                    f"exhaustion-link-{link_number}-member-{member_number}"
                )
                user = User.objects.create_user(
                    username=username,
                    email=f"{username}@example.com",
                )
                user.users.district = district
                user.users.legalName = username
                user.users.address = "1 Test Street"
                user.users.userType = "U2D2"
                user.users.save()

                ModaMembers.objects.create(
                    user=user,
                    moda=second_link,
                    is_member=True,
                )

                if member_number == 0:
                    delegates.append(user)

            self.assertTrue(second_link.is_active)

        general = HolcModel.objects.get(district=district, code=1)
        creator = delegates[1]

        creator.users.refresh_from_db()
        self.assertEqual(creator.users.userType, "U4D3")

        # Occupy every ordinary Caucus number, 02 through 99.
        for expected_code in range(2, 100):
            caucus = HolcModel.objects.create(district=district)
            self.assertEqual(caucus.code, expected_code)

        request = APIRequestFactory().post(
            "/holc/",
            {"user": creator.username, "district": district.code},
            format="json",
        )
        force_authenticate(request, user=creator)
        response = HolcViewSet.as_view({"post": "create"})(request)

        self.assertEqual(response.status_code, 400)

        # The failed creation must not strand the delegate without
        # a Caucus membership.
        self.assertTrue(
            HolcMembers.objects.filter(
                user=creator,
                holc=general,
                is_member=True,
            ).exists()
        )

        creator.users.refresh_from_db()
        self.assertEqual(creator.users.userType, "U4D3")

class CaucusAdmissionTests(TestCase):
    def test_accepting_pending_delegate_transfers_accepted_membership(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )

        applicant = User.objects.create_user(
            username="accepted-transfer-applicant",
            email="accepted-transfer-applicant@example.com",
        )
        applicant.users.district = district
        applicant.users.legalName = "Accepted Transfer Applicant"
        applicant.users.address = "1 Test Street"
        applicant.users.userType = "U2D2"
        applicant.users.save()

        # This test isolates the admission transition. Second Link
        # activation behavior is covered separately.
        second_link = ModaModel.objects.create(
            district=district,
            status=True,
        )
        ModaMembers.objects.create(
            user=applicant,
            moda=second_link,
            is_member=True,
        )

        applicant.users.refresh_from_db()
        self.assertEqual(applicant.users.userType, "U4D3")

        general_holc = User.objects.create_user(
            username="general-transfer-holc",
            email="general-transfer-holc@example.com",
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

        source_membership = HolcMembers.objects.create(
            user=applicant,
            holc=general,
            is_member=True,
            is_delegate=False,
        )

        destination_holc = User.objects.create_user(
            username="destination-transfer-holc",
            email="destination-transfer-holc@example.com",
        )
        destination_holc.users.district = district
        destination_holc.users.legalName = "Destination HoLC"
        destination_holc.users.address = "3 Test Street"
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

        self.assertTrue(source_membership.is_member)
        self.assertFalse(pending_membership.is_member)
        self.assertFalse(pending_membership.is_delegate)

        accepted_membership = accept_eligible_delegate_into_caucus(
            pending_membership
        )

        accepted_membership.refresh_from_db()

        self.assertTrue(accepted_membership.is_member)
        self.assertFalse(accepted_membership.is_delegate)
        self.assertEqual(accepted_membership.holc, destination)

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

        self.assertTrue(
            ModaMembers.objects.filter(
                user=applicant,
                is_member=True,
                is_delegate=True,
                moda=second_link,
                moda__status=True,
            ).exists()
        )

    def test_delegate_cannot_apply_another_user_to_existing_caucus(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )

        delegate = User.objects.create_user(
            username="applying-delegate",
            email="applying-delegate@example.com",
        )
        delegate.users.district = district
        delegate.users.legalName = "Applying Delegate"
        delegate.users.address = "1 Test Street"
        delegate.users.userType = "U4D3"
        delegate.users.save()

        other_user = User.objects.create_user(
            username="other-caucus-user",
            email="other-caucus-user@example.com",
        )
        other_user.users.district = district
        other_user.users.legalName = "Other Caucus User"
        other_user.users.address = "2 Test Street"
        other_user.users.userType = "U1D0"
        other_user.users.save()

        destination = HolcModel.objects.create(
            district=district,
            invitation_key=1234567890,
        )

        request = APIRequestFactory().post(
            "/holc-members/join_invite_key/",
            {
                "inviteKey": destination.invitation_key,
                "user": other_user.username,
            },
            format="json",
        )
        force_authenticate(request, user=delegate)

        response = HolcMembersViewSet.as_view(
            {"post": "join_invite_key"}
        )(request)

        self.assertEqual(response.status_code, 403)

        self.assertFalse(
            HolcMembers.objects.filter(
                user=other_user,
                holc=destination,
            ).exists()
        )

    def test_role_code_alone_cannot_apply_to_existing_caucus(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )

        applicant = User.objects.create_user(
            username="role-only-delegate",
            email="role-only-delegate@example.com",
        )
        applicant.users.district = district
        applicant.users.legalName = "Role Only Delegate"
        applicant.users.address = "1 Test Street"
        applicant.users.userType = "U4D3"
        applicant.users.save()

        caucus_owner = User.objects.create_user(
            username="existing-holc",
            email="existing-holc@example.com",
        )
        caucus_owner.users.district = district
        caucus_owner.users.legalName = "Existing HoLC"
        caucus_owner.users.address = "2 Test Street"
        caucus_owner.users.userType = "U4D3"
        caucus_owner.users.save()

        destination = HolcModel.objects.create(
            district=district,
            invitation_key=2345678901,
        )
        HolcMembers.objects.create(
            user=caucus_owner,
            holc=destination,
            is_member=True,
        )

        request = APIRequestFactory().post(
            "/holc-members/join_invite_key/",
            {
                "inviteKey": destination.invitation_key,
                "user": applicant.username,
            },
            format="json",
        )
        force_authenticate(request, user=applicant)

        response = HolcMembersViewSet.as_view(
            {"post": "join_invite_key"}
        )(request)

        self.assertEqual(response.status_code, 403)

        self.assertFalse(
            HolcMembers.objects.filter(
                user=applicant,
                holc=destination,
            ).exists()
        )

        applicant.users.refresh_from_db()
        self.assertEqual(applicant.users.userType, "U4D3")

    def test_eligible_delegate_application_is_pending_and_preserves_membership(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )
        delegates = []

        # Activate two Second Links. Their delegates join General Caucus.
        for link_number in range(2):
            second_link = ModaModel.objects.create(district=district)

            for member_number in range(6):
                username = (
                    f"pending-link-{link_number}-member-{member_number}"
                )
                user = User.objects.create_user(
                    username=username,
                    email=f"{username}@example.com",
                )
                user.users.district = district
                user.users.legalName = username
                user.users.address = "1 Test Street"
                user.users.userType = "U2D2"
                user.users.save()

                ModaMembers.objects.create(
                    user=user,
                    moda=second_link,
                    is_member=True,
                )

                if member_number == 0:
                    delegates.append(user)

            self.assertTrue(second_link.is_active)

        general = HolcModel.objects.get(
            district=district,
            code=1,
        )
        applicant = delegates[1]

        applicant.users.refresh_from_db()
        self.assertEqual(applicant.users.userType, "U4D3")

        # Create an existing ordinary Caucus with its own HoLC.
        caucus_owner = User.objects.create_user(
            username="pending-destination-holc",
            email="pending-destination-holc@example.com",
        )
        caucus_owner.users.district = district
        caucus_owner.users.legalName = "Destination HoLC"
        caucus_owner.users.address = "2 Test Street"
        caucus_owner.users.userType = "U4D3"
        caucus_owner.users.save()

        destination = HolcModel.objects.create(
            district=district,
            invitation_key=3456789012,
        )
        HolcMembers.objects.create(
            user=caucus_owner,
            holc=destination,
            is_member=True,
        )

        self.assertEqual(destination.code, 2)

        request = APIRequestFactory().post(
            "/holc-members/join_invite_key/",
            {
                "inviteKey": destination.invitation_key,
                "user": applicant.username,
            },
            format="json",
        )
        force_authenticate(request, user=applicant)

        response = HolcMembersViewSet.as_view(
            {"post": "join_invite_key"}
        )(request)

        self.assertEqual(response.status_code, 200)

        # The applicant remains an accepted General Caucus member.
        self.assertTrue(
            HolcMembers.objects.filter(
                user=applicant,
                holc=general,
                is_member=True,
            ).exists()
        )

        # The destination record exists, but remains pending.
        self.assertTrue(
            HolcMembers.objects.filter(
                user=applicant,
                holc=destination,
                is_member=False,
                is_delegate=False,
            ).exists()
        )

        # Pending application does not create a second accepted membership.
        self.assertEqual(
            HolcMembers.objects.filter(
                user=applicant,
                is_member=True,
            ).count(),
            1,
        )

        applicant.users.refresh_from_db()
        self.assertEqual(applicant.users.userType, "U4D3")

    def test_delegate_cannot_apply_to_general_caucus(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )

        applicant = User.objects.create_user(
            username="general-application-delegate",
            email="general-application-delegate@example.com",
        )
        applicant.users.district = district
        applicant.users.legalName = "General Application Delegate"
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

        applicant.users.refresh_from_db()
        self.assertEqual(applicant.users.userType, "U4D3")

        general = HolcModel.objects.create(
            district=district,
            code=1,
            invitation_key=4567890123,
        )

        request = APIRequestFactory().post(
            "/holc-members/join_invite_key/",
            {
                "inviteKey": general.invitation_key,
                "user": applicant.username,
            },
            format="json",
        )
        force_authenticate(request, user=applicant)

        response = HolcMembersViewSet.as_view(
            {"post": "join_invite_key"}
        )(request)

        self.assertEqual(response.status_code, 403)

        self.assertFalse(
            HolcMembers.objects.filter(
                user=applicant,
                holc=general,
            ).exists()
        )

        applicant.users.refresh_from_db()
        self.assertEqual(applicant.users.userType, "U4D3")

    def test_duplicate_pending_application_is_rejected(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )

        applicant = User.objects.create_user(
            username="duplicate-pending-delegate",
            email="duplicate-pending-delegate@example.com",
        )
        applicant.users.district = district
        applicant.users.legalName = "Duplicate Pending Delegate"
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

        destination_holc = User.objects.create_user(
            username="duplicate-destination-holc",
            email="duplicate-destination-holc@example.com",
        )
        destination_holc.users.district = district
        destination_holc.users.legalName = "Destination HoLC"
        destination_holc.users.address = "2 Test Street"
        destination_holc.users.userType = "U4D3"
        destination_holc.users.save()

        destination = HolcModel.objects.create(
            district=district,
            invitation_key=5678901234,
        )
        HolcMembers.objects.create(
            user=destination_holc,
            holc=destination,
            is_member=True,
        )

        HolcMembers.objects.create(
            user=applicant,
            holc=destination,
            is_member=False,
            is_delegate=False,
        )

        request = APIRequestFactory().post(
            "/holc-members/join_invite_key/",
            {
                "inviteKey": destination.invitation_key,
                "user": applicant.username,
            },
            format="json",
        )
        force_authenticate(request, user=applicant)

        response = HolcMembersViewSet.as_view(
            {"post": "join_invite_key"}
        )(request)

        self.assertEqual(response.status_code, 400)

        self.assertEqual(
            HolcMembers.objects.filter(
                user=applicant,
                holc=destination,
                is_member=False,
            ).count(),
            1,
        )

        applicant.users.refresh_from_db()
        self.assertEqual(applicant.users.userType, "U4D3")

    def test_actual_holc_cannot_apply_even_with_u4d3_role_code(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )

        applicant = User.objects.create_user(
            username="actual-holc-applicant",
            email="actual-holc-applicant@example.com",
        )
        applicant.users.district = district
        applicant.users.legalName = "Actual HoLC Applicant"
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

        source = HolcModel.objects.create(district=district)
        source_membership = HolcMembers.objects.create(
            user=applicant,
            holc=source,
            is_member=True,
        )

        self.assertTrue(source_membership.is_delegate)

        # Simulate a stale or inconsistent cached role code. Authorization
        # must still respect the actual HoLC office.
        applicant.users.userType = "U4D3"
        applicant.users.save(update_fields=["userType"])

        destination_holc = User.objects.create_user(
            username="actual-holc-destination-owner",
            email="actual-holc-destination-owner@example.com",
        )
        destination_holc.users.district = district
        destination_holc.users.legalName = "Destination HoLC"
        destination_holc.users.address = "2 Test Street"
        destination_holc.users.userType = "U4D3"
        destination_holc.users.save()

        destination = HolcModel.objects.create(
            district=district,
            invitation_key=6789012345,
        )
        HolcMembers.objects.create(
            user=destination_holc,
            holc=destination,
            is_member=True,
        )

        request = APIRequestFactory().post(
            "/holc-members/join_invite_key/",
            {
                "inviteKey": destination.invitation_key,
                "user": applicant.username,
            },
            format="json",
        )
        force_authenticate(request, user=applicant)

        response = HolcMembersViewSet.as_view(
            {"post": "join_invite_key"}
        )(request)

        self.assertEqual(response.status_code, 403)

        self.assertFalse(
            HolcMembers.objects.filter(
                user=applicant,
                holc=destination,
            ).exists()
        )

        self.assertTrue(
            HolcMembers.objects.filter(
                user=applicant,
                holc=source,
                is_member=True,
                is_delegate=True,
            ).exists()
        )

class CaucusExitTests(TestCase):
    def test_eligible_delegate_leaving_ordinary_caucus_returns_to_general(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )
        delegates = []

        # Activate two Second Links so General Caucus exists and the
        # second delegate is an eligible U4D3 Caucus Delegate.
        for link_number in range(2):
            second_link = ModaModel.objects.create(district=district)

            for member_number in range(6):
                username = (
                    f"leave-link-{link_number}-member-{member_number}"
                )
                user = User.objects.create_user(
                    username=username,
                    email=f"{username}@example.com",
                )
                user.users.district = district
                user.users.legalName = username
                user.users.address = "1 Test Street"
                user.users.userType = "U2D2"
                user.users.save()

                ModaMembers.objects.create(
                    user=user,
                    moda=second_link,
                    is_member=True,
                )

                if member_number == 0:
                    delegates.append(user)

            self.assertTrue(second_link.is_active)

        general = HolcModel.objects.get(
            district=district,
            code=1,
        )
        applicant = delegates[1]

        applicant.users.refresh_from_db()
        self.assertEqual(applicant.users.userType, "U4D3")

        # Create an ordinary Caucus with a separate HoLC.
        caucus_owner = User.objects.create_user(
            username="leave-destination-holc",
            email="leave-destination-holc@example.com",
        )
        caucus_owner.users.district = district
        caucus_owner.users.legalName = "Destination HoLC"
        caucus_owner.users.address = "2 Test Street"
        caucus_owner.users.userType = "U4D3"
        caucus_owner.users.save()

        ordinary = HolcModel.objects.create(district=district)
        HolcMembers.objects.create(
            user=caucus_owner,
            holc=ordinary,
            is_member=True,
        )

        self.assertEqual(ordinary.code, 2)

        # Establish the precondition: the eligible delegate has already
        # transferred from General Caucus into the ordinary Caucus.
        HolcMembers.objects.filter(
            user=applicant,
            holc=general,
            is_member=True,
        ).delete()

        ordinary_membership = HolcMembers.objects.create(
            user=applicant,
            holc=ordinary,
            is_member=True,
            is_delegate=False,
        )

        self.assertFalse(
            HolcMembers.objects.filter(
                user=applicant,
                holc=general,
                is_member=True,
            ).exists()
        )
        self.assertTrue(
            HolcMembers.objects.filter(
                user=applicant,
                holc=ordinary,
                is_member=True,
                is_delegate=False,
            ).exists()
        )

        request = APIRequestFactory().delete(
            f"/holc-members/{ordinary_membership.pk}/"
        )
        force_authenticate(request, user=applicant)

        response = HolcMembersViewSet.as_view(
            {"delete": "destroy"}
        )(
            request,
            pk=ordinary_membership.pk,
        )

        self.assertEqual(response.status_code, 204)

        # Leaving the ordinary Caucus returns an otherwise eligible
        # Caucus Delegate to General Caucus automatically.
        self.assertFalse(
            HolcMembers.objects.filter(
                user=applicant,
                holc=ordinary,
                is_member=True,
            ).exists()
        )
        self.assertTrue(
            HolcMembers.objects.filter(
                user=applicant,
                holc=general,
                is_member=True,
                is_delegate=False,
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

        # Voluntary Caucus exit does not affect the underlying
        # Second Link delegate mandate.
        self.assertTrue(
            ModaMembers.objects.filter(
                user=applicant,
                is_member=True,
                is_delegate=True,
                moda__district=district,
                moda__status=True,
            ).exists()
        )

    def test_expelled_eligible_delegate_returns_to_general(self):
        district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )
        delegates = []

        for link_number in range(2):
            second_link = ModaModel.objects.create(district=district)

            for member_number in range(6):
                username = (
                    f"expel-link-{link_number}-member-{member_number}"
                )
                user = User.objects.create_user(
                    username=username,
                    email=f"{username}@example.com",
                )
                user.users.district = district
                user.users.legalName = username
                user.users.address = "1 Test Street"
                user.users.userType = "U2D2"
                user.users.save()

                ModaMembers.objects.create(
                    user=user,
                    moda=second_link,
                    is_member=True,
                )

                if member_number == 0:
                    delegates.append(user)

            self.assertTrue(second_link.is_active)

        general = HolcModel.objects.get(
            district=district,
            code=1,
        )
        expelled_user = delegates[1]

        caucus_owner = User.objects.create_user(
            username="expulsion-caucus-holc",
            email="expulsion-caucus-holc@example.com",
        )
        caucus_owner.users.district = district
        caucus_owner.users.legalName = "Expulsion Caucus HoLC"
        caucus_owner.users.address = "2 Test Street"
        caucus_owner.users.userType = "U4D3"
        caucus_owner.users.save()

        ordinary = HolcModel.objects.create(district=district)
        HolcMembers.objects.create(
            user=caucus_owner,
            holc=ordinary,
            is_member=True,
        )

        HolcMembers.objects.filter(
            user=expelled_user,
            holc=general,
            is_member=True,
        ).delete()

        ordinary_membership = HolcMembers.objects.create(
            user=expelled_user,
            holc=ordinary,
            is_member=True,
            is_delegate=False,
        )

        general_membership = expel_eligible_delegate_to_general(
            ordinary_membership
        )

        self.assertEqual(general_membership.holc, general)
        self.assertTrue(general_membership.is_member)
        self.assertFalse(general_membership.is_delegate)

        self.assertFalse(
            HolcMembers.objects.filter(
                user=expelled_user,
                holc=ordinary,
                is_member=True,
            ).exists()
        )

        self.assertEqual(
            HolcMembers.objects.filter(
                user=expelled_user,
                is_member=True,
            ).count(),
            1,
        )

        expelled_user.users.refresh_from_db()
        self.assertEqual(expelled_user.users.userType, "U4D3")

        self.assertTrue(
            ModaMembers.objects.filter(
                user=expelled_user,
                is_member=True,
                is_delegate=True,
                moda__district=district,
                moda__status=True,
            ).exists()
        )
