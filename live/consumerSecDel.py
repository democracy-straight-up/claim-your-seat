import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from api import models as apiModels
from api import sec_del_ser, serializers
from api.models import generate_unique_invitation_key


class SecDelConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.sec_del_name = self.scope['url_route']['kwargs']['sec_del_name']
        self.user_name = self.scope['url_route']['kwargs']['user_name']
        self.room_name =  self.sec_del_name

        # Join room group
        await self.channel_layer.group_add(self.room_name, self.channel_name)

        # Fetch existing circle members using database_sync_to_async
        members = {'status':"success",  "action":"init",
                   'member_list': await self.get_members(),
                   'vote_ins': await self.get_vote_ins(),}

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

    @database_sync_to_async
    def get_vote_ins(self):
        instances = apiModels.VoteInSecDelMember.objects.filter(sec_del__code=self.sec_del_name)
        serialize = sec_del_ser.VoteInSecDelMemberSerializer(instances, many=True)
        return serialize.data
        
    @database_sync_to_async
    def get_f_link(self):
        f_link = apiModels.SecDelModel.objects.filter(code = self.sec_del_name).first()
        obj = sec_del_ser.SecDelSerializer(f_link)
        return obj.data
    
    
    @staticmethod
    @database_sync_to_async
    def voteOut(payload):  
        SecDel_instance = apiModels.SecDelMembers.objects.get(pk = payload['member']) 
        user_instance = User.objects.get(username = payload['voter'])
        if SecDel_instance and user_instance:
            apiModels.VoteOutSecDelMember.objects.create(voter = user_instance, candidate=SecDel_instance)
            return {"status":"success", "message":"voted in"}
        return {"status":"error", "message":"could not vote out"}
    
    @staticmethod
    @database_sync_to_async
    def putFarward(payload):  
        SecDel_instance = apiModels.SecDelMembers.objects.get(pk = payload['member']) 
        user_instance = User.objects.get(username = payload['voter'])
        if SecDel_instance and user_instance:
            apiModels.PutFarwardSecDelMember.objects.create(voter = user_instance, candidate=SecDel_instance)
            return {"status":"success", "message":"voted"}
        return {"status":"error", "message":"could not vote"}
    

    @staticmethod
    @database_sync_to_async
    def removeCandidate(candidate):  
        apiModels.SecDelMembers.objects.get(pk = candidate).delete()
        return {"status":"success", "message":"removed"}
    
    @staticmethod
    @database_sync_to_async
    def changeInvitKey(payload):
        instance = apiModels.SecDelModel.objects.get(code = payload['f_link'])
        if instance:
            instance.invitation_key = generate_unique_invitation_key()
            instance.save()
            return {"status":"success", "f_link": instance.invitation_key}
        return {"status":"error"}

    
    @database_sync_to_async
    def voteIn(self,data):  
        try:
            voter = User.objects.get(username = data['voter'])
            candidate = apiModels.SecDelMembers.objects.get(pk = data['candidate'])
            sec_del = apiModels.SecDelModel.objects.get(code = self.sec_del_name)
            instance_tuple =  apiModels.VoteInSecDelMember.objects.update_or_create(voter=voter,sec_del=sec_del, candidate=candidate)
            serialized = sec_del_ser.VoteInSecDelMemberSerializer(instance_tuple[0])
            instance_tuple[0].candidate.save()
            vote = serializers.UserSerializer(voter)
            return {"status":"success","action":'vote_in', "message":"voted successfully.", "user":vote.data, "instance":serialized.data}
        except:
            vote = serializers.UserSerializer(voter)
            return {"status": "error","action":"vote_in", "message": "Could not vote.","user":vote.data}
    
    @staticmethod
    @database_sync_to_async
    def voteOut(payload):  
        SecDel_instance = apiModels.SecDelMembers.objects.get(pk = payload['member']) 
        user_instance = User.objects.get(username = payload['voter'])
        if SecDel_instance and user_instance:
            apiModels.VoteOutSecDelMember.objects.create(voter = user_instance, candidate=SecDel_instance)
            return {"status":"success", "message":"voted in"}
        return {"status":"error", "message":"could not vote out"}
    
    @staticmethod
    @database_sync_to_async
    def putFarward(payload):  
        SecDel_instance = apiModels.SecDelMembers.objects.get(pk = payload['member']) 
        user_instance = User.objects.get(username = payload['voter'])
        if SecDel_instance and user_instance:
            apiModels.PutFarwardSecDelMember.objects.create(voter = user_instance, candidate=SecDel_instance)
            return {"status":"success", "message":"voted"}
        return {"status":"error", "message":"could not vote"}
    

    @staticmethod
    @database_sync_to_async
    def removeCandidate(candidate):  
        apiModels.SecDelMembers.objects.get(pk = candidate).delete()
        return {"status":"success", "message":"removed"}
    
    @staticmethod
    @database_sync_to_async
    def DissolveSecDel(payload):  
        instance = apiModels.SecDelMembers.objects.get(pk = payload['member'])
        instance.sec_del.delete()
        instance.user.users.userType = 'U1D1'
        instance.user.users.save()
        return {"status":"success", "message":"removed"}

    async def receive(self, text_data):
        """ Check messages. If message is for voting in a candidate then vote the candidate. """
        data = json.loads(text_data)

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
                # vote in the candidate and return the circle members

                res = await self.voteIn(data["payload"])
                if res['status'] == 'error':
                    await self.channel_layer.group_send(self.room_name, {
                        'type': 'send_members',
                        'members_list': res,
                        }
                    )
                else:
                    await self.channel_layer.group_send(self.room_name, {
                        'type': 'send_members',
                        'members_list':{'status':"success",'action': res ,'member_list': await self.get_members()} ,
                        }
                    )
                return
            
            case 'putForward':
                payload = data['payload']
                instance = await self.putFarward(payload)
                if instance['status'] == "success":
                    await self.channel_layer.group_send(self.room_name, {
                        'type': 'send_members',
                        'members_list': {'status':"success", 'action':'member_listing', 'member_list': await self.get_members()} ,
                        }
                    )
                return
            case 'vote_out':
                payload = data['payload']
                instance = await self.voteOut(payload)
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
            
            case "invitationKey":
                obj = await self.changeInvitKey(data['payload'])
                if obj['status'] == 'success':
                    await self.channel_layer.group_send(self.room_name, {
                        'type': 'send_members',
                        'members_list': {'status':"success", 'action':'invite_key', 'f_link': await self.get_f_link()} ,
                        }
                    )
                return
           
            case "dissolve":
                # get the memeber instance and remove the member.sec_del. 
                # upon removing the sec_del, the member will be removed as well.
                obj = await self.DissolveSecDel(data['payload'])
                if obj['status'] == 'success':
                    await self.channel_layer.group_send(self.room_name, {
                        'type': 'send_members',
                        'members_list': {'status':"success", 'action':'dissolve'}
                        }
                    )
                return

    # Send to each member
    async def send_members(self, event):
        # Send message to WebSocket
        await self.send(text_data=json.dumps(event['members_list']))
