import datetime
from django.test import TestCase, Client
from .models import TestingModel
import datetime
from django.utils import timezone

class TestingModelModelTest(TestCase):
    def setUp(self):
      self.t = TestingModel.objects.create(
        name='Taylor Swift',
        email='erastour@gmail.com',
        is_test=True,
        tagline='I am a singer',
        schedule_date=datetime.date(2019, 1, 1)  # Fix: Use datetime.date instead of datetime.datetime
      )
      global c
      c = Client()

    def test_testing_model_model_exists(self):
      testers = TestingModel.objects.count()

      self.assertEqual(testers, 1)

    def test_user_model_has_attributes(self):
        self.assertEqual(self.t.name, 'Taylor Swift')
        self.assertEqual(self.t.email, 'erastour@gmail.com')
        self.assertEqual(self.t.status, 0)
        self.assertEqual(self.t.is_test, True)
        self.assertEqual(self.t.tagline, 'I am a singer')
        self.assertEqual(self.t.schedule_date, datetime.date(2019, 1, 1))