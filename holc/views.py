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
from django.db import transaction
from django.core.exceptions import ValidationError
from moda.models import ModaMembers

class HolcViewSet(viewsets.ModelViewSet):
    queryset = models.HolcModel.objects.all()
    serializer_class = serializers.HolcSerializer
    
    def create(self, request, *args, **kwargs):
        user = request.user
        profile = getattr(user, "users", None)

        if (
            not user.is_authenticated
            or not user.is_active
            or getattr(profile, "userType", None) != "U4D3"
        ):
            return Response(
                {
                    "message": (
                        "Only a Caucus Delegate who is not a HoLC "
                        "may create a Caucus."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if request.data.get("user") != request.user.username:
            return Response(
                {"message": "You can only create a Caucus for yourself."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            district = Districts.objects.get(code=request.data["district"])
        except KeyError:
            return Response(
                {"message": "District is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Districts.DoesNotExist:
            return Response(
                {"message": "District not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if getattr(profile, "district_id", None) != district.pk:
            return Response(
                {"message": "You may only create a Caucus in your own district."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            with transaction.atomic():
                has_active_delegate_mandate = (
                    ModaMembers.objects.select_for_update()
                    .filter(
                        user=user,
                        is_member=True,
                        is_delegate=True,
                        moda__district=district,
                        moda__status=True,
                    )
                    .exists()
                )

                if not has_active_delegate_mandate:
                    return Response(
                        {
                            "message": (
                                "An active Second Link delegate mandate is "
                                "required to create a Caucus."
                            )
                        },
                        status=status.HTTP_403_FORBIDDEN,
                    )

                current_memberships = list(
                    models.HolcMembers.objects.select_for_update().filter(
                        user=user,
                        is_member=True,
                        holc__district=district,
                    )
                )

                if any(
                    membership.is_delegate
                    for membership in current_memberships
                ):
                    return Response(
                        {
                            "message": (
                                "A HoLC must relinquish that office before "
                                "creating another Caucus."
                            )
                        },
                        status=status.HTTP_403_FORBIDDEN,
                    )

                current_membership_ids = [
                    membership.pk
                    for membership in current_memberships
                ]

                if current_membership_ids:
                    models.HolcMembers.objects.filter(
                        pk__in=current_membership_ids
                    ).delete()

                holc = models.HolcModel.objects.create(district=district)

                models.HolcMembers.objects.create(
                    user=user,
                    holc=holc,
                    is_member=True,
                )

                # Persist the new Caucus's active status immediately.
                holc.is_active

        except ValidationError as exc:
            message = exc.messages[0] if exc.messages else str(exc)
            return Response(
                {"message": message},
                status=status.HTTP_400_BAD_REQUEST,
            )

        obj = serializers.HolcSerializer(holc)
        return JsonResponse(obj.data)


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
