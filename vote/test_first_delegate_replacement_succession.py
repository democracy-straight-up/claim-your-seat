from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase

from vote.models import (
    CircleBackNForth,
    CircleMember_put_forward,
    Districts,
    Group,
    GroupMember,
)


class FirstDelegateReplacementSuccessionTests(TestCase):
    def setUp(self):
        self.district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )

        self.circle = Group.objects.create(
            code="C1001",
            district=self.district,
            invitation_code="1234567890",
            group_type=1,
        )

        self.incumbent_user = self.create_user(
            "first_delegate_incumbent",
            "First Delegate Incumbent",
        )
        self.candidate_user = self.create_user(
            "first_delegate_candidate",
            "First Delegate Candidate",
        )
        self.voter_user = self.create_user(
            "first_delegate_voter",
            "First Delegate Voter",
        )

        self.incumbent = GroupMember.objects.create(
            user=self.incumbent_user,
            group=self.circle,
            is_member=True,
        )
        self.candidate = GroupMember.objects.create(
            user=self.candidate_user,
            group=self.circle,
            is_member=True,
        )
        self.voter = GroupMember.objects.create(
            user=self.voter_user,
            group=self.circle,
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
        user.users.userType = "U1D0"
        user.users.save()
        return user

    def test_first_delegate_replacement_moves_new_delegate_to_position_zero(
        self,
    ):
        self.assertEqual(self.incumbent.succession_position, 0)
        self.assertEqual(self.candidate.succession_position, 1)
        self.assertEqual(self.voter.succession_position, 2)

        CircleMember_put_forward.objects.create(
            voter=self.candidate_user,
            recipient=self.candidate,
            group=self.circle,
        )
        CircleMember_put_forward.objects.create(
            voter=self.voter_user,
            recipient=self.candidate,
            group=self.circle,
        )

        self.incumbent.refresh_from_db()
        self.candidate.refresh_from_db()

        self.assertFalse(self.incumbent.is_delegate)
        self.assertEqual(self.incumbent.succession_position, 1)

        self.assertTrue(self.candidate.is_delegate)
        self.assertEqual(self.candidate.succession_position, 0)

        position_zero = GroupMember.objects.get(
            group=self.circle,
            is_member=True,
            succession_position=0,
        )
        delegate = GroupMember.objects.get(
            group=self.circle,
            is_member=True,
            is_delegate=True,
        )

        self.assertEqual(position_zero.pk, delegate.pk)

    def test_first_delegate_replacement_swaps_with_candidate_farther_down_line(
        self,
    ):
        GroupMember.objects.filter(pk=self.candidate.pk).update(
            succession_position=2
        )
        GroupMember.objects.filter(pk=self.voter.pk).update(
            succession_position=1
        )

        self.candidate.refresh_from_db()
        self.voter.refresh_from_db()

        CircleMember_put_forward.objects.create(
            voter=self.candidate_user,
            recipient=self.candidate,
            group=self.circle,
        )
        CircleMember_put_forward.objects.create(
            voter=self.voter_user,
            recipient=self.candidate,
            group=self.circle,
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

    def test_first_delegate_replacement_notifies_circle_and_officeholders(
        self,
    ):
        with self.captureOnCommitCallbacks(execute=True):
            CircleMember_put_forward.objects.create(
                voter=self.candidate_user,
                recipient=self.candidate,
                group=self.circle,
            )
            CircleMember_put_forward.objects.create(
                voter=self.voter_user,
                recipient=self.candidate,
                group=self.circle,
            )

        system_message = CircleBackNForth.objects.get(
            circle=self.circle,
            is_system=True,
        )

        self.assertIsNone(system_message.sender)
        self.assertEqual(
            system_message.message,
            (
                "Succession update: First Delegate Candidate became "
                "F-Del, replacing First Delegate Incumbent. "
                "First Delegate Incumbent moved from position 0 to "
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