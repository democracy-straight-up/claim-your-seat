from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings

from api.models import BackNForthChat, SecDelMembers, SecDelModel
from vote.models import Districts


class FirstLinkSuccessionNotificationTests(TestCase):
    def setUp(self):
        self.district = Districts.objects.create(
            name="Vermont At-Large",
            code="VT01",
        )

        self.delegate = User.objects.create_user(
            username="sec-del",
            password="testpass",
            email="alice@example.com",
        )
        self.delegate.users.district = self.district
        self.delegate.users.legalName = "Alice Delegate"
        self.delegate.users.save()

        self.first_successor = User.objects.create_user(
            username="first-link-first-successor",
            password="testpass",
            email="carlos@example.com",
        )
        self.first_successor.users.district = self.district
        self.first_successor.users.legalName = "Carlos Successor"
        self.first_successor.users.save()

        self.second_successor = User.objects.create_user(
            username="first-link-second-successor",
            password="testpass",
            email="dahlia@example.com",
        )
        self.second_successor.users.district = self.district
        self.second_successor.users.legalName = "Dahlia Successor"
        self.second_successor.users.save()

        self.first_link = SecDelModel.objects.create(
            district=self.district,
        )

        SecDelMembers.objects.create(
            user=self.delegate,
            sec_del=self.first_link,
            is_member=True,
        )

        self.first_membership = SecDelMembers.objects.create(
            user=self.first_successor,
            sec_del=self.first_link,
            is_member=True,
        )

        self.second_membership = SecDelMembers.objects.create(
            user=self.second_successor,
            sec_del=self.first_link,
            is_member=True,
        )

    def test_position_swap_posts_exact_change_to_first_link_back_and_forth(
        self,
    ):
        moved = self.second_membership.move_forward_one_position()

        self.assertTrue(moved)

        messages = BackNForthChat.objects.filter(
            sec_del=self.first_link,
        )

        self.assertEqual(messages.count(), 1)

        message = messages.get()

        self.assertIsNone(message.sender)
        self.assertTrue(message.is_system)
        self.assertEqual(
            message.message,
            (
                "Succession update: Dahlia Successor advanced from "
                "position 2 to position 1; Carlos Successor moved "
                "from position 1 to position 2."
            ),
        )

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
    )
    def test_delegate_change_posts_to_back_and_forth_and_emails_both_delegates(
        self,
    ):
        with self.captureOnCommitCallbacks(execute=True):
            moved = self.first_membership.move_forward_one_position()

        self.assertTrue(moved)

        messages = BackNForthChat.objects.filter(
            sec_del=self.first_link,
        )

        self.assertEqual(messages.count(), 1)

        message = messages.get()

        self.assertIsNone(message.sender)
        self.assertTrue(message.is_system)
        self.assertEqual(
            message.message,
            (
                "Succession update: Carlos Successor became "
                "Sec-Del, replacing Alice Delegate. "
                "Alice Delegate moved from position 0 to position 1."
            ),
        )

        self.assertEqual(len(mail.outbox), 2)

        recipients = {
            recipient
            for email in mail.outbox
            for recipient in email.to
        }

        self.assertEqual(
            recipients,
            {
                "alice@example.com",
                "carlos@example.com",
            },
        )
