from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase

from api.models import (
    BackNForthChat,
    PutFarwardSecDelMember,
    SecDelMembers,
    SecDelModel,
)
from vote.models import Districts


class SecondDelegateReplacementSuccessionTests(TestCase):
    def setUp(self):
        self.district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )

        self.first_link = SecDelModel.objects.create(
            district=self.district,
        )

        self.incumbent_user = self.create_user(
            "second_delegate_incumbent",
            "Second Delegate Incumbent",
        )
        self.candidate_user = self.create_user(
            "second_delegate_candidate",
            "Second Delegate Candidate",
        )
        self.voter_user = self.create_user(
            "second_delegate_voter",
            "Second Delegate Voter",
        )

        self.incumbent = SecDelMembers.objects.create(
            user=self.incumbent_user,
            sec_del=self.first_link,
            is_member=True,
        )
        self.candidate = SecDelMembers.objects.create(
            user=self.candidate_user,
            sec_del=self.first_link,
            is_member=True,
        )
        self.voter = SecDelMembers.objects.create(
            user=self.voter_user,
            sec_del=self.first_link,
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
        user.users.userType = "U2D1"
        user.users.save()
        return user

    def test_second_delegate_replacement_moves_new_delegate_to_position_zero(
        self,
    ):
        self.assertEqual(self.incumbent.succession_position, 0)
        self.assertEqual(self.candidate.succession_position, 1)
        self.assertEqual(self.voter.succession_position, 2)

        PutFarwardSecDelMember.objects.create(
            voter=self.candidate_user,
            candidate=self.candidate,
            sec_del=self.first_link,
        )
        PutFarwardSecDelMember.objects.create(
            voter=self.voter_user,
            candidate=self.candidate,
            sec_del=self.first_link,
        )

        self.incumbent.refresh_from_db()
        self.candidate.refresh_from_db()

        self.assertFalse(self.incumbent.is_delegate)
        self.assertEqual(self.incumbent.succession_position, 1)

        self.assertTrue(self.candidate.is_delegate)
        self.assertEqual(self.candidate.succession_position, 0)

        position_zero = SecDelMembers.objects.get(
            sec_del=self.first_link,
            is_member=True,
            succession_position=0,
        )
        delegate = SecDelMembers.objects.get(
            sec_del=self.first_link,
            is_member=True,
            is_delegate=True,
        )

        self.assertEqual(position_zero.pk, delegate.pk)

    def test_second_delegate_replacement_swaps_with_candidate_farther_down_line(
        self,
    ):
        SecDelMembers.objects.filter(pk=self.candidate.pk).update(
            succession_position=2
        )
        SecDelMembers.objects.filter(pk=self.voter.pk).update(
            succession_position=1
        )

        self.candidate.refresh_from_db()
        self.voter.refresh_from_db()

        PutFarwardSecDelMember.objects.create(
            voter=self.candidate_user,
            candidate=self.candidate,
            sec_del=self.first_link,
        )
        PutFarwardSecDelMember.objects.create(
            voter=self.voter_user,
            candidate=self.candidate,
            sec_del=self.first_link,
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

    def test_second_delegate_replacement_notifies_first_link_and_officeholders(
        self,
    ):
        with self.captureOnCommitCallbacks(execute=True):
            PutFarwardSecDelMember.objects.create(
                voter=self.candidate_user,
                candidate=self.candidate,
                sec_del=self.first_link,
            )
            PutFarwardSecDelMember.objects.create(
                voter=self.voter_user,
                candidate=self.candidate,
                sec_del=self.first_link,
            )

        system_message = BackNForthChat.objects.get(
            sec_del=self.first_link,
            is_system=True,
        )

        self.assertIsNone(system_message.sender)
        self.assertEqual(
            system_message.message,
            (
                "Succession update: Second Delegate Candidate became "
                "Sec-Del, replacing Second Delegate Incumbent. "
                "Second Delegate Incumbent moved from position 0 to "
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