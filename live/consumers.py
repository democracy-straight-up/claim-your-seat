import json
from channels.generic.websocket import WebsocketConsumer
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from channels.exceptions import StopConsumer
from asgiref.sync import sync_to_async
from asgiref.sync import async_to_sync
from vote import models as voteModels
from api import serializers as apiSerializers
import api.views as apiView
from django.contrib.auth.models import User
from django.core.paginator import Paginator

class HouseKeepingConsumer(WebsocketConsumer):
    def connect(self):
        self.circle_name = self.scope['url_route']['kwargs']['circle_name']
        self.user_name = self.scope['url_route']['kwargs']['user_name']
        self.room_group_name = 'chat_%s' % self.circle_name
        data = {}
        try:
            circle = ''
            if self.circle_name:
                circle = voteModels.Circle.objects.get(code = self.circle_name)
            # get all the circle members.
            circleMembers = circle.circlemember_set.all()

            data = {
                "circle": apiSerializers.CircleSerializer(circle).data,
                "circleMembers": apiSerializers.CIRCLEMemberSer(circleMembers, many=True).data
            }
        except:
            print("something went wrong...")

        # Join room group
        async_to_sync(self.channel_layer.group_add)(
            self.room_group_name,
            self.channel_name
        )

        self.accept()
        self.send(text_data=json.dumps({
            'type':'circlemember',
            'data': data
        }))

    def disconnect(self, close_code):
        # Leave room group
        self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        raise StopConsumer()

    # Receive message from WebSocket
    def receive(self, text_data):
        text_data_json = json.loads(text_data)
        # Send message to room group
        async_to_sync(self.channel_layer.group_send)(
            self.room_group_name,
            {
                'type': 'chat',
                'data': switch(text_data_json)
            }
        )
     # Receive message from room group
    def chat(self, event):
        # Send message to WebSocket
        self.send(text_data=json.dumps({
            'type':event['data']['type'],
            'data': event['data']
        }))


def majorityputFarward(recipient):
    if recipient.putFarward.all().count() >= (recipient.circle.circlemember_set.all().count()/2):
        return True
    return False

def majorityVotes(candidate):
    if candidate.voteIns.all().count() > (candidate.circle.circlemember_set.filter(is_member=True).count()/2):
        return True
    return False

def majorityVotesOut(member):
    if member.voteOuts.all().count() >= (member.circle.circlemember_set.all().count()/2):
        return True
    return False

def switch(text_data_json):
    match text_data_json['type']:
        case 'circleInvitationKey':
            circle = voteModels.Circle.objects.get(code = text_data_json['circle'])
            circle.invitation_code = apiView.circle_invitation_generator()
            circle.save()
            return {'type':text_data_json['type'], 'data':apiSerializers.CircleSerializer(circle).data}
        case 'joined':
            circle = voteModels.Circle.objects.get(code = text_data_json['circle'])
            return {'type':text_data_json['type'], 'data':apiSerializers.CIRCLEMemberSer(circle.circlemember_set.all(), many=True).data}

        case 'voteIn':
            """vote a candidate in and check if the candidate has 50+1 vote to become members or circle.
            if so, return the circlemembers. else return that the vote in has been done only.
            also check if the user already voted in for him/her
            """
            # search on vote In for candidate and the user
            user = User.objects.get(username = text_data_json['voter'])
            candidate = voteModels.CircleMember.objects.get(pk = text_data_json['candidate'])
            votedIn = voteModels.CircleMember_vote_in.objects.filter(candidate = candidate, voter = user).exists()
            if votedIn:
                return {
                    'type':text_data_json['type'],
                    'done': False,
                    'voter': user.username,
                    'candidate': candidate.user.username,
                    'data':'you have already voted in for the candidate.'
                    }

            voteIN = voteModels.CircleMember_vote_in.objects.create(candidate = candidate, voter = user)
            voteIN.save()
            # check if candidate has got the majority votes
            if majorityVotes(candidate):
                candidate.is_member = True
                candidate.save()
                # set the member.user.users.userType to 1 as it becomes the member in a circle.
                userType = candidate.user
                userType.users.userType = 1
                userType.save()
                # remove all votes in for this members
                votedIn = voteModels.CircleMember_vote_in.objects.filter(candidate = candidate).delete()
                circleMembers = candidate.circle.circlemember_set.all()
                data = {
                    'circle':apiSerializers.CircleSerializer(candidate.circle).data,
                    'circlemembers':apiSerializers.CIRCLEMemberSer(circleMembers, many=True).data
                }
                return {
                    'type': text_data_json['type'],
                    'done': True,
                    'voter': user.username,
                    'candidate': candidate.user.username,
                    'is_member':candidate.is_member,
                    'data':data
                    }
            return {
                'type': text_data_json['type'],
                'done':True,
                'candidate': candidate.user.username,
                'voter':user.username,
                'data':apiSerializers.CIRCLEMemberSer(candidate.circle.circlemember_set.all(), many=True).data
                }

        case 'voteOut':
            """this is for voting out a member while the circle is active"""
            user = User.objects.get(username = text_data_json['voter'])
            member =voteModels.CircleMember.objects.get(pk = text_data_json['member'])
            # check if the voter is already in the vote out:
            votedOut = voteModels.CircleMember_vote_out.objects.filter(voter = user, candidate = member).exists()
            if votedOut:
                return {
                    'type':text_data_json['type'],
                    'done': False,
                    'voter': user.username,
                    'candidate': member.user.username,
                    'data':'you have already voted out for this member.'
                    }

            voteOut = voteModels.CircleMember_vote_out.objects.create(candidate = member, voter = user)
            voteOut.save()
            circleMembers = member.circle.circlemember_set.all()
            return {
                'type': text_data_json['type'],
                'done': True,
                'voter': user.username,
                'member': member.user.username,
                'data':apiSerializers.CIRCLEMemberSer(circleMembers, many=True).data
                }

        case 'delegate':
            """this functionality choose for delegation"""
            #  circle: the circle id coming from client
            # F_delFor: the person chosen as delegate
            # voter: the member who voted
            user = User.objects.get(username = text_data_json['voter'])
            recipient = voteModels.CircleMember.objects.get(pk = text_data_json['recipient'])
            delegated = voteModels.CircleMember_put_farward.objects.filter(voter = user, recipient = recipient).exists()
            if delegated:
                return {
                    'type':text_data_json['type'],
                    'done': False,
                    'voter': user.username,
                    'recipient': recipient.user.username,
                    'data':'you have already delegated for this member.'
                    }
            putFrwd = voteModels.CircleMember_put_farward.objects.create(recipient = recipient, voter = user)
            putFrwd.save()
            if majorityputFarward(recipient):
                # revoke the prev delegate to member
                prevDel = recipient.circle.circlemember_set.get(is_delegate = True)

                recipient.is_delegate = True
                recipient.save()

                prevDel.is_delegate = False
                prevDel.save()
                # remove all the pufarward votes of prevDel
                recipient.putFarward.all().delete()


                # here you have to update the FDel field of the circle as true
                # indicating that the circle had it's first election

                return {
                    'type': text_data_json['type'],
                    'done': True,
                    'voter': user.username,
                    'recipient': recipient.user.username,
                    'is_delegate':recipient.is_delegate,
                    'data':apiSerializers.CIRCLEMemberSer(recipient.circle.circlemember_set.all(), many=True).data
                    }

            return {
                'type': text_data_json['type'],
                'done': True,
                'voter': user.username,
                'recipient': recipient.user.username,
                'is_delegate':recipient.is_delegate,
                'data':apiSerializers.CIRCLEMemberSer(recipient.circle.circlemember_set.all(), many=True).data
                }

        case 'desolveCircle':
            """check if the circle has one member only and he/she is delegate.
            in case of removing, return circle removed done else return not aligible to remove """
            circle = voteModels.Circle.objects.get(code = text_data_json['circle'])
            user = User.objects.get(username = text_data_json['user'])
            # check if the circle has only one member.
            if circle.circlemember_set.all().count() <=1:
                member = circle.circlemember_set.all()[0]
                if member.user == user and member.is_delegate:
                    circle.delete()
                    user.users.userType = 0
                    user.save()
                    return {'type': text_data_json['type'],'done':True, 'data':"removed the circle"}

            return {'type': text_data_json['type'],'done':False, 'data':"unable to remove"}

        case 'removemember':
            """ this case removes the candidate or member"""
            circle = voteModels.Circle.objects.get(code = text_data_json['circle'])
            member = voteModels.CircleMember.objects.get(pk = text_data_json['member'])
            member.delete()
            # set the userType back to zero
            member.user.users.userType = 0
            member.user.users.save()
            data = {
                "circle": apiSerializers.CircleSerializer(circle).data,
                "circleMembers": apiSerializers.CIRCLEMemberSer(circle.circlemember_set.all(), many=True).data
            }
            return {
                'type':text_data_json['type'],
                'done': member.user.username,
                'data':data
                }

        case default:
            return {'type': 'notype', 'data':'no action to preferm'}

class CircleBackNForth(AsyncWebsocketConsumer):
    async def connect(self):
        # get circle and username
        self.circleName = self.scope['url_route']['kwargs']['circleName']
        self.userName = self.scope['url_route']['kwargs']['userName']

        # create room with circlename
        self.room_group_name = self.circleName
        self.username = self.userName
        self.request = self.scope.get('request')
        self.pageNum = 1
        self.paginator = 10

        # construct B&F entries
        self.queryset_init = None

        # connect to db and retraive old messages of that circle
        self.usrs = await database_sync_to_async(self.get_messages)()

        # add user to circle room
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        # send message to that web socket request only. not to the group members
        await self.send(text_data=json.dumps(self.usrs))

    def get_messages(self):
        """ Get the B&f entries and paginate them in 10 entries per page.
        The entries are sorted from the latest to the oldest.
        """
        circle = voteModels.Circle.objects.get(code = self.circleName)
        if circle:
            objects = apiSerializers.CircleBackNForthSerializer(
                voteModels.CircleBackNForth.objects.filter(circle=circle).order_by('-date'), many=True
                ).data
            self.queryset_init = objects

            paginator = Paginator(objects, self.paginator)  # Paginate queryset with 5 items per page
            page = paginator.get_page(self.pageNum)
            return list(page)
        return 0

    # Receive message from WebSocket
    async def receive(self, text_data):
        """Check if the page_number is in the message.
        If so, it means to load more messages. Else, forward the new entry to the room
        """
        if "page_number" in text_data:
            page_number = text_data.split(",")[1]
            # here send the next page of the paginated queryset
            # send only to that user
            self.pageNum = page_number
            paginator = Paginator(self.queryset_init, self.paginator)  # Paginate queryset with 5 items per page
            page = paginator.get_page(self.pageNum)

            items = list(page)
            await self.send(text_data=json.dumps(items))
        else:
            # get the message from the client. change it to python json and send to group
            text_json = json.loads(text_data)
            await self.channel_layer.group_send(
                self.room_group_name, {"type": "circleChat", "message": text_json}
            )

    # handling function for sending all the messages to room members
    async def circleChat(self, event):
        # save the incoming messages into DB here.
        saved_massage = await database_sync_to_async(self.save_message)(event['message'])
        await self.send(text_data=json.dumps(saved_massage))

    # Save the message into DB and return a serialized instance of the message
    def save_message(self,msg):
        # get circle and user instance
        circle = voteModels.Circle.objects.get(code = self.circleName)
        usr = User.objects.get(username = msg["sender"])
        # here validate if the user is a member of the circle and create a message instance to save into DB
        objects = voteModels.CircleBackNForth.objects.create( circle = circle, sender= usr, message = ""+msg['message'],)
        objects.save()
        return apiSerializers.CircleBackNForthSerializer(objects).data

    # when a member of the room leaves the room
    async def disconnect(self,message):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        self.close()

# end of the B&F
