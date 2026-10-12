from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase

from moda.models import (
    ModaBackNForthChat,
    ModaMembers,
    ModaModel,
    PutFarwardModaMember,
)
from vote.models import Districts


class CaucusDelegateReplacementSuccessionTests(TestCase):
    def setUp(self):
        self.district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )

        self.second_link = ModaModel.objects.create(
            district=self.district,
        )

        self.incumbent_user = self.create_user(
            "caucus_delegate_incumbent",
            "Caucus Delegate Incumbent",
        )
        self.candidate_user = self.create_user(
            "caucus_delegate_candidate",
            "Caucus Delegate Candidate",
        )
        self.voter_user = self.create_user(
            "caucus_delegate_voter",
            "Caucus Delegate Voter",
        )

        self.incumbent = ModaMembers.objects.create(
            user=self.incumbent_user,
            moda=self.second_link,
            is_member=True,
        )
        self.candidate = ModaMembers.objects.create(
            user=self.candidate_user,
            moda=self.second_link,
            is_member=True,
        )
        self.voter = ModaMembers.objects.create(
            user=self.voter_user,
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

    def test_caucus_delegate_replacement_moves_new_delegate_to_position_zero(
        self,
    ):
        self.assertEqual(self.incumbent.succession_position, 0)
        self.assertEqual(self.candidate.succession_position, 1)
        self.assertEqual(self.voter.succession_position, 2)

        PutFarwardModaMember.objects.create(
            voter=self.candidate_user,
            candidate=self.candidate,
            moda=self.second_link,
        )
        PutFarwardModaMember.objects.create(
            voter=self.voter_user,
            candidate=self.candidate,
            moda=self.second_link,
        )

        self.incumbent.refresh_from_db()
        self.candidate.refresh_from_db()

        self.assertFalse(self.incumbent.is_delegate)
        self.assertEqual(self.incumbent.succession_position, 1)

        self.assertTrue(self.candidate.is_delegate)
        self.assertEqual(self.candidate.succession_position, 0)

        position_zero = ModaMembers.objects.get(
            moda=self.second_link,
            is_member=True,
            succession_position=0,
        )
        delegate = ModaMembers.objects.get(
            moda=self.second_link,
            is_member=True,
            is_delegate=True,
        )

        self.assertEqual(position_zero.pk, delegate.pk)

    def test_caucus_delegate_replacement_swaps_with_candidate_farther_down_line(
        self,
    ):
        ModaMembers.objects.filter(pk=self.candidate.pk).update(
            succession_position=2
        )
        ModaMembers.objects.filter(pk=self.voter.pk).update(
            succession_position=1
        )

        self.candidate.refresh_from_db()
        self.voter.refresh_from_db()

        PutFarwardModaMember.objects.create(
            voter=self.candidate_user,
            candidate=self.candidate,
            moda=self.second_link,
        )
        PutFarwardModaMember.objects.create(
            voter=self.voter_user,
            candidate=self.candidate,
            moda=self.second_link,
        )

        self.incumbent.refresh_from_db()
        self.candidate.refresh_from_db()
        self.voter.refresh_from_db()

        self.assertFalse(self.incumbent.is_delegate)
        self.assertEqual(self.incumbent.succession_position, 2)

        self.assertTrue(self.candidate.is_delegate)
        self.assertEqual(self.candidate.succession_position, 0)

        self.assertFalse(self.voter.is_delegate)
        self.assertEqual(self.voter.succession_position, 1)

    def test_caucus_delegate_replacement_notifies_second_link_and_officeholders(
        self,
    ):
        with self.captureOnCommitCallbacks(execute=True):
            PutFarwardModaMember.objects.create(
                voter=self.candidate_user,
                candidate=self.candidate,
                moda=self.second_link,
            )
            PutFarwardModaMember.objects.create(
                voter=self.voter_user,
                candidate=self.candidate,
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
                "Succession update: Caucus Delegate Candidate became "
                "Caucus Delegate, replacing Caucus Delegate Incumbent. "
                "Caucus Delegate Incumbent moved from position 0 to "
                "position 1."
            ),
        )

        email_recipients = {
            recipient
            for message in mail.outbox
            for recipient in message.to
        }

        self.assertIn(
            self.incumbent_user.email,
            email_recipients,
        )
        self.assertIn(
            self.candidate_user.email,
            email_recipients,
        )