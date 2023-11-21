import json
from channels.generic.websocket import AsyncWebsocketConsumer
from .models import Bill, BillVote, Advice
from asgiref.sync import sync_to_async 
from channels.db import database_sync_to_async 
from django.contrib.auth.models import User
from vote import models as voteModels
from api import serializers as apiSerializers
from .serializers import AdviceSerializer

class BillConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.bill_id = self.scope['url_route']['kwargs']['bill_id']
        self.room_group_name = f'bill_{self.bill_id}'

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        # Fetch existing votes for the bill using database_sync_to_async
        bill_votes = await self.get_bill_votes()
        
        # Accept the WebSocket connection
        await self.accept()

        # Send initial vote counts to the connected client
        await self.send(text_data=json.dumps(bill_votes))


    @database_sync_to_async
    def get_bill_votes(self,district_code=None):
        try:
            bill = Bill.objects.get(number=self.bill_id)
        except Bill.DoesNotExist:
            return {
                'yea_votes': 0,
                'nay_votes': 0,
                'present_votes': 0,
                'proxy_votes': 0,
            }
        
        if district_code:
            return {
                'yea_votes': bill.count_yea_votes(),
                'nay_votes': bill.count_nay_votes(),
                'present_votes': bill.count_present_votes(),
                'proxy_votes': bill.count_proxy_votes(),
                'district_yea_vote': bill.count_district_yea_votes(district_code),
                'district_nay_vote': bill.count_district_nay_votes(district_code),
                'district_present_vote': bill.count_district_present_votes(district_code),
                'district_proxy_vote': bill.count_district_proxy_votes(district_code),
            }
        else:
            return {
                'yea_votes': bill.count_yea_votes(),
                'nay_votes': bill.count_nay_votes(),
                'present_votes': bill.count_present_votes(),
                'proxy_votes': bill.count_proxy_votes(),
            }


    @database_sync_to_async
    def get_existing_vote(self, bill, username):
        obj = BillVote.objects.filter(bill=bill, voter__username=username).first()
        return obj

    @database_sync_to_async
    def update_existing_vote(self, existing_vote, vote_type):
        existing_vote.your_vote = vote_type
        existing_vote.save()

    @database_sync_to_async
    def create_new_vote(self, bill, user, vote_type):
        ob = BillVote.objects.create(bill=bill, voter=user, your_vote=vote_type)
        ob.save()
    
    @database_sync_to_async
    def get_user_instance(self, username):
        try:
            u_obj = User.objects.get(username = username)
            district_code = u_obj.users.district
            return u_obj, district_code
        except User.DoesNotExist:
            return None, None
        
    async def receive(self, text_data):
        data = json.loads(text_data)
        vote_type = data['vote_type']
        username = data['username']

        # Fetch existing votes for the bill using database_sync_to_async
        try:
            bill = await database_sync_to_async(Bill.objects.get)(number=self.bill_id)
        except Bill.DoesNotExist:
            return

        # get user instance 
        u, district_code = await self.get_user_instance(username)
        # Check if the user has already voted for this bill
        existing_vote = await self.get_existing_vote(bill, username)

        if existing_vote:
            # Update the existing vote using database_sync_to_async
            await self.update_existing_vote(existing_vote, vote_type)
        else:
            # Create a new vote using database_sync_to_async
            await self.create_new_vote(bill, u, vote_type)

        # Fetch updated votes for the bill using database_sync_to_async
        updated_bill_votes = await self.get_bill_votes(district_code)
        # Send updated vote counts to the room group

        await self.channel_layer.group_send(self.room_group_name, {
                'type': 'update_vote_counts',
                'votes': updated_bill_votes,
            }
        )

    # Send to each member
    async def update_vote_counts(self, event):
        # Send message to WebSocket
        await self.send(text_data=json.dumps(event['votes']))
    


class AdviceConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.bill_id = self.scope['url_route']['kwargs']['bill_id']
        self.podName = self.scope['url_route']['kwargs']['podName']
        self.room_group_name = f'bill_{self.bill_id}_pod_{self.podName}'

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        advice = await self.get_advice()
        # Accept the WebSocket connection
        await self.accept()

        # Send initial advice to the connected client
        await self.send(text_data=json.dumps(advice))


    @database_sync_to_async
    def get_advice(self):
        pod = voteModels.Pod.objects.get(code = self.podName)
        if pod:
            data = AdviceSerializer(Advice.objects.filter(
                bill__number=self.bill_id, pod__code=self.podName),many=True,fields=('username','advice')
            ).data

            return list(data)
        return 0

    @database_sync_to_async
    def get_existing_advice(self, bill, username):
        obj = Advice.objects.filter(bill=bill, voter__username=username).first()
        return obj

    @database_sync_to_async
    def update_existing_advice(self, existing_advice, vote_type):
        existing_advice.advice = vote_type
        existing_advice.save()

    @database_sync_to_async
    def create_new_advice(self, pod, bill, user, vote_type):
        ob = Advice.objects.create(pod=pod,bill=bill, voter=user, advice=vote_type)
        ob.save()
    
    @database_sync_to_async
    def get_user_instance(self, username):
        try:
            u_obj = User.objects.get(username = username)
            return u_obj
        except User.DoesNotExist:
            return None
    
    async def receive(self, text_data):
        data = json.loads(text_data)
        vote_type = data['advice']
        username = data['username']

        try:
            bill = await database_sync_to_async(Bill.objects.get)(number=self.bill_id)
        except Bill.DoesNotExist:
            return

        pod = await database_sync_to_async(voteModels.Pod.objects.get)(code = self.podName)
  
        # get user instance 
        u = await self.get_user_instance(username)
        # Check if the user already has advice
        existing_advice = await self.get_existing_advice(bill, username)

        if existing_advice:
            # Update the existing advice using database_sync_to_async
            await self.update_existing_advice(existing_advice, vote_type)
        else:
            # Create a new advice using database_sync_to_async
            await self.create_new_advice(pod, bill, u, vote_type)

        updated_bill_advice = await self.get_advice()
        # Send updated advices to the room group

        await self.channel_layer.group_send(self.room_group_name, {
                'type': 'update_advice',
                'advice': updated_bill_advice,
            }
        )

    # Send to each member
    async def update_advice(self, event):
        # Send message to WebSocket
        await self.send(text_data=json.dumps(event['advice']))
    