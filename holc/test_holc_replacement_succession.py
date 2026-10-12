from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase

from holc.models import (
    HolcBackNForthChat,
    HolcMembers,
    HolcModel,
    PutForwardHolcMember,
)
from moda.models import ModaMembers, ModaModel
from vote.models import Districts


class HolcReplacementSuccessionTests(TestCase):
    def setUp(self):
        self.district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )

        self.caucus = HolcModel.objects.create(
            district=self.district,
        )

        self.incumbent_user = self.create_user(
            "holc_incumbent",
            "HoLC Incumbent",
        )
        self.candidate_user = self.create_user(
            "holc_candidate",
            "HoLC Candidate",
        )
        self.voter_user = self.create_user(
            "holc_voter",
            "HoLC Voter",
        )

        self.incumbent = HolcMembers.objects.create(
            user=self.incumbent_user,
            holc=self.caucus,
            is_member=True,
        )
        self.candidate = HolcMembers.objects.create(
            user=self.candidate_user,
            holc=self.caucus,
            is_member=True,
        )
        self.voter = HolcMembers.objects.create(
            user=self.voter_user,
            holc=self.caucus,
            is_member=True,
        )

        # The candidate must hold an active Second Delegate mandate
        # in the same district to be eligible to become HoLC.
        self.second_link = ModaModel.objects.create(
            district=self.district,
            status=True,
        )
        ModaMembers.objects.create(
            user=self.candidate_user,
            moda=self.second_link,
            is_member=True,
        )

    def test_holc_replacement_swaps_with_candidate_farther_down_line(self):
        HolcMembers.objects.filter(pk=self.candidate.pk).update(
            succession_position=2
        )
        HolcMembers.objects.filter(pk=self.voter.pk).update(
            succession_position=1
        )
        self.candidate.refresh_from_db()
        self.voter.refresh_from_db()
        PutForwardHolcMember.objects.create(
            voter=self.candidate_user,
            candidate=self.candidate,
            holc=self.caucus,
        )
        PutForwardHolcMember.objects.create(
            voter=self.voter_user,
            candidate=self.candidate,
            holc=self.caucus,
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

    def create_user(self, username, legal_name):
        user = User.objects.create_user(
            username=username,
            email=f"{username}@example.com",
        )
        user.users.district = self.district
        user.users.legalName = legal_name
        user.users.address = "1 Test Street"
        user.users.userType = "U4D3"
        user.users.save()
        return user

    def test_holc_replacement_moves_new_holc_to_position_zero(self):
        self.assertEqual(self.incumbent.succession_position, 0)
        self.assertEqual(self.candidate.succession_position, 1)
        self.assertEqual(self.voter.succession_position, 2)

        PutForwardHolcMember.objects.create(
            voter=self.candidate_user,
            candidate=self.candidate,
            holc=self.caucus,
        )
        PutForwardHolcMember.objects.create(
            voter=self.voter_user,
            candidate=self.candidate,
            holc=self.caucus,
        )

        self.incumbent.refresh_from_db()
        self.candidate.refresh_from_db()

        self.assertFalse(self.incumbent.is_delegate)
        self.assertEqual(self.incumbent.succession_position, 1)

        self.assertTrue(self.candidate.is_delegate)
        self.assertEqual(self.candidate.succession_position, 0)

        position_zero = HolcMembers.objects.get(
            holc=self.caucus,
            is_member=True,
            succession_position=0,
        )
        delegate = HolcMembers.objects.get(
            holc=self.caucus,
            is_member=True,
            is_delegate=True,
        )

        self.assertEqual(position_zero.pk, delegate.pk)

    def test_holc_replacement_notifies_the_caucus_and_both_officeholders(self):
        with self.captureOnCommitCallbacks(execute=True):
            PutForwardHolcMember.objects.create(
                voter=self.candidate_user,
                candidate=self.candidate,
                holc=self.caucus,
            )
            PutForwardHolcMember.objects.create(
                voter=self.voter_user,
                candidate=self.candidate,
                holc=self.caucus,
            )

        system_message = HolcBackNForthChat.objects.get(
            holc=self.caucus,
            is_system=True,
        )

        self.assertIsNone(system_message.sender)
        self.assertEqual(
            system_message.message,
            (
                "Succession update: HoLC Candidate became HoLC, "
                "replacing HoLC Incumbent. HoLC Incumbent moved "
                "from position 0 to position 1."
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