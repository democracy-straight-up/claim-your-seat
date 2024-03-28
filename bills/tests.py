from rest_framework.test import APITestCase
from .views import BillViewSet, BillVoteViewSet
from .models import Bill, BillVote
from bills import billConsumer
from rest_framework import status
from django.test import TransactionTestCase
from django.contrib.auth.models import User
import json



class BillViewTestCase(APITestCase):

    def setUp(self):
        self.url = '/bill/bills/'
        # self.bill = Bill.objects.last()
        # self.bill.id = None
        # self.bill.number = "9999"
        # self.bill.title = "test"
        # self.bill.save()

    def authenticate(self):
        response = self.client.post(
            '/api/register/',
            {
                "username":"test",
                "password":"A123123a",
                "password2":"A123123a",
                "email":"testz@app.com",
                "district":"NY01",
                "legalName":"test",
                "address":"test"
            },
        )

        # response = self.client.post('/api/token/',{
        #     "username":"test",
        #     "password":"A123123a",
        # })
        print(response)

        token = response.data['access']
        print("\n")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


    def test_add_bill(self):

        self.authenticate()

        sample_bill = {
            "congress":
                118
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
            "advice":
                "This field is required."
        }
        response = self.client.post(self.url,json.dumps(sample_bill),content_type="application/json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["title"], sample_bill["title"])


    def test_update_bill(self):
        self.authenticate()
        billobj = Bill.objects.last()
        pk = billobj.id
        print(pk)
        update_data = {
            "number":"9998"
        }
        update_url = self.url+f'{pk}/'
        response = self.client.patch(update_url,json.dumps(update_data),content_type="application/json")

        self.assertNotEqual(response.data["number"],"9999")


    def test_delete_bill(self):
        self.authenticate()
        billobj = Bill.objects.last()
        pk = billobj.id
        print(pk)
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
