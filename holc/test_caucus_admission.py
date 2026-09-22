from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate
from moda.models import ModaMembers, ModaModel
from holc.models import HolcMembers, HolcModel
from holc.views import HolcViewSet
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