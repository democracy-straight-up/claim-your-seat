from django.contrib.auth.models import User
from django.test import TestCase

from api.serializers import CircleBackNForthSerializer
from vote.models import CircleBackNForth, Districts, Group, Users


class CircleBackNForthSystemMessageTests(TestCase):
    def setUp(self):
        self.district, _ = Districts.objects.get_or_create(
            code="VT00",
            defaults={"name": "Vermont"},
        )

        self.user = User.objects.create_user(
            username="circle-system-test",
            password="local-test-password",
            is_active=True,
        )
        Users.objects.update_or_create(
            user=self.user,
            defaults={"district": self.district},
        )

        self.circle = Group.objects.create(
            code="CBS01",
            district=self.district,
            invitation_code="1234567890",
            group_type=1,
        )

    def test_system_message_serializes_with_system_identity(self):
        message = CircleBackNForth.objects.create(
            circle=self.circle,
            sender=None,
            message="Betty became F-Del, replacing Alice.",
            is_system=True,
        )

        data = CircleBackNForthSerializer(message).data

        self.assertIsNone(data["sender"])
        self.assertTrue(data["is_system"])
