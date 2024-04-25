import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from vote import models as voteModels
from api import serializers
from api import views as apiViews

class CircleConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.circle_name = self.scope['url_route']['kwargs']['circle_name']
        self.user_name = self.scope['url_route']['kwargs']['user_name']
        self.room_group_name = 'chat_%s' % self.circle_name
        # Join room group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        # Fetch existing circle members using database_sync_to_async
        members = {'status':"success",'message':'listed all members.', 'member_list': await self.get_members()}

        # Accept the WebSocket connection
        await self.accept()

        # Send initial Circle members to the connected client
        await self.send(text_data=json.dumps(members))

    # when a member of the room leaves the room
    async def disconnect(self, close_code):
        # Remove the client from the room (channel group)
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

        # Your custom disconnect logic here
        await self.send(text_data=json.dumps({"status": "disconnecting", "message": "Goodbye!"}))

        # Call the parent class disconnect method
        await super().disconnect(close_code)

    @database_sync_to_async
    def get_members(self):
        MemberInstances = voteModels.CircleMember.objects.filter(circle__code=self.circle_name)
        members = serializers.CircleMemberSerializer(MemberInstances, many=True)
        return members.data

    @database_sync_to_async
    def candidate_vote(self, data):
        """ Vote for candidate
        make sure to not forget about the mejority votes to make
        the candidate a member
        """
        try:
            voter = User.objects.get(username = data['voter'])
            candidate = voteModels.CircleMember.objects.get(pk = data['candidate'])
            voteModels.CircleMember_vote_in.objects.update_or_create(voter=voter, candidate=candidate)
            vote = serializers.UserSerializer(voter)
            return {"status":"success","action":'vote_in', "message":"voted successfully.", "user":vote.data}
        except:
            vote = serializers.UserSerializer(voter)
            return {"status": "error","action":"vote_in", "message": "Could not vote","user":vote.data}

    @database_sync_to_async
    def member_vote_out(self, data):
        """ Vote for member out. If the majority of the members agree on removing this member,
        she/he shall be removed.
        """
        try:
            voter = User.objects.get(username = data['voter'])
            member = voteModels.CircleMember.objects.get(pk = data['member'])
            voteModels.CircleMember_vote_out.objects.update_or_create(voter=voter, candidate=member)
            vote = serializers.UserSerializer(voter)
            return {"status":"success","action":'vote_out', "message":"voted out successfully.", "user":vote.data}
        except:
            vote = serializers.UserSerializer(voter)
            return {"status": "error","action":"vote_out", "message": "Could not vote out.","user":vote.data}

    @database_sync_to_async
    def remove_candidate(self, data):
        """ remove the candidate or members from this circle
        """
        try:
            remover = User.objects.get(username = data['remover'])
            member = voteModels.CircleMember.objects.get(pk = data['candidate'])
            # set back the userType to 0 while removing.
            member.user.users.userType = 0
            member.user.users.save()
            member.delete()
            # remove the circlemember
            vote = serializers.UserSerializer(remover)
            return {"status":"success","action":'remove_candidate', "message":"removed successfully.", "user":vote.data}
        except:
            vote = serializers.UserSerializer(remover)
            return {"status": "error","action":"vote_in", "message": "Could note remove candidate.","user":vote.data}

    @database_sync_to_async
    def put_forward(self, data):
        """ change the circle gelegation.
        """
        try:
            voter = User.objects.get(username = data['voter'])
            member = voteModels.CircleMember.objects.get(pk = data['member'])
            voteModels.CircleMember_put_forward.objects.update_or_create(voter=voter, recipient=member)
            vote = serializers.UserSerializer(voter)
            return {"status":"success","action":'put_forward', "message":"voted for gelegation.", "user":vote.data}
        except:
            vote = serializers.UserSerializer(voter)
            return {"status": "error","action":"vote_out", "message": "Could not vote for gelegation.","user":vote.data}

    @database_sync_to_async
    def dissolveCircle(self, data):
        """removing this Circle."""
        try:
            # this is the only member which is fdel as well. same as voter
            member = voteModels.CircleMember.objects.get(pk = data['member'])
            # get the circle
            if member.is_delegate and member.circle.circlemember_set.all().count() == 1:
                member.circle.delete()
                # set the userType to 0
                member.user.users.userType = 0
                member.user.users.save()
                return {"status":"success","action":'dissolve', "message":"Circle Dissolved."}
        except:
            return {"status": "error","action":"dissolve", "message": "Could not dissolve."}

    @database_sync_to_async
    def invitation_key(self):
        try:
            circle = voteModels.Circle.objects.get(code=self.circle_name)
            circle.invitation_code = apiViews.circle_invitation_generator()
            circle.save()
            serialized = serializers.CircleSerializer(circle)
            return {"status":"success","action":'invitation_key', "message":"invitation key generated successfully.", "circle":serialized.data}
        except:
            return {"status": "error","action":"invitation_key", "message": "Could note generate invitation key."}

    async def receive(self, text_data):
        """ Check messages. If message is for voting in a candidate
        then vote the candidate.
        """
        data = json.loads(text_data)

        match data["action"]:
            case "vote_in":
                # vote in the candidate and return the circle members
                res = await self.candidate_vote(data["payload"])
                if res['status'] == 'error':
                    await self.channel_layer.group_send(self.room_group_name, {
                        'type': 'send_members',
                        'members_list': res,
                        }
                    )
                else:
                    await self.channel_layer.group_send(self.room_group_name, {
                        'type': 'send_members',
                        'members_list':{'status':"success",'action': res ,'member_list': await self.get_members()} ,
                        }
                    )
                return

            case "remove_candidate":
                # remove the candidate or member and return the circle members
                removed = await self.remove_candidate(data["payload"])
                if removed['status'] == 'error':
                    await self.channel_layer.group_send(self.room_group_name, {
                        'type': 'send_members',
                        'members_list': removed,
                        }
                    )
                else:
                    await self.channel_layer.group_send(self.room_group_name, {
                        'type': 'send_members',
                        'members_list':{'status':"success",'action': removed ,'member_list': await self.get_members()} ,
                        }
                    )
                return

            case "join":
                """ the candidate is already joined and only needs to update the Circle list to members"""
                await self.channel_layer.group_send(self.room_group_name, {
                    'type': 'send_members',
                    'members_list':{'status':"success", 'member_list': await self.get_members()} ,
                    }
                )
                return

                # vote out the candidate and return the circle members

            case "vote_out":
                 # vote in the candidate and return the circle members
                res = await self.member_vote_out(data["payload"])
                if res['status'] == 'error':
                    await self.channel_layer.group_send(self.room_group_name, {
                        'type': 'send_members',
                        'members_list': res,
                        }
                    )
                else:
                    await self.channel_layer.group_send(self.room_group_name, {
                        'type': 'send_members',
                        'members_list':{'status':"success",'action': res ,'member_list': await self.get_members()} ,
                        }
                    )
                return

            case "invitationKey":
                circle = await self.invitation_key()
                await self.channel_layer.group_send(self.room_group_name, {
                        'type': 'send_members',
                        'members_list': {"status": "success","action":'invitationKey', "circle":circle['circle']}
                        }
                    )
                return

            case "putForward":
                res = await self.put_forward(data["payload"])
                if res['status'] == 'error':
                    await self.channel_layer.group_send(self.room_group_name, {
                        'type': 'send_members',
                        'members_list': res,
                        }
                    )
                else:
                    await self.channel_layer.group_send(self.room_group_name, {
                        'type': 'send_members',
                        'members_list':{'status':"success",'action': res ,'member_list': await self.get_members()} ,
                        }
                    )
                return

            case "dissolve":
                await self.channel_layer.group_send(self.room_group_name, {
                    'type': 'send_members',
                    'members_list': await self.dissolveCircle(data['payload']),
                    }
                )
                return

            case _:
                print("action not found:")
                pass


        # if any of the functions returns error, the message being sent will be that error only to that user.
        # otherwise, the circle members will be sent back to the room



    # Send to each member
    async def send_members(self, event):
        # Send message to WebSocket
        await self.send(text_data=json.dumps(event['members_list']))
