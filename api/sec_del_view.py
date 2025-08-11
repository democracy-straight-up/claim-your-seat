from rest_framework import viewsets
from api import models as apiModels
from api import sec_del_ser as apiSerializer
from django.contrib.auth.models import User
from vote.models import Districts
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated


class SecDelViewSet(viewsets.ModelViewSet):
    queryset = apiModels.SecDelModel.objects.all()
    serializer_class = apiSerializer.SecDelSerializer
    
    def create(self, request, *args, **kwargs):
        try:
            user=None, 
            district =None
            if 'user' in request.data and 'district' in request.data:
                user = User.objects.get(username=request.data['user'])
                district = Districts.objects.get(
                    code=request.data['district'])
            else:
                messages = "District are required."
                return Response({"message:": messages}, status=status.HTTP_400_BAD_REQUEST)
            
            print("later on, uncomment this condition ", user,district)
            # check if the userType is not 0 return
            # if user.users.userType[:2] == 'U2':
            #     messages = "Already belongs to a sec del."
            #     return Response({"message": messages}, status=status.HTTP_400_BAD_REQUEST)
            # create a sec_del object
            sec_del = apiModels.SecDelModel.objects.create( district=district  )
            # set the userType attribute of the creator to 1
            # add the user to circle member as delegate. it does not require to save. create automatically saves as well
            apiModels.SecDelMembers.objects.create(user=user,sec_del=sec_del, is_member=True)
            obj = apiSerializer.SecDelSerializer(sec_del)
    
            return JsonResponse(obj.data)
        except:
            messages = "Something Went Wrong."
            return Response({"message:": messages}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['POST'])
    def get_f_link_by_user(self,request):
        try:
            username = request.data['user']
        except KeyError:
            return Response({'message': "Missing 'user' field in request data."},
                status=status.HTTP_400_BAD_REQUEST)
        # get_object_or_404 handles the try/except DoesNotExist for you
        # It raises Http404 if the object is not found
        instance = get_object_or_404(apiModels.SecDelMembers, user__username=username)
        # If the object is found, execution continues here
        serial = self.get_serializer(instance.sec_del)
        return Response(serial.data)
    
class SecDelMembersViewSet(viewsets.ModelViewSet):
    queryset = apiModels.SecDelMembers.objects.all()
    serializer_class = apiSerializer.SecDelMembersSerializer

    @action(detail=False, methods=['POST'])
    def join_invite_key(self,request):
        try:
            sec_del = apiModels.SecDelModel.objects.get(invitation_key=request.data['inviteKey'])
            user = User.objects.get(username=request.data['user'])
            apiModels.SecDelMembers.objects.create(user=user, sec_del=sec_del)
            members = apiModels.SecDelMembers.objects.filter(sec_del=sec_del)
            serializer = self.get_serializer(members, many=True)
            return Response(serializer.data)
        except apiModels.SecDelModel.DoesNotExist:
            return Response({"message": "f-link not found."}, status=status.HTTP_404_NOT_FOUND)
        except apiModels.SecDelMembers.DoesNotExist:
            return Response({"message": "f-link members not found."}, status=status.HTTP_404_NOT_FOUND)
        except apiModels.MaxMembershipReached:
            return Response({"message": "The F-Link has reached its maximum membership and does not accept new candidate!"}, status=status.HTTP_406_NOT_ACCEPTABLE)


# Contact API Views
class SecDelContactInfoViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing SecDel contacts
    """
    serializer_class = apiSerializer.SecDelMemberContactInfoSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        # Get the user's current group (circle) - assuming user is only in one active group
        user_group_membership = apiModels.SecDelMembers.objects.filter(
            user=self.request.user, is_member=True
        ).first()

        if not user_group_membership:
            # If user is not a member of any group, return empty queryset
            return apiModels.ContactInfo.objects.none()
        
        # Return contacts only for the user's current group
        return apiModels.ContactInfo.objects.filter(
            sec_del=user_group_membership.sec_del
        )
    
    def perform_update(self, serializer):
        # Only allow updating if user is a delegate of the group
        contact = serializer.instance
        user_is_delegate = apiModels.SecDelMembers.objects.filter(
            user=self.request.user,
            sec_del=contact.sec_del,
            is_delegate=True
        ).exists()
        
        if not user_is_delegate:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only delegates can update contact information")
        
        serializer.save()