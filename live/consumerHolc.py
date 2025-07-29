import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from holc import models 
from holc import serializers


class HolcConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.holc_name = self.scope['url_route']['kwargs']['holc_name']
        self.user_name = self.scope['url_route']['kwargs']['user_name']
        self.room_name =  self.holc_name

        # Join room group
        await self.channel_layer.group_add(self.room_name, self.channel_name)

        # Fetch existing holc members using database_sync_to_async
        members = {'status':"success",'message':'listed all', "action":"init",
                   'member_list': await self.get_members(),
                   'vote_outs': await self.get_vote_outs(),
                   'vote_ins': await self.get_vote_ins(),
                   'put_forwards': await self.get_put_forwards()}
        
        # Accept the WebSocket connection
        await self.accept()

        # Send initial holc members to the connected client
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
        memberslist = models.HolcMembers.objects.filter(holc__code = self.holc_name)
        members = serializers.HolcMembersSerializer(memberslist, many=True)
        return members.data

    @database_sync_to_async
    def get_vote_ins(self):
        instances = models.VoteInHolcMember.objects.filter(holc__code=self.holc_name)
        serialize = serializers.VoteInHolcMemberSerializer(instances, many=True)
        return serialize.data
    
    @database_sync_to_async
    def get_vote_outs(self):
        instances = models.VoteOutHolcMember.objects.filter(holc__code=self.holc_name)
        serialize = serializers.VoteOutHolcMemberSerializer(instances, many=True)
        return serialize.data
    
    @database_sync_to_async
    def get_put_forwards(self):
        instances = models.PutForwardHolcMember.objects.filter(holc__code=self.holc_name)
        serialize = serializers.PutForwardHolcMemberSerializer(instances, many=True)
        return serialize.data
    
    @database_sync_to_async
    def member_vote_out(self, data):
        """ Vote for member out. If the majority of the members agree on removing this member,
        she/he shall be removed.
        """
        try:
            voter = User.objects.get(username = data['voter'])
            member =  models.HolcMembers.objects.get(pk = data['member'])
            holc = models.HolcModel.objects.get(code=self.holc_name)
            instance = models.VoteOutHolcMember.objects.update_or_create(voter=voter, candidate=member, holc=holc)
            serialized = serializers.VoteOutHolcMemberSerializer(instance[0])
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
            member = models.HolcMembers.objects.get(pk = data['member'])
            instance = models.VoteOutHolcMember.objects.get(voter=voter, candidate=member)
            instance.delete()
            serialized = serializers.VoteOutHolcMemberSerializer(instance)
            vote = serializers.UserSerializer(voter)
            return {"status":"success","action":'undo_vote_out', "message":"vote removed successfully.", "user":vote.data, "instance":serialized.data}
        except:
            vote = serializers.UserSerializer(voter)
            return {"status": "error","action":"undo_vote_out", "message": "Could not remove vote.","user":vote.data}

    @database_sync_to_async
    def put_forward(self, data):
        """ change the holc delegation."""
        try:
            voter = User.objects.get(username = data['voter'])
            member = models.HolcMembers.objects.get(pk = data['member'])
            holc = models.HolcModel.objects.get(code=self.holc_name)
            instance = models.PutForwardHolcMember.objects.update_or_create(voter = voter,candidate = member, holc = holc)
            serialized = serializers.PutForwardHolcMemberSerializer(instance[0])
            vote = serializers.UserSerializer(voter)
            return {"status":"success","action":'put_forward', "message":"voted for delegate.", "user":vote.data, "instance":serialized.data}
        except:
            vote = serializers.UserSerializer(voter)
            return {"status": "error","action":"put_forward", "message": "Could not vote for delegate.","user":vote.data}
        
    @database_sync_to_async
    def undo_put_forward(self, data):
        """ undo the holc delegate vote."""
        try:
            voter = User.objects.get(username = data['voter'])
            member = models.HolcMembers.objects.get(pk = data['member'])
            instance = models.PutForwardHolcMember.objects.get(voter = voter,candidate = member)
            serialized = serializers.PutForwardHolcMemberSerializer(instance)
            vote = serializers.UserSerializer(voter)
            instance.delete()
            return {"status":"success","action":'undo_put_forward', "message":"removed vote for delegate.", "user":vote.data, "instance":serialized.data}
        except:
            vote = serializers.UserSerializer(voter)
            return {"status": "error","action":"undo_put_forward", "message": "Could not remove vote for delegate.","user":vote.data}


    @database_sync_to_async
    def invitation_key(self):
        try:
            holc = models.HolcModel.objects.get(code=self.holc_name)
            holc.invitation_key = models.generate_unique_invitation_key()
            holc.save()
            serialized = serializers.HolcSerializer(holc)
            return {"status":"success","action":'invitation_key', "message":"invitation key generated successfully.", "holc":serialized.data}
        except:
            return {"status": "error","action":"invitation_key", "message": "Could not generate invitation key."}
    
    @database_sync_to_async
    def voteIn(self,data):  
        try:
            voter = User.objects.get(username = data['voter'])
            candidate = models.HolcMembers.objects.get(pk = data['candidate'])
            holc = models.HolcModel.objects.get(code = self.holc_name)
            instance_tuple =  models.VoteInHolcMember.objects.update_or_create(voter=voter,holc=holc, candidate=candidate)
            serialized = serializers.VoteInHolcMemberSerializer(instance_tuple[0])
            vote = serializers.UserSerializer(voter)
            return {"status":"success","action":'vote_in', "message":"voted successfully.", "user":vote.data, "instance":serialized.data}
        except:
            vote = serializers.UserSerializer(voter)
            return {"status": "error","action":"vote_in", "message": "Could not vote.","user":vote.data}
    
    

    @database_sync_to_async
    def remove_candidate(self, data):
        """ remove the candidate or members from this holc """
        try:
            remover = User.objects.get(username = data['remover'])
            member = models.HolcMembers.objects.get(pk = data['candidate'])
            member.user.users.userType = 'U3D3'
            member.user.users.save()
            member.delete()
            vote = serializers.UserSerializer(remover)
            return {"status":"success","action":'remove_candidate', "message":"removed successfully.", "user":vote.data}
        except:
            # vote = serializers.UserSerializer(remover)
            return {"status": "error","action":"remove_candidate", "message": "Could not remove candidate.","user":""}

    @staticmethod
    @database_sync_to_async
    def DissolveHolc(payload):  
        instance = models.HolcMembers.objects.get(pk = payload['member'])
        instance.holc.delete()
        instance.user.users.userType = 'U3D3'
        instance.user.users.save()
        return {"status":"success", "message":"removed"}

    async def receive(self, text_data):
        """ Check messages. If message is for voting in a candidate then vote the candidate. """
        data = json.loads(text_data)

        match data["action"]:
            case 'remove_candidate':
                # remove the candidate or member and return the holc members
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
                # vote in the candidate and return the holc members
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
                 # vote in the candidate and return the holc members
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
                 # vote in the candidate and return the holc members
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
                ik = await self.invitation_key()
                await self.channel_layer.group_send(self.room_name, {
                        'type': 'send_members',
                        'members_list': {"status": "success","action":'invitationKey', "holc":ik['holc'], 'member_list': await self.get_members()}
                        }
                    )
                return
           
            case "dissolve":
                # get the memeber instance and remove the member.holc. 
                # upon removing the holc, the member will be removed as well.
                obj = await self.DissolveHolc(data['payload'])
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
