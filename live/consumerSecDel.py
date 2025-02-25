import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

# from django.contrib.auth.models import User

from api import models as apiModels
from api import sec_del_ser

class SecDelConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.sec_del_name = self.scope['url_route']['kwargs']['sec_del_name']
        self.user_name = self.scope['url_route']['kwargs']['user_name']
        self.room_name =  self.sec_del_name

        # Join room group
        await self.channel_layer.group_add(self.room_name, self.channel_name)

        # Fetch existing circle members using database_sync_to_async
        members = {'status':"success",'action':'member_listing', 'member_list': await self.get_members()}

        # Accept the WebSocket connection
        await self.accept()

        # Send initial Circle members to the connected client
        await self.send(text_data=json.dumps(members))

    # when a member of the room leaves the room
    async def disconnect(self, close_code):
        # Remove the client from the room (channel group)
        await self.channel_layer.group_discard(self.room_name, self.channel_name)

        # Your custom disconnect logic here
        await self.send(text_data=json.dumps({"status": "disconnecting", "message": "Goodbye!"}))

        # Call the parent class disconnect method
        await super().disconnect(close_code)

    @database_sync_to_async
    def get_members(self):
        memberslist = apiModels.SecDelMembers.objects.filter(sec_del__code = self.sec_del_name)
        members = sec_del_ser.SecDelMembersSerializer(memberslist, many=True)
        return members.data

    
    @staticmethod
    @database_sync_to_async
    def voteIn(candidate):  
        member = apiModels.SecDelMembers.objects.get(pk = candidate)
        member.vote_in_count += 1
        member.save()
        return {"status":"success", "message":"voted in"}
    
    @staticmethod
    @database_sync_to_async
    def removeCandidate(candidate):  
        apiModels.SecDelMembers.objects.get(pk = candidate).delete()
        return {"status":"success", "message":"removed"}

    async def receive(self, text_data):
        """ Check messages. If message is for voting in a candidate then vote the candidate. """
        data = json.loads(text_data)
        print("data received: ", data)
        match data["action"]:
            case 'remove_candidate':
                candidate = data['candidate']
                instance = await self.removeCandidate(candidate)
                if instance['status'] == "success":
                    await self.channel_layer.group_send(self.room_name, {
                        'type': 'send_members',
                        'members_list': {'status':"success", 'action':'member_listing', 'member_list': await self.get_members()} ,
                        }
                    )
                return
            case 'vote_in':
                candidate = data['candidate']
                instance = await self.voteIn(candidate)
                if instance['status'] == "success":
                    await self.channel_layer.group_send(self.room_name, {
                        'type': 'send_members',
                        'members_list': {'status':"success", 'action':'member_listing', 'member_list': await self.get_members()} ,
                        }
                    )
                return
            
            case "join":
                await self.channel_layer.group_send(self.room_name, {
                    'type': 'send_members',
                    'members_list':{'status':"success", 'action':'member_listing', 'member_list': await self.get_members()} ,
                    }
                )
                return
            case "dissolve":
                """ the candidate has already joint and only needs to update the Circle list to members"""
                """here do the deletion of the cirlce"""


        # if any of the functions returns error, the message being sent will be that error only to that user.
        # otherwise, the circle members will be sent back to the room

    # Send to each member
    async def send_members(self, event):
        # Send message to WebSocket
        await self.send(text_data=json.dumps(event['members_list']))
