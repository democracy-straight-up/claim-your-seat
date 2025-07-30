import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from rep import models 
from rep import serializers


class DistrictCouncilConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.district_council_name = self.scope['url_route']['kwargs']['district_council_name']
        self.user_name = self.scope['url_route']['kwargs']['user_name']
        self.room_name =  self.district_council_name

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
        memberslist = models.DistrictCouncilMembers.objects.filter(district_council__code = self.district_council_name)
        members = serializers.DistrictCouncilMembersSerializer(memberslist, many=True)
        return members.data

    @database_sync_to_async
    def get_vote_ins(self):
        instances = models.VoteInDistrictCouncilMember.objects.filter(district_council__code=self.district_council_name)
        serialize = serializers.VoteInDistrictCouncilMemberSerializer(instances, many=True)
        return serialize.data
    
    @database_sync_to_async
    def get_vote_outs(self):
        instances = models.VoteOutDistrictCouncilMember.objects.filter(district_council__code=self.district_council_name)
        serialize = serializers.VoteOutDistrictCouncilMemberSerializer(instances, many=True)
        return serialize.data
    
    @database_sync_to_async
    def get_put_forwards(self):
        instances = models.PutForwardDistrictCouncilMember.objects.filter(district_council__code=self.district_council_name)
        serialize = serializers.PutForwardDistrictCouncilMemberSerializer(instances, many=True)
        return serialize.data
    
    @database_sync_to_async
    def member_vote_out(self, data):
        """ Vote for member out. If the majority of the members agree on removing this member,
        she/he shall be removed.
        """
        try:
            voter = User.objects.get(username = data['voter'])
            member =  models.DistrictCouncilMembers.objects.get(pk = data['member'])
            rep = models.DistrictCouncil.objects.get(code=self.district_council_name)
            instance = models.VoteOutDistrictCouncilMember.objects.update_or_create(voter=voter, candidate=member, district_council=rep)
            serialized = serializers.VoteOutDistrictCouncilMemberSerializer(instance[0])
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
            member = models.DistrictCouncilMembers.objects.get(pk = data['member'])
            instance = models.VoteOutDistrictCouncilMember.objects.get(voter=voter, candidate=member)
            instance.delete()
            serialized = serializers.VoteOutDistrictCouncilMemberSerializer(instance)
            vote = serializers.UserSerializer(voter)
            return {"status":"success","action":'undo_vote_out', "message":"vote removed successfully.", "user":vote.data, "instance":serialized.data}
        except:
            vote = serializers.UserSerializer(voter)
            return {"status": "error","action":"undo_vote_out", "message": "Could not remove vote.","user":vote.data}

    @database_sync_to_async
    def put_forward(self, data):
        """ change the district council delegation."""
        try:
            voter = User.objects.get(username = data['voter'])
            member = models.DistrictCouncilMembers.objects.get(pk = data['member'])
            rep = models.DistrictCouncil.objects.get(code=self.district_council_name)
            instance = models.PutForwardDistrictCouncilMember.objects.update_or_create(voter = voter,candidate = member, district_council = rep)
            serialized = serializers.PutForwardDistrictCouncilMemberSerializer(instance[0])
            vote = serializers.UserSerializer(voter)
            return {"status":"success","action":'put_forward', "message":"voted for delegate.", "user":vote.data, "instance":serialized.data}
        except:
            vote = serializers.UserSerializer(voter)
            return {"status": "error","action":"put_forward", "message": "Could not vote for delegate.","user":vote.data}
        
    @database_sync_to_async
    def undo_put_forward(self, data):
        """ undo the district council delegate vote."""
        try:
            voter = User.objects.get(username = data['voter'])
            member = models.DistrictCouncilMembers.objects.get(pk = data['member'])
            instance = models.PutForwardDistrictCouncilMember.objects.get(voter = voter,candidate = member)
            serialized = serializers.PutForwardDistrictCouncilMemberSerializer(instance)
            vote = serializers.UserSerializer(voter)
            instance.delete()
            return {"status":"success","action":'undo_put_forward', "message":"removed vote for delegate.", "user":vote.data, "instance":serialized.data}
        except:
            vote = serializers.UserSerializer(voter)
            return {"status": "error","action":"undo_put_forward", "message": "Could not remove vote for delegate.","user":vote.data}


    @database_sync_to_async
    def invitation_key(self):
        try:
            rep = models.DistrictCouncil.objects.get(code=self.district_council_name)
            rep.invitation_key = models.generate_unique_invitation_key()
            rep.save()
            serialized = serializers.DistrictCouncilSerializer(rep)
            return {"status":"success","action":'invitation_key', "message":"invitation key generated successfully.", "district_council":serialized.data}
        except:
            return {"status": "error","action":"invitation_key", "message": "Could not generate invitation key."}
    
    @database_sync_to_async
    def voteIn(self,data):  
        try:
            voter = User.objects.get(username = data['voter'])
            candidate = models.DistrictCouncilMembers.objects.get(pk = data['candidate'])
            rep = models.DistrictCouncil.objects.get(code = self.district_council_name)
            instance_tuple =  models.VoteInDistrictCouncilMember.objects.update_or_create(voter=voter,district_council=rep, candidate=candidate)
            serialized = serializers.VoteInDistrictCouncilMemberSerializer(instance_tuple[0])
            vote = serializers.UserSerializer(voter)
            return {"status":"success","action":'vote_in', "message":"voted successfully.", "user":vote.data, "instance":serialized.data}
        except:
            vote = serializers.UserSerializer(voter)
            return {"status": "error","action":"vote_in", "message": "Could not vote.","user":vote.data}
    
    

    @database_sync_to_async
    def remove_candidate(self, data):
        """ remove the candidate or members from this district council """
        try:
            remover = User.objects.get(username = data['remover'])
            member = models.DistrictCouncilMembers.objects.get(pk = data['candidate'])
            member.user.users.userType = 'U4D4'
            member.user.users.save()
            member.delete()
            vote = serializers.UserSerializer(remover)
            return {"status":"success","action":'remove_candidate', "message":"removed successfully.", "user":vote.data}
        except:
            # vote = serializers.UserSerializer(remover)
            return {"status": "error","action":"remove_candidate", "message": "Could not remove candidate.","user":""}

    @staticmethod
    @database_sync_to_async
    def DissolveDistrictCouncil(payload):  
        instance = models.DistrictCouncilMembers.objects.get(pk = payload['member'])
        instance.district_council.delete()
        instance.user.users.userType = 'U4D4'
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
                        'members_list': {"status": "success","action":'invitationKey', "district_council":ik['district_council'], 'member_list': await self.get_members()}
                        }
                    )
                return
           
            case "dissolve":
                # get the memeber instance and remove the member.holc. 
                # upon removing the holc, the member will be removed as well.
                obj = await self.DissolveDistrictCouncil(data['payload'])
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
