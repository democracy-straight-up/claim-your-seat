from rest_framework.test import APITestCase
from .views import BillViewSet, BillVoteViewSet
from .models import Bill, BillVote
from bills import billConsumer
from rest_framework import status
from rest_framework.response import Response   # added by siva
from django.test import TransactionTestCase
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
import json



class BillViewTestCase(APITestCase):

    def setUp(self):
        from django.core.management import call_command
        call_command('loaddata', 'districts_data.json')
        # call_command('loaddata', 'dummy_users_data.json')

        self.url = '/bill/bills/'
        # self.bill = Bill.objects.last()
        # self.bill.id = 1
        # self.bill.number = "9999"
        # self.bill.title = "test"
        # self.bill.save()

    def authenticate(self):

        response = self.client.post(
            '/api/register/',
            {
                "username": "test",
                "password": "muWMpROTX..",
                "password2": "muWMpROTX..",
                "email": "test1@gmail.com",
                "district": "NY01",
                "legalName": "test",
                "is_reg": "true",
                "is_reg1": "true",
                "address": "test"
            }
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        token_response = self.client.post('/api/token/',{
            "username": response.data['username'],
            "password": "muWMpROTX..",
        }, format='json')
        # self.assertEqual(token_response.data, status.HTTP_200_OK, token_response.content)
        self.assertFalse('token' in token_response.data, token_response.content)
        token = token_response.data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


    def test_add_bill(self, **kwagrs):

        self.authenticate()

        self.sample_bill = {
            "congress":
                "118"
            ,
            "number":
                "9999"
            ,
            "origin_chamber":
                "House"
            ,
            "origin_chamber_code":
                "H"
            ,
            "title":
                "test"
            ,
            "bill_type":
                "test"
            ,
            "url":
                "https://api.congress.gov/v3/bill/118/hr/6127?format=json"
            ,
            "latest_action_date":
                "2023-11-01"
            ,
            "latest_action_text":
                "test"
            ,
            "text":
                "This field is required."
            ,
            "voting_start":
                "2023-11-01"
            ,
            "voting_close":
                "2023-11-01"
            ,
            "schedule_date":
                "2023-11-01"

            # "advice":
            #     "This field is required."
        }

        response = self.client.post(self.url,json.dumps(self.sample_bill),content_type="application/json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["title"], self.sample_bill["title"])


    def test_update_bill(self, **kwagrs):
        self.authenticate()
        Bill.objects.create(id="1")
        billobj = Bill.objects.latest()
        pk = billobj.id
        update_data = {
            "number":"9998"
        }
        update_url = self.url+f'{pk}/'
        response = self.client.patch(update_url,json.dumps(update_data),content_type="application/json")

        self.assertNotEqual(response.data["number"],"9999")


    def test_delete_bill(self):
        self.authenticate()
        Bill.objects.create(id="1")
        billobj = Bill.objects.last()
        pk = billobj.id
        delete_url = self.url+f'{pk}/'
        self.client.delete(delete_url)
        self.assertFalse(Bill.objects.filter(id=pk).exists())


# class BillVoteTestCase(APITestCase):

#     def setUp(self):
#         self.factory = APIRequestFactory()
#         self.view = BillVoteViewSet.as_view()
#         self.url = '/bill/bill-vote/'
#         # self.bill = Bill.objects.all().first()
#         # self.user = User.objects.get(username = 'K3K7N')
#         # self.vote_type = 'Y'
#         # self.obj = BillVote.objects.create(bill=self.bill, voter=self.user, your_vote=self.vote_type)
#         # self.obj.save()

#     def test_add_record(self):
#         self.authenticate()
#         voter =
#         voter_id =
#         sample_data = {
#         "bill": {
#             "id":"9",
#             "number": "6127",
#             "bill_type": "HR"
#         },
#         "voter": {
#             "id": "247",
#             "username": "V8W1B"
#         },
#         "your_vote": "Pr"
#         }


#     def test_update_record(self):
#         sample_data = {
#         "your_vote": "Y"
#         }

#     def test_delete_record(self):
#         pass
