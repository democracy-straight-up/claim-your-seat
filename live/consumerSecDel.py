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
        members = {'status':"success",'message':'listed all', "action":"init",
                   'member_list': await self.get_members(),
                   'vote_outs': await self.get_vote_outs(),
                   'vote_ins': await self.get_vote_ins(),
                   'put_forwards': await self.get_put_forwards()}
        

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
    def get_vote_outs(self):
        instances = apiModels.VoteOutSecDelMember.objects.filter(sec_del__code=self.sec_del_name)
        serialize = sec_del_ser.VoteInSecDelMemberSerializer(instances, many=True)
        return serialize.data
    
    @database_sync_to_async
    def get_put_forwards(self):
        instances = apiModels.PutFarwardSecDelMember.objects.filter(sec_del__code=self.sec_del_name)
        serialize = sec_del_ser.PutFarwardSecDelMemberSerializer(instances, many=True)
        return serialize.data
    
    @database_sync_to_async
    def get_f_link(self):
        f_link = apiModels.SecDelModel.objects.filter(code = self.sec_del_name).first()
        obj = sec_del_ser.SecDelSerializer(f_link)
        return obj.data
    
    
    @database_sync_to_async
    def member_vote_out(self, data):
        """ Vote for member out. If the majority of the members agree on removing this member,
        she/he shall be removed.
        """
        try:
            voter = User.objects.get(username = data['voter'])
            member =  apiModels.SecDelMembers.objects.get(pk = data['member'])
            sec_del = apiModels.SecDelModel.objects.get(code=self.sec_del_name)
            instance = apiModels.VoteOutSecDelMember.objects.update_or_create(voter=voter, candidate=member, sec_del=sec_del)
            serialized = sec_del_ser.VoteOutSecDelMemberSerializer(instance[0])
            vote = serializers.UserSerializer(voter)
            return {"status":"success","action":'vote_out', "message":"voted out successfully.", "user":vote.data, "instance":serialized.data}
        except:
            vote = serializers.UserSerializer(voter)
            return {"status": "error","action":"vote_out", "message": "Could not vote out.","user":vote.data}
        
    @database_sync_to_async
    def undo_vote_out(self, data):
        """removing the vote of the member (undoing the voting out)"""
        try:
            voter = User.objects.get(username = data['voter'])
            member = apiModels.SecDelMembers.objects.get(pk = data['member'])
            instance = apiModels.VoteOutSecDelMember.objects.get(voter=voter, candidate=member)
            instance.delete()
            serialized = sec_del_ser.VoteOutSecDelMemberSerializer(instance)
            vote = serializers.UserSerializer(voter)
            return {"status":"success","action":'undo_vote_out', "message":"vote removed successfully.", "user":vote.data, "instance":serialized.data}
        except:
            vote = serializers.UserSerializer(voter)
            return {"status": "error","action":"undo_vote_out", "message": "Could not remove vote.","user":vote.data}

    @database_sync_to_async
    def put_forward(self, data):
        """ change the circle gelegation."""
        try:
            voter = User.objects.get(username = data['voter'])
            member = apiModels.SecDelMembers.objects.get(pk = data['member'])
            sec_del = apiModels.SecDelModel.objects.get(code=self.sec_del_name)
            instance = apiModels.PutFarwardSecDelMember.objects.update_or_create(voter = voter,candidate = member, sec_del = sec_del)
            serialized = sec_del_ser.PutFarwardSecDelMemberSerializer(instance[0])
            vote = serializers.UserSerializer(voter)
            return {"status":"success","action":'put_forward', "message":"voted for delegate.", "user":vote.data, "instance":serialized.data}
        except:
            print("somehting went wrong on puting...")
            vote = serializers.UserSerializer(voter)
            return {"status": "error","action":"put_forward", "message": "Could not vote for delegate.","user":vote.data}
        
    @database_sync_to_async
    def undo_put_forward(self, data):
        """ undo the circle delegate vote."""
        try:
            voter = User.objects.get(username = data['voter'])
            member = apiModels.SecDelMembers.objects.get(pk = data['member'])
            instance = apiModels.PutFarwardSecDelMember.objects.get(voter = voter,candidate = member)
            serialized = sec_del_ser.PutFarwardSecDelMemberSerializer(instance)
            vote = serializers.UserSerializer(voter)
            instance.delete()
            return {"status":"success","action":'undo_put_forward', "message":"removed vote for delegate.", "user":vote.data, "instance":serialized.data}
        except:
            print("something went wrong on undoing the put...")
            vote = serializers.UserSerializer(voter)
            return {"status": "error","action":"undo_put_forward", "message": "Could not remove vote for delegate.","user":vote.data}


    @database_sync_to_async
    def invitation_key(self):
        try:
            sec_del = apiModels.SecDelModel.objects.get(code=self.sec_del_name)
            sec_del.invitation_key = apiModels.generate_unique_invitation_key()
            sec_del.save()
            serialized = sec_del_ser.SecDelSerializer(sec_del)
            return {"status":"success","action":'invitation_key', "message":"invitation key generated successfully.", "sec_del":serialized.data}
        except:
            return {"status": "error","action":"invitation_key", "message": "Could note generate invitation key."}
    
    @database_sync_to_async
    def voteIn(self,data):  
        try:
            voter = User.objects.get(username = data['voter'])
            candidate = apiModels.SecDelMembers.objects.get(pk = data['candidate'])
            sec_del = apiModels.SecDelModel.objects.get(code = self.sec_del_name)
            instance_tuple =  apiModels.VoteInSecDelMember.objects.update_or_create(voter=voter,sec_del=sec_del, candidate=candidate)
            serialized = sec_del_ser.VoteInSecDelMemberSerializer(instance_tuple[0])
            vote = serializers.UserSerializer(voter)
            return {"status":"success","action":'vote_in', "message":"voted successfully.", "user":vote.data, "instance":serialized.data}
        except:
            vote = serializers.UserSerializer(voter)
            return {"status": "error","action":"vote_in", "message": "Could not vote.","user":vote.data}
    
    

    @database_sync_to_async
    def remove_candidate(self, data):
        """ remove the candidate or members from this circle
        removing candidate... {'action': 'remove_candidate', 'payload': {'remover': 'I3H5N', 'candidate': 60}}
        removing candidate    {'action': 'remove_candidate', 'remover': 'I3H5N', 'candidate': 63}

        """
        try:
            remover = User.objects.get(username = data['payload']['remover'])
            member = apiModels.SecDelMembers.objects.get(pk = data['payload']['candidate'])
            member.delete()
            # remove the circlemember
            vote = serializers.UserSerializer(remover)
            return {"status":"success","action":'remove_candidate', "message":"removed successfully.", "user":vote.data}
        except:
            # vote = serializers.UserSerializer(remover)
            return {"status": "error","action":"remove_candidate", "message": "Could note remove candidate.","user":""}

    @staticmethod
    @database_sync_to_async
    def DissolveSecDel(payload):  
        instance = apiModels.SecDelMembers.objects.get(pk = payload['member'])
        instance.sec_del.delete()
        # instance.user.users.userType = 'U1D1'
        # instance.user.users.save()
        return {"status":"success", "message":"removed"}

    async def receive(self, text_data):
        """ Check messages. If message is for voting in a candidate then vote the candidate. """
        data = json.loads(text_data)

        match data["action"]:
            case 'remove_candidate':
                # remove the candidate or member and return the circle members
                res = await self.remove_candidate(data)
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
            
            case "putForward":
                res = await self.put_forward(data["payload"])
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
            
            case "undo_putForward":
                res = await self.undo_put_forward(data["payload"])
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
            
            case "vote_out":
                 # vote in the candidate and return the circle members
                res = await self.member_vote_out(data["payload"])
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
            
            case "undo_vote_out":
                 # vote in the candidate and return the circle members
                res = await self.undo_vote_out(data["payload"])
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

            case "join":
                await self.channel_layer.group_send(self.room_name, {
                    'type': 'send_members',
                    'members_list':{'status':"success", 'action':'member_listing', 'member_list': await self.get_members()} ,
                    }
                )
                return
            
            case "invitationKey":
                sd = await self.invitation_key()
                await self.channel_layer.group_send(self.room_name, {
                        'type': 'send_members',
                        'members_list': {"status": "success","action":'invitationKey', "sec_del":sd['sec_del'], 'member_list': await self.get_members()}
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
