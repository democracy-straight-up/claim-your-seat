from django.contrib.auth.models import User
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate
from moda.views import ModaMembersViewSet, ModaViewSet
from holc.models import HolcMembers, HolcModel
from moda.models import (
    ModaBackNForthChat,
    ModaMembers,
    ModaModel,
    VoteOutModaMember,
)
from vote.models import Districts


class SecondLinkDirectRemovalSuccessionTests(TestCase):
    def setUp(self):
        self.district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )

        self.second_link = ModaModel.objects.create(
            district=self.district,
        )

        self.delegate_user = self.create_user(
            "removal_caucus_delegate",
            "Removal Caucus Delegate",
        )
        self.removed_user = self.create_user(
            "removal_second_link_member",
            "Removal Second Link Member",
        )
        self.successor_user = self.create_user(
            "removal_second_link_successor",
            "Removal Second Link Successor",
        )

        self.delegate = ModaMembers.objects.create(
            user=self.delegate_user,
            moda=self.second_link,
            is_member=True,
        )
        self.removed_member = ModaMembers.objects.create(
            user=self.removed_user,
            moda=self.second_link,
            is_member=True,
        )
        self.successor = ModaMembers.objects.create(
            user=self.successor_user,
            moda=self.second_link,
            is_member=True,
        )

    def create_user(self, username, legal_name):
        user = User.objects.create_user(
            username=username,
            email=f"{username}@example.com",
        )
        user.users.district = self.district
        user.users.legalName = legal_name
        user.users.address = "1 Test Street"
        user.users.userType = "U3D2"
        user.users.save()
        return user

    def test_removing_non_delegate_compacts_second_link_succession_line(self):
        self.assertEqual(self.delegate.succession_position, 0)
        self.assertEqual(self.removed_member.succession_position, 1)
        self.assertEqual(self.successor.succession_position, 2)

        VoteOutModaMember.objects.create(
            voter=self.delegate_user,
            candidate=self.removed_member,
            moda=self.second_link,
        )
        VoteOutModaMember.objects.create(
            voter=self.successor_user,
            candidate=self.removed_member,
            moda=self.second_link,
        )

        self.assertFalse(
            ModaMembers.objects.filter(
                pk=self.removed_member.pk
            ).exists()
        )

        self.delegate.refresh_from_db()
        self.successor.refresh_from_db()

        self.assertTrue(self.delegate.is_delegate)
        self.assertEqual(self.delegate.succession_position, 0)

        self.assertFalse(self.successor.is_delegate)
        self.assertEqual(self.successor.succession_position, 1)

    def test_removing_non_delegate_records_compaction_in_second_link_back_and_forth(
        self,
    ):
        VoteOutModaMember.objects.create(
            voter=self.delegate_user,
            candidate=self.removed_member,
            moda=self.second_link,
        )
        VoteOutModaMember.objects.create(
            voter=self.successor_user,
            candidate=self.removed_member,
            moda=self.second_link,
        )

        system_message = ModaBackNForthChat.objects.get(
            moda=self.second_link,
            is_system=True,
        )

        self.assertIsNone(system_message.sender)
        self.assertEqual(
            system_message.message,
            (
                "Succession update: Removal Second Link Successor moved "
                "from position 2 to position 1 after Removal Second Link "
                "Member was removed."
            ),
        )

    def test_removing_caucus_delegate_promotes_position_one(self):
        VoteOutModaMember.objects.create(
            voter=self.removed_user,
            candidate=self.delegate,
            moda=self.second_link,
        )
        VoteOutModaMember.objects.create(
            voter=self.successor_user,
            candidate=self.delegate,
            moda=self.second_link,
        )

        self.assertFalse(
            ModaMembers.objects.filter(
                pk=self.delegate.pk
            ).exists()
        )

        self.removed_member.refresh_from_db()
        self.successor.refresh_from_db()
        self.removed_user.users.refresh_from_db()

        self.assertTrue(self.removed_member.is_delegate)
        self.assertEqual(
            self.removed_member.succession_position,
            0,
        )
        self.assertEqual(
            self.removed_user.users.userType,
            "U4D3",
        )

        self.assertFalse(self.successor.is_delegate)
        self.assertEqual(
            self.successor.succession_position,
            1,
        )

        self.assertEqual(
            ModaMembers.objects.filter(
                moda=self.second_link,
                is_member=True,
                is_delegate=True,
            ).count(),
            1,
        )

    def test_removing_caucus_delegate_removes_dependent_caucus_membership(
        self,
    ):
        caucus = HolcModel.objects.create(
            district=self.district,
        )

        caucus_founder_user = self.create_user(
            "caucus_founder",
            "Caucus Founder",
        )

        HolcMembers.objects.create(
            user=caucus_founder_user,
            holc=caucus,
            is_member=True,
        )

        dependent_membership = HolcMembers.objects.create(
            user=self.delegate_user,
            holc=caucus,
            is_member=True,
        )

        self.assertTrue(
            HolcMembers.objects.filter(
                pk=dependent_membership.pk
            ).exists()
        )

        VoteOutModaMember.objects.create(
            voter=self.removed_user,
            candidate=self.delegate,
            moda=self.second_link,
        )
        VoteOutModaMember.objects.create(
            voter=self.successor_user,
            candidate=self.delegate,
            moda=self.second_link,
        )

        self.assertFalse(
            HolcMembers.objects.filter(
                pk=dependent_membership.pk
            ).exists()
        )

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
    )
    def test_removing_caucus_delegate_posts_promotion_and_sends_emails(
        self,
    ):
        with self.captureOnCommitCallbacks(execute=True):
            VoteOutModaMember.objects.create(
                voter=self.removed_user,
                candidate=self.delegate,
                moda=self.second_link,
            )
            VoteOutModaMember.objects.create(
                voter=self.successor_user,
                candidate=self.delegate,
                moda=self.second_link,
            )

        self.removed_member.refresh_from_db()

        self.assertTrue(self.removed_member.is_delegate)
        self.assertEqual(
            self.removed_member.succession_position,
            0,
        )

        messages = ModaBackNForthChat.objects.filter(
            moda=self.second_link,
            is_system=True,
        )

        promotion_messages = [
            message
            for message in messages
            if (
                "Removal Second Link Member became Caucus Delegate"
                in message.message
                and "Removal Caucus Delegate" in message.message
            )
        ]

        self.assertEqual(len(promotion_messages), 1)
        self.assertIsNone(promotion_messages[0].sender)
        self.assertNotIn(
            "position None",
            promotion_messages[0].message,
        )
        recipients = {
            recipient
            for email in mail.outbox
            for recipient in email.to
        }

        self.assertEqual(
            recipients,
            {
                "removal_caucus_delegate@example.com",
                "removal_second_link_member@example.com",
            },
        )
        outgoing_emails = [
            email
            for email in mail.outbox
            if "removal_caucus_delegate@example.com" in email.to
        ]

        self.assertEqual(len(outgoing_emails), 1)
        self.assertIn(
            "you were removed from",
            outgoing_emails[0].body,
        )
        self.assertNotIn(
            "position None",
            outgoing_emails[0].body,
        )
        self.assertNotIn(
            "lower-level",
            outgoing_emails[0].body,
        )

    def test_caucus_delegate_cannot_voluntarily_leave_second_link(
        self,
    ):
        factory = APIRequestFactory()

        request = factory.delete(
            f"/moda-members/{self.delegate.pk}/"
        )
        force_authenticate(
            request,
            user=self.delegate_user,
        )

        view = ModaMembersViewSet.as_view({
            "delete": "destroy",
        })

        response = view(
            request,
            pk=self.delegate.pk,
        )

        self.assertEqual(response.status_code, 403)

        self.delegate.refresh_from_db()

        self.assertTrue(self.delegate.is_member)
        self.assertTrue(self.delegate.is_delegate)
        self.assertEqual(
            self.delegate.succession_position,
            0,
        )

        self.assertEqual(
            ModaMembers.objects.filter(
                moda=self.second_link,
                is_member=True,
            ).count(),
            3,
        )

    def test_non_delegate_can_voluntarily_leave_second_link(self):
        factory = APIRequestFactory()
        request = factory.delete(
            f"/moda-members/{self.successor.pk}/"
        )
        force_authenticate(request, user=self.successor_user)

        view = ModaMembersViewSet.as_view({
            "delete": "destroy",
        })
        response = view(request, pk=self.successor.pk)

        self.assertEqual(response.status_code, 204)
        self.assertFalse(
            ModaMembers.objects.filter(pk=self.successor.pk).exists()
        )

        self.delegate.refresh_from_db()
        self.assertTrue(self.delegate.is_delegate)
        self.assertTrue(self.delegate.is_member)

    def test_member_cannot_delete_another_members_membership(self):
        factory = APIRequestFactory()
        request = factory.delete(
            f"/moda-members/{self.removed_member.pk}/"
        )
        force_authenticate(request, user=self.successor_user)

        view = ModaMembersViewSet.as_view({
            "delete": "destroy",
        })
        response = view(request, pk=self.removed_member.pk)

        self.assertEqual(response.status_code, 403)
        self.assertTrue(
            ModaMembers.objects.filter(
                pk=self.removed_member.pk,
                is_member=True,
            ).exists()
        )

    def test_voluntary_departure_compacts_second_link_succession(self):
        factory = APIRequestFactory()
        view = ModaMembersViewSet.as_view({
            "delete": "destroy",
        })

        request = factory.delete(
            f"/moda-members/{self.removed_member.pk}/"
        )
        force_authenticate(request, user=self.removed_user)

        response = view(request, pk=self.removed_member.pk)

        self.assertEqual(response.status_code, 204)

        self.assertFalse(
            ModaMembers.objects.filter(
                pk=self.removed_member.pk
            ).exists()
        )

        self.successor.refresh_from_db()

        self.assertEqual(
            self.successor.succession_position,
            1,
        )

        self.delegate.refresh_from_db()
        self.assertTrue(self.delegate.is_delegate)
        self.assertEqual(self.delegate.succession_position, 0)

    def test_voluntary_departure_records_compaction_in_back_and_forth(
        self,
    ):
        factory = APIRequestFactory()
        request = factory.delete(
            f"/moda-members/{self.removed_member.pk}/"
        )
        force_authenticate(request, user=self.removed_user)

        view = ModaMembersViewSet.as_view({
            "delete": "destroy",
        })
        response = view(request, pk=self.removed_member.pk)

        self.assertEqual(response.status_code, 204)

        messages = ModaBackNForthChat.objects.filter(
            moda=self.second_link,
            is_system=True,
        )

        self.assertEqual(messages.count(), 1)

        message = messages.get()
        self.assertIsNone(message.sender)
        self.assertEqual(
            message.message,
            (
                "Succession update: Removal Second Link Successor "
                "moved from position 2 to position 1 after "
                "Removal Second Link Member voluntarily left "
                "the Second Link."
            ),
        )

    def test_sole_member_can_dissolve_second_link(self):
        # Remove the other accepted members from this test fixture.
        ModaMembers.objects.filter(
            pk__in=[
                self.removed_member.pk,
                self.successor.pk,
            ]
        ).delete()

        self.assertEqual(
            ModaMembers.objects.filter(
                moda=self.second_link,
                is_member=True,
            ).count(),
            1,
        )

        second_link_pk = self.second_link.pk

        self.second_link.delete()

        self.assertFalse(
            ModaModel.objects.filter(pk=second_link_pk).exists()
        )
        self.assertFalse(
            ModaMembers.objects.filter(
                moda_id=second_link_pk,
            ).exists()
        )

        self.delegate_user.users.refresh_from_db()
        self.assertEqual(
            self.delegate_user.users.userType,
            "U2D2",
        )

    def test_second_link_cannot_be_dissolved_with_multiple_members(self):
        second_link_pk = self.second_link.pk

        # The fixture begins with three accepted members.
        self.assertEqual(
            ModaMembers.objects.filter(
                moda=self.second_link,
                is_member=True,
            ).count(),
            3,
        )

        # Direct model deletion must reject dissolution.
        with self.assertRaises(ValidationError):
            self.second_link.delete()

        # Rejection must leave the entire group intact.
        self.assertTrue(
            ModaModel.objects.filter(pk=second_link_pk).exists()
        )

        self.assertEqual(
            ModaMembers.objects.filter(
                moda_id=second_link_pk,
                is_member=True,
            ).count(),
            3,
        )

        self.delegate.refresh_from_db()
        self.assertTrue(self.delegate.is_delegate)
        self.assertEqual(self.delegate.succession_position, 0)

    def test_nonmember_cannot_delete_second_link_via_rest(self):
        # Leave only the current Caucus Delegate in the group.
        ModaMembers.objects.filter(
            pk__in=[
                self.removed_member.pk,
                self.successor.pk,
            ]
        ).delete()

        self.assertEqual(
            ModaMembers.objects.filter(
                moda=self.second_link,
                is_member=True,
            ).count(),
            1,
        )

        second_link_pk = self.second_link.pk

        # A former member attempts deletion through the REST API.
        request = APIRequestFactory().delete(
            f"/moda/{second_link_pk}/"
        )
        force_authenticate(
            request,
            user=self.successor_user,
        )

        view = ModaViewSet.as_view({
            "delete": "destroy",
        })

        response = view(
            request,
            pk=second_link_pk,
        )

        self.assertEqual(response.status_code, 403)

        # The group and its delegate must remain intact.
        self.assertTrue(
            ModaModel.objects.filter(
                pk=second_link_pk,
            ).exists()
        )

        self.delegate.refresh_from_db()
        self.assertTrue(self.delegate.is_member)
        self.assertTrue(self.delegate.is_delegate)

    def test_sole_delegate_can_dissolve_second_link_via_rest(self):
        # Leave only the serving Caucus Delegate.
        ModaMembers.objects.filter(
            pk__in=[
                self.removed_member.pk,
                self.successor.pk,
            ]
        ).delete()

        self.assertEqual(
            ModaMembers.objects.filter(
                moda=self.second_link,
                is_member=True,
            ).count(),
            1,
        )

        second_link_pk = self.second_link.pk

        request = APIRequestFactory().delete(
            f"/moda/{second_link_pk}/"
        )
        force_authenticate(
            request,
            user=self.delegate_user,
        )

        view = ModaViewSet.as_view({
            "delete": "destroy",
        })

        response = view(
            request,
            pk=second_link_pk,
        )

        self.assertEqual(response.status_code, 204)

        # The Second Link and its memberships are gone.
        self.assertFalse(
            ModaModel.objects.filter(
                pk=second_link_pk,
            ).exists()
        )

        self.assertFalse(
            ModaMembers.objects.filter(
                moda_id=second_link_pk,
            ).exists()
        )

        # Alice retains her underlying Second Delegate mandate.
        self.delegate_user.users.refresh_from_db()
        self.assertEqual(
            self.delegate_user.users.userType,
            "U2D2",
        )

    def test_delegate_cannot_dissolve_multi_member_second_link_via_rest(self):
        second_link_pk = self.second_link.pk

        # The existing fixture has three accepted members.
        self.assertEqual(
            ModaMembers.objects.filter(
                moda=self.second_link,
                is_member=True,
            ).count(),
            3,
        )

        request = APIRequestFactory().delete(
            f"/moda/{second_link_pk}/"
        )
        force_authenticate(
            request,
            user=self.delegate_user,
        )

        view = ModaViewSet.as_view({
            "delete": "destroy",
        })

        response = view(
            request,
            pk=second_link_pk,
        )

        self.assertEqual(response.status_code, 409)

        # The group and all memberships remain intact.
        self.assertTrue(
            ModaModel.objects.filter(pk=second_link_pk).exists()
        )

        self.assertEqual(
            ModaMembers.objects.filter(
                moda_id=second_link_pk,
                is_member=True,
            ).count(),
            3,
        )

        self.delegate.refresh_from_db()
        self.assertTrue(self.delegate.is_delegate)
        self.assertEqual(self.delegate.succession_position, 0)

    def test_cannot_create_second_link_for_another_user(self):
        victim = self.create_user(
            "unauthorized_link_victim",
            "Unauthorized Link Victim",
        )

        # Make the victim eligible to found a Second Link.
        victim.users.userType = "U2D2"
        victim.users.save(update_fields=["userType"])

        original_count = ModaModel.objects.count()

        # An unrelated authenticated user tries to
        # create a Second Link in the victim's name.
        request = APIRequestFactory().post(
            "/moda/",
            {
                "user": victim.username,
                "district": self.district.code,
            },
            format="json",
        )

        force_authenticate(
            request,
            user=self.removed_user,
        )

        view = ModaViewSet.as_view({
            "post": "create",
        })

        response = view(request)

        self.assertEqual(response.status_code, 403)

        # No unauthorized group or membership is created.
        self.assertEqual(
            ModaModel.objects.count(),
            original_count,
        )

        self.assertFalse(
            ModaMembers.objects.filter(
                user=victim,
            ).exists()
        )
    def test_eligible_user_can_create_own_second_link(self):
        founder = self.create_user(
            "authorized_link_founder",
            "Authorized Link Founder",
        )

        founder.users.userType = "U2D2"
        founder.users.save(update_fields=["userType"])

        original_count = ModaModel.objects.count()

        request = APIRequestFactory().post(
            "/moda/",
            {
                "user": founder.username,
                "district": self.district.code,
            },
            format="json",
        )
        force_authenticate(request, user=founder)

        view = ModaViewSet.as_view({"post": "create"})
        response = view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            ModaModel.objects.count(),
            original_count + 1,
        )

        membership = ModaMembers.objects.get(user=founder)

        self.assertTrue(membership.is_member)
        self.assertTrue(membership.is_delegate)
        self.assertEqual(membership.succession_position, 0)
        self.assertEqual(membership.moda.district, self.district)
    def test_existing_delegate_cannot_create_another_second_link(self):
        # The fixture already makes this user the
        # Caucus Delegate of an existing Second Link.
        self.delegate.refresh_from_db()
        self.assertTrue(self.delegate.is_member)
        self.assertTrue(self.delegate.is_delegate)

        original_group_count = ModaModel.objects.count()
        original_membership_count = ModaMembers.objects.filter(
            user=self.delegate_user,
        ).count()

        request = APIRequestFactory().post(
            "/moda/",
            {
                "user": self.delegate_user.username,
                "district": self.district.code,
            },
            format="json",
        )

        force_authenticate(
            request,
            user=self.delegate_user,
        )

        view = ModaViewSet.as_view({"post": "create"})
        response = view(request)

        # Existing members cannot found another Second Link.
        self.assertEqual(response.status_code, 400)

        self.assertEqual(
            ModaModel.objects.count(),
            original_group_count,
        )

        self.assertEqual(
            ModaMembers.objects.filter(
                user=self.delegate_user,
            ).count(),
            original_membership_count,
        )

        # The original membership remains intact.
        self.delegate.refresh_from_db()
        self.assertTrue(self.delegate.is_delegate)
    def test_member_cannot_promote_self_via_rest_patch(self):
        self.assertTrue(self.delegate.is_delegate)
        self.assertFalse(self.removed_member.is_delegate)

        request = APIRequestFactory().patch(
            f"/moda-members/{self.removed_member.pk}/",
            {"is_delegate": True},
            format="json",
        )

        force_authenticate(
            request,
            user=self.removed_user,
        )

        view = ModaMembersViewSet.as_view({
            "patch": "partial_update",
        })

        response = view(
            request,
            pk=self.removed_member.pk,
        )

        # Direct membership updates must not be available.
        self.assertEqual(response.status_code, 405)

        self.removed_member.refresh_from_db()
        self.delegate.refresh_from_db()

        # The existing Caucus Delegate remains in office.
        self.assertFalse(self.removed_member.is_delegate)
        self.assertTrue(self.delegate.is_delegate)

    def test_member_cannot_change_delegate_via_rest_put(self):
        request = APIRequestFactory().put(
            f"/moda-members/{self.removed_member.pk}/",
            {
                "user": self.removed_user.pk,
                "moda": self.second_link.pk,
                "is_member": True,
                "is_delegate": True,
            },
            format="json",
        )

        force_authenticate(request, user=self.removed_user)

        view = ModaMembersViewSet.as_view({
            "put": "update",
        })

        response = view(
            request,
            pk=self.removed_member.pk,
        )

        self.assertEqual(response.status_code, 405)

        self.removed_member.refresh_from_db()
        self.delegate.refresh_from_db()

        self.assertFalse(self.removed_member.is_delegate)
        self.assertTrue(self.delegate.is_delegate)

    def test_cannot_create_accepted_membership_via_rest(self):
        outsider = self.create_user(
            "unauthorized_membership_outsider",
            "Unauthorized Membership Outsider",
        )

        outsider.users.userType = "U2D2"
        outsider.users.save(update_fields=["userType"])

        self.assertFalse(
            ModaMembers.objects.filter(
                user=outsider,
                moda=self.second_link,
            ).exists()
        )

        # An ordinary member attempts to admit someone
        # directly, bypassing Housekeeping voting.
        request = APIRequestFactory().post(
            "/moda-members/",
            {
                "user": outsider.pk,
                "moda": self.second_link.pk,
                "is_member": True,
                "is_delegate": False,
            },
            format="json",
        )

        force_authenticate(
            request,
            user=self.removed_user,
        )

        view = ModaMembersViewSet.as_view({
            "post": "create",
        })

        response = view(request)

        # Membership creation must use authorized
        # procedures, not generic REST creation.
        self.assertEqual(response.status_code, 405)

        self.assertFalse(
            ModaMembers.objects.filter(
                user=outsider,
                moda=self.second_link,
            ).exists()
        )

        self.assertEqual(
            ModaMembers.objects.filter(
                moda=self.second_link,
                is_member=True,
            ).count(),
            3,
        )
    def test_member_cannot_patch_second_link_via_rest(self):
        self.second_link.refresh_from_db()
        original_status = self.second_link.status

        request = APIRequestFactory().patch(
            f"/moda/{self.second_link.pk}/",
            {"status": not original_status},
            format="json",
        )

        force_authenticate(
            request,
            user=self.removed_user,
        )

        view = ModaViewSet.as_view({
            "patch": "partial_update",
        })

        response = view(
            request,
            pk=self.second_link.pk,
        )

        self.assertEqual(response.status_code, 405)

        self.second_link.refresh_from_db()
        self.assertEqual(
            self.second_link.status,
            original_status,
        )
    def test_member_cannot_update_second_link_via_rest_put(self):
        self.second_link.refresh_from_db()
        original_status = self.second_link.status

        request = APIRequestFactory().put(
            f"/moda/{self.second_link.pk}/",
            {
                "district": self.district.pk,
                "status": not original_status,
            },
            format="json",
        )

        force_authenticate(
            request,
            user=self.removed_user,
        )

        view = ModaViewSet.as_view({
            "put": "update",
        })

        response = view(
            request,
            pk=self.second_link.pk,
        )

        self.assertEqual(response.status_code, 405)

        self.second_link.refresh_from_db()
        self.assertEqual(
            self.second_link.status,
            original_status,
        )
    def test_cannot_join_second_link_for_another_user(self):
        applicant = self.create_user(
            "unauthorized_invitation_applicant",
            "Unauthorized Invitation Applicant",
        )

        applicant.users.userType = "U2D2"
        applicant.users.save(update_fields=["userType"])

        request = APIRequestFactory().post(
            "/moda-members/join_invite_key/",
            {
                "inviteKey": self.second_link.invitation_key,
                "user": applicant.username,
            },
            format="json",
        )

        force_authenticate(
            request,
            user=self.removed_user,
        )

        view = ModaMembersViewSet.as_view({
            "post": "join_invite_key",
        })

        response = view(request)

        self.assertEqual(response.status_code, 403)

        self.assertFalse(
            ModaMembers.objects.filter(
                user=applicant,
                moda=self.second_link,
            ).exists()
        )
    def test_user_can_join_second_link_with_own_invitation(self):
        applicant = self.create_user(
            "authorized_invitation_applicant",
            "Authorized Invitation Applicant",
        )

        applicant.users.userType = "U2D2"
        applicant.users.save(update_fields=["userType"])

        request = APIRequestFactory().post(
            "/moda-members/join_invite_key/",
            {
                "inviteKey": self.second_link.invitation_key,
                "user": applicant.username,
            },
            format="json",
        )

        force_authenticate(request, user=applicant)

        view = ModaMembersViewSet.as_view({
            "post": "join_invite_key",
        })

        response = view(request)

        self.assertEqual(response.status_code, 200)

        membership = ModaMembers.objects.get(
            user=applicant,
            moda=self.second_link,
        )

        # Applying does not automatically confer membership.
        self.assertFalse(membership.is_member)
        self.assertFalse(membership.is_delegate)

        # Existing members and the serving delegate are unchanged.
        self.assertEqual(
            ModaMembers.objects.filter(
                moda=self.second_link,
                is_member=True,
            ).count(),
            3,
        )

        self.delegate.refresh_from_db()
        self.assertTrue(self.delegate.is_delegate)

    def test_existing_member_cannot_apply_to_another_second_link(self):
        # Bob already belongs to the original Second Link.
        self.removed_member.refresh_from_db()
        self.assertTrue(self.removed_member.is_member)

        # Create another Second Link.
        other_link = ModaModel.objects.create(
            district=self.district,
        )

        request = APIRequestFactory().post(
            "/moda-members/join_invite_key/",
            {
                "inviteKey": other_link.invitation_key,
                "user": self.removed_user.username,
            },
            format="json",
        )

        force_authenticate(
            request,
            user=self.removed_user,
        )

        view = ModaMembersViewSet.as_view({
            "post": "join_invite_key",
        })

        response = view(request)

        # Existing members cannot apply to another Link.
        self.assertEqual(response.status_code, 400)

        self.assertFalse(
            ModaMembers.objects.filter(
                user=self.removed_user,
                moda=other_link,
            ).exists()
        )

        # Original membership remains intact.
        self.removed_member.refresh_from_db()
        self.assertTrue(self.removed_member.is_member)

        self.assertEqual(
            ModaMembers.objects.filter(
                user=self.removed_user,
            ).count(),
            1,
        )