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
from django.db import IntegrityError, transaction
from django.db.models import F
from succession_notifications import (
    post_succession_update,
    user_display_name,
)

class ModaViewSet(viewsets.ModelViewSet):
    queryset = models.ModaModel.objects.all()
    serializer_class = serializers.ModaSerializer
    def update(self, request, *args, **kwargs):
        return Response(
            {"message": "Direct Second Link updates are not permitted."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def partial_update(self, request, *args, **kwargs):
        return Response(
            {"message": "Direct Second Link updates are not permitted."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )
    def destroy(self, request, *args, **kwargs):
        if not request.user or not request.user.is_authenticated:
            return Response(
                {"message": "Authentication is required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        with transaction.atomic():
            second_link = self.get_object()
            second_link = models.ModaModel.objects.select_for_update().get(
                pk=second_link.pk
            )

            # Only the serving Caucus Delegate may dissolve the group.
            is_delegate = models.ModaMembers.objects.filter(
                moda=second_link,
                user=request.user,
                is_member=True,
                is_delegate=True,
            ).exists()

            if not is_delegate:
                return Response(
                    {
                        "message": (
                            "Only the current Caucus Delegate "
                            "may dissolve this Second Link."
                        )
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            # A delegate cannot dissolve a group containing
            # other accepted members.
            accepted_count = models.ModaMembers.objects.filter(
                moda=second_link,
                is_member=True,
            ).count()

            if accepted_count != 1:
                return Response(
                    {
                        "message": (
                            "The Second Link cannot be dissolved "
                            "while other accepted members remain."
                        )
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            second_link.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)
    
    def create(self, request, *args, **kwargs):
        if not request.user or not request.user.is_authenticated:
            return Response(
                {"message": "Authentication is required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        supplied_username = request.data.get("user")

        if (
            supplied_username is not None
            and supplied_username != request.user.username
        ):
            return Response(
                {
                    "message": (
                        "You may only create a Second Link "
                        "for your own account."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            user=None, 
            district =None
            if 'user' in request.data and 'district' in request.data:
                user = request.user
                district = Districts.objects.get(
                    code=request.data['district'])
            else:
                messages = "District is required."
                return Response({"message:": messages}, status=status.HTTP_400_BAD_REQUEST)

            # check if the userType is not 0 return
            if user.users.userType[:2] == 'U3':
                messages = "Already belongs to a S-Link."
                return Response({"message": messages}, status=status.HTTP_400_BAD_REQUEST)
            # A user may not already belong to, or be
            # an applicant for, another Second Link.
            if models.ModaMembers.objects.filter(user=user).exists():
                return Response(
                    {
                        "message": (
                            "User already has a Second Link "
                            "membership or application."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Create the Second Link.
            moda = models.ModaModel.objects.create(district=district)
    
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
    def create(self, request, *args, **kwargs):
        return Response(
            {
                "message": (
                    "Direct membership creation is not permitted."
                )
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )
    def update(self, request, *args, **kwargs):
        return Response(
            {"message": "Direct membership updates are not permitted."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def partial_update(self, request, *args, **kwargs):
        return Response(
            {"message": "Direct membership updates are not permitted."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )
    def destroy(self, request, *args, **kwargs):
        if not request.user or not request.user.is_authenticated:
            return Response(
                {"message": "Authentication is required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        membership = self.get_object()

        if membership.user_id != request.user.pk:
            return Response(
                {"message": "You may only leave your own Second Link."},
                status=status.HTTP_403_FORBIDDEN,
            )

        with transaction.atomic():
            membership = models.ModaMembers.objects.select_for_update().get(
                pk=membership.pk
            )
            if membership.is_member and membership.is_delegate:
                return Response(
                    {
                        "message": (
                            "A Caucus Delegate must be replaced before "
                            "voluntarily leaving the Second Link. "
                            "If you are the sole member, use the "
                            "group dissolution procedure."
                        )
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
            second_link = membership.moda
            departing_position = membership.succession_position
            departing_name = user_display_name(membership.user)

            compacted_memberships = []

            if membership.is_member and departing_position is not None:
                compacted_memberships = list(
                    models.ModaMembers.objects.select_for_update()
                    .filter(
                        moda=second_link,
                        is_member=True,
                        succession_position__gt=departing_position,
                    )
                    .order_by("succession_position")
                )

            membership.delete()

            if compacted_memberships:
                models.ModaMembers.objects.filter(
                    pk__in=[
                        member.pk
                        for member in compacted_memberships
                    ]
                ).update(
                    succession_position=F("succession_position") - 1
                )

                for member in compacted_memberships:
                    old_position = member.succession_position
                    new_position = old_position - 1

                    post_succession_update(
                        message_model=models.ModaBackNForthChat,
                        group_field="moda",
                        group=second_link,
                        message=(
                            f"Succession update: "
                            f"{user_display_name(member.user)} moved "
                            f"from position {old_position} to position "
                            f"{new_position} after {departing_name} "
                            f"voluntarily left the Second Link."
                        ),
                    )

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['POST'])
    def join_invite_key(self, request):
        if not request.user or not request.user.is_authenticated:
            return Response(
                {"message": "Authentication is required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        supplied_username = request.data.get("user")

        if not supplied_username:
            return Response(
                {"message": "User is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if supplied_username != request.user.username:
            return Response(
                {
                    "message": (
                        "You may only apply to join a Second Link "
                        "using your own account."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            moda = models.ModaModel.objects.get(invitation_key=request.data['inviteKey'])
            user = request.user

            if models.ModaMembers.objects.filter(user=user).exists():
                return Response(
                    {
                        "message": (
                            "You already belong to a Second Link "
                            "or have a pending application."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                with transaction.atomic():
                    models.ModaMembers.objects.create(
                        user=user,
                        moda=moda,
                    )
            except IntegrityError:
                return Response(
                    {
                        "message": (
                            "You already belong to a Second Link "
                            "or have a pending application."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            members = models.ModaMembers.objects.filter(moda=moda)
            serializer = self.get_serializer(members, many=True)
            return Response(serializer.data)
        except models.ModaModel.DoesNotExist:
            return Response({"message": "S-Link not found."}, status=status.HTTP_404_NOT_FOUND)
        except models.ModaMembers.DoesNotExist:
            return Response({"message": "S-Link members not found."}, status=status.HTTP_404_NOT_FOUND)
        except models.MaxMembershipReached:
            return Response({"message": "The S-Link has reached its maximum membership and does not accept new candidate!"}, status=status.HTTP_406_NOT_ACCEPTABLE)


class ModaMemberContactViewSet(viewsets.ModelViewSet):
    queryset = models.ModaMemberContact.objects.all()
    serializer_class = serializers.ModaMemberContactSerializer
    
    @action(detail=False, methods=['GET'])
    def by_moda_code(self, request):
        """Get all contact info for a specific moda by code"""
        code = request.query_params.get('code')
        if not code:
            return Response({"message": "Moda code is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            moda = models.ModaModel.objects.get(code=code)
            contacts = models.ModaMemberContact.objects.filter(moda=moda)
            serializer = self.get_serializer(contacts, many=True)
            return Response(serializer.data)
        except models.ModaModel.DoesNotExist:
            return Response({"message": "Moda not found"}, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=False, methods=['GET'])
    def by_member(self, request):
        """Get contact info for a specific member by username"""
        username = request.query_params.get('username')
        if not username:
            return Response({"message": "Username is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            member = models.ModaMembers.objects.get(user__username=username)
            contact = models.ModaMemberContact.objects.get(member=member)
            serializer = self.get_serializer(contact)
            return Response(serializer.data)
        except models.ModaMembers.DoesNotExist:
            return Response({"message": "Member not found"}, status=status.HTTP_404_NOT_FOUND)
        except models.ModaMemberContact.DoesNotExist:
            return Response({"message": "Contact info not found"}, status=status.HTTP_404_NOT_FOUND)
