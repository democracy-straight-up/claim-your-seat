from rest_framework import viewsets
from moda import models 
from moda import serializers
from django.contrib.auth.models import User
from vote.models import Districts
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404


class ModaViewSet(viewsets.ModelViewSet):
    queryset = models.ModaModel.objects.all()
    serializer_class = serializers.ModaSerializer
    
    def create(self, request, *args, **kwargs):
        try:
            user=None, 
            district =None
            if 'user' in request.data and 'district' in request.data:
                user = User.objects.get(username=request.data['user'])
                district = Districts.objects.get(
                    code=request.data['district'])
            else:
                messages = "District is required."
                return Response({"message:": messages}, status=status.HTTP_400_BAD_REQUEST)

            # check if the userType is not 0 return
            if user.users.userType[:2] == 'U3':
                messages = "Already belongs to a S-Link."
                return Response({"message": messages}, status=status.HTTP_400_BAD_REQUEST)
            # create a sec_del object
            moda =  models.ModaModel.objects.create(district=district)
    
            # set the userType attribute of the creator to 1
            # add the user to circle member as delegate. it does not require to save. create automatically saves as well
            models.ModaMembers.objects.create(user=user, moda=moda, is_member=True)

            obj = serializers.ModaSerializer(moda)
    
            return JsonResponse(obj.data)
        except:
            messages = "Something Went Wrong."
            return Response({"message:": messages}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['POST'])
    def get_s_link_by_user(self,request):
        try:
            username = request.data['user']
        except KeyError:
            return Response({'message': "Missing 'user' field in request data."},
                status=status.HTTP_400_BAD_REQUEST)
        # get_object_or_404 handles the try/except DoesNotExist for you
        # It raises Http404 if the object is not found
  
        instance = get_object_or_404(models.ModaMembers, user__username=username)
        # If the object is found, execution continues here
        serial = self.get_serializer(instance.moda)
        return Response(serial.data)
    
class ModaMembersViewSet(viewsets.ModelViewSet):
    queryset = models.ModaMembers.objects.all()
    serializer_class = serializers.ModaMembersSerializer

    @action(detail=False, methods=['POST'])
    def join_invite_key(self,request):
        try:
            moda = models.ModaModel.objects.get(invitation_key=request.data['inviteKey'])
            user = User.objects.get(username=request.data['user'])
            models.ModaMembers.objects.create(user=user, moda=moda)
            members = models.ModaMembers.objects.filter(moda=moda)
            serializer = self.get_serializer(members, many=True)
            return Response(serializer.data)
        except models.ModaModel.DoesNotExist:
            return Response({"message": "S-Link not found."}, status=status.HTTP_404_NOT_FOUND)
        except models.ModaMembers.DoesNotExist:
            return Response({"message": "S-Link members not found."}, status=status.HTTP_404_NOT_FOUND)
        except models.MaxMembershipReached:
            return Response({"message": "The S-Link has reached its maximum membership and does not accept new candidate!"}, status=status.HTTP_406_NOT_ACCEPTABLE)
