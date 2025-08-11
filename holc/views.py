from rest_framework import viewsets
from holc import models 
from holc import serializers
from django.contrib.auth.models import User
from vote.models import Districts
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404


class HolcViewSet(viewsets.ModelViewSet):
    queryset = models.HolcModel.objects.all()
    serializer_class = serializers.HolcSerializer
    
    def create(self, request, *args, **kwargs):
        try:
            user=None 
            district =None
            if 'user' in request.data and 'district' in request.data:
                user = User.objects.get(username=request.data['user'])
                district = Districts.objects.get(
                    code=request.data['district'])
            else:
                messages = "District is required."
                return Response({"message": messages}, status=status.HTTP_400_BAD_REQUEST)

            # check if the userType is not 0 return
            if user.users.userType[:2] == 'U4':
                messages = "Already belong to another Holc."
                return Response({"message": messages}, status=status.HTTP_400_BAD_REQUEST)
            # create a sec_del object
            holc =  models.HolcModel.objects.create(district=district)
    
            # set the userType attribute of the creator to 1
            # add the user to circle member as delegate. it does not require to save. create automatically saves as well
            models.HolcMembers.objects.create(user=user, holc=holc, is_member=True)

            obj = serializers.HolcSerializer(holc)
    
            return JsonResponse(obj.data)
        except:
            messages = "Something Went Wrong."
            return Response({"message": messages}, status=status.HTTP_400_BAD_REQUEST)


    @action(detail=False, methods=['POST'])
    def get_holc_by_user(self,request):
        try:
            username = request.data['user']
        except KeyError:
            return Response({'message': "Missing 'user' field in request data."},
                status=status.HTTP_400_BAD_REQUEST)
        # get_object_or_404 handles the try/except DoesNotExist for you
        # It raises Http404 if the object is not found
        instance = get_object_or_404(models.HolcMembers, user__username=username)
        # If the object is found, execution continues here
        serial = self.get_serializer(instance.holc)
        return Response(serial.data)
    
class HolcMembersViewSet(viewsets.ModelViewSet):
    queryset = models.HolcMembers.objects.all()
    serializer_class = serializers.HolcMembersSerializer

    @action(detail=False, methods=['POST'])
    def join_invite_key(self,request):
        try:
            holc = models.HolcModel.objects.get(invitation_key=request.data['inviteKey'])
            user = User.objects.get(username=request.data['user'])
            models.HolcMembers.objects.create(user=user, holc=holc)
            members = models.HolcMembers.objects.filter(holc=holc)
            serializer = self.get_serializer(members, many=True)
            return Response(serializer.data)
        except models.HolcModel.DoesNotExist:
            return Response({"message": "Holc not found."}, status=status.HTTP_404_NOT_FOUND)
        except models.HolcMembers.DoesNotExist:
            return Response({"message": "Holc members not found."}, status=status.HTTP_404_NOT_FOUND)
        except models.MaxMembershipReached:
            return Response({"message": "This Holc has reached its maximum membership and does not accept new candidate!"}, status=status.HTTP_406_NOT_ACCEPTABLE)


class HolcMemberContactViewSet(viewsets.ModelViewSet):
    queryset = models.HolcMemberContact.objects.all()
    serializer_class = serializers.HolcMemberContactSerializer
    
    @action(detail=False, methods=['GET'])
    def by_holc_code(self, request):
        """Get all contact info for a specific holc by code"""
        code = request.query_params.get('code')
        if not code:
            return Response({"message": "Holc code is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            holc = models.HolcModel.objects.get(code=code)
            contacts = models.HolcMemberContact.objects.filter(holc=holc)
            serializer = self.get_serializer(contacts, many=True)
            return Response(serializer.data)
        except models.HolcModel.DoesNotExist:
            return Response({"message": "Holc not found"}, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=False, methods=['GET'])
    def by_member(self, request):
        """Get contact info for a specific member by username"""
        username = request.query_params.get('username')
        if not username:
            return Response({"message": "Username is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            member = models.HolcMembers.objects.get(user__username=username)
            contact = models.HolcMemberContact.objects.get(member=member)
            serializer = self.get_serializer(contact)
            return Response(serializer.data)
        except models.HolcMembers.DoesNotExist:
            return Response({"message": "Member not found"}, status=status.HTTP_404_NOT_FOUND)
        except models.HolcMemberContact.DoesNotExist:
            return Response({"message": "Contact info not found"}, status=status.HTTP_404_NOT_FOUND)
