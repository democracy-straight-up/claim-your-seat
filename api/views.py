from curses.ascii import NUL
import os
from django.urls import reverse
from rest_framework import viewsets
from vote import models as voteModels
from api import serializers as apiSerializers
from rest_framework.permissions import IsAuthenticatedOrReadOnly, AllowAny
from django.contrib.auth.models import User
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework import generics
from rest_framework.decorators import api_view
from rest_framework.pagination import PageNumberPagination

from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from vote.token import account_activation_token
from django.http import JsonResponse
from django.contrib.auth import authenticate, login
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string


from api import models as apiModels

class CustomPagination(PageNumberPagination):
    """
    We are creating a custome pagination 
    to limit the query and more """
    page_size = 10  # Number of items per page
    # Allows the client to override the page size
    page_size_query_param = 'page_size'
    max_page_size = 100  # Maximum page size to prevent abuse


class DistrictsViewSet(viewsets.ModelViewSet):
    queryset = voteModels.Districts.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = apiSerializers.DistrictsSerializer


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = apiSerializers.RegisterSerializer


def activate(request, uidb64, token):
    """after the claiming your seat, this function handles the activation of user via email"""
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        users = User.objects.get(id=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        users = None
        return Response({"status": 'exception!'}, status=status.HTTP_400_BAD_REQUEST)
    if users is not None and account_activation_token.check_token(users, token):
        users.is_active = User.objects.filter(
            id=uid).update(is_active=True, is_staff=True)
        return JsonResponse({'entry_code': users.username}, safe=False)
    else:
        return Response({"status": 'Activation link is invalid!'}, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetRequestView(APIView):
    queryset = User.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = apiSerializers.PasswordResetRequestSerializer

    def post(self, request, *args, **kwargs):
        serializer = apiSerializers.PasswordResetRequestSerializer(
            data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            user = User.objects.get(email=email)
            mail_subject = 'Reset your password'
            # prepare the email by template
            message = render_to_string('api/resetPasswordEmail.html', {
                'user': user,
                'domain': os.environ.get('APP_DOMAIN'),
                'protocol': 'https',
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': account_activation_token.make_token(user),
            })

            send_mail(
                mail_subject,
                message,
                settings.EMAIL_HOST_USER,
                [email]
            )
            return Response({"message": "Email sent."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetConfirmView(APIView):
    queryset = User.objects.all()
    permission_classes = (AllowAny,)

    def post(self, request):
        serializer = apiSerializers.PasswordResetSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            return Response({"message": "Password is reset"}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserPageView(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = apiSerializers.UserSerializer


class VoterPageView(viewsets.ModelViewSet):
    queryset = voteModels.Users.objects.all()
    serializer_class = apiSerializers.VoterPageSerializer


class LoginPageView(APIView):
    """
    View to list all users in the system.
    * Requires token authentication.
    """
    # authentication_classes = [authentication.TokenAuthentication]
    # permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        """
        authenticate user and return the use object to the voterpage
        """
        post_data = request.data
        # username is the entry-code
        authedUser = authenticate(
            request, username=post_data['username'], password=post_data['password'])

        if authedUser is not None:
            # authenticate if has the same district code
            dist = voteModels.Districts.objects.get(
                code=post_data['district'].upper())
            if authedUser.users.district != dist:
                messages = 'Invalid Credential. Check if you have entered the right district code'
                return Response({"status": messages}, status=status.HTTP_400_BAD_REQUEST)

            # login(request,authedUser)
            data = {
                'legalName': authedUser.users.legalName,
                'username': authedUser.username,
                'email': authedUser.email,
                'userType': authedUser.users.userType,
                'address': authedUser.users.address,
                'verificationScore': authedUser.users.verificationScore,
                'is_reg': authedUser.users.is_reg,
                'district': authedUser.users.district.code,
                'date_joined': authedUser.date_joined,
            }
            return JsonResponse(data)
        else:
            messages = "Invalid Credential"
            return Response({"status": messages}, status=status.HTTP_400_BAD_REQUEST)


def pod_invitation_generator():
    """ this function is being used in cnosumerCircle as well
    this is the pod code generator. 
    It uses random and checks for the database. 
    return the code if it's not taken
    """
    import random
    code = str(random.randint(0, 9999999999))
    is_exist = voteModels.Pod.objects.filter(invitation_code=code).exists()
    if is_exist:
        pod_invitation_generator()
    return code


def pod_code_generator():
    """
    this is the pod code generator. 
    It uses random and checks for the database. 
    return the code if it's not taken
    """
    import random
    code = str(random.randint(1, 99999))
    is_exist = voteModels.Pod.objects.filter(code=code).exists()

    if is_exist:
        pod_code_generator()
    return code


class CreatePOD(APIView):
    """
    creates a pod. 
    it set the userType to 1.
    it set the user as a delegate pod member
    """

    def post(self, request):
        try:
            user = NUL
            district = NUL
            if 'user' in request.data and 'district' in request.data:
                user = User.objects.get(username=request.data['user'])
                district = voteModels.Districts.objects.get(
                    code=request.data['district'])
            else:
                messages = "User and District are required."
                return Response({"message:": messages}, status=status.HTTP_400_BAD_REQUEST)

            # check if the userType is not 0 return
            if user.users.userType != 0:
                messages = "Already belongs to a pod."
                return Response({"message": messages}, status=status.HTTP_400_BAD_REQUEST)

            # create a pod
            pod = voteModels.Pod.objects.create(
                code=pod_code_generator(),
                district=district,
                invitation_code=pod_invitation_generator()
            )
            pod.save()

            # set the userType attribute of the creator to 1
            user.users.userType += 1
            user.save()
            user.users.save()

            # add the user to pod member as delegate
            pod_member_obj = voteModels.PodMember.objects.create(
                user=user,
                pod=pod,
                is_delegate=True,
                is_member=True,
                member_number=1,
            )
            pod_member_obj.save()
            obj = apiSerializers.PodSerializer(pod)
            return JsonResponse(obj.data)
        except:
            messages = "Something Went Wrong."
            return Response({"message:": messages}, status=status.HTTP_400_BAD_REQUEST)


class PodMem(APIView):
    # check if this class is even being used...
    # It retrives all the podmembers of all pods.
    # something we do not want
    def post(self, request):
        try:
            pod = voteModels.PodMember.objects.all()
            return Response(apiSerializers.PODMemberSer(pod, many=True).data, status=status.HTTP_200_OK)
        except:
            return JsonResponse({False: True})


class UserView(APIView):
    def post(self, request):
        try:
            user = NUL
            if 'user' in request.data:
                user = User.objects.get(username=request.data['user'])
            else:
                messages = "user is required."
                return Response({"message": messages}, status=status.HTTP_400_BAD_REQUEST)

            # if user.users.userstype is 1 then send the pod info as well.
            if user.users.userType == 1:
                return JsonResponse({
                    "pod": apiSerializers.PodSerializer(user.podmember_set.first().pod).data,
                    "user": apiSerializers.UserSerializer(user).data,
                })

            return JsonResponse({"user": apiSerializers.UserSerializer(user).data, })

        except:
            messages = "Something Went Wrong."
            return Response({"message": messages}, status=status.HTTP_400_BAD_REQUEST)


class HouseKeeping(APIView):
    def post(self, request):
        try:
            pod = NUL
            if 'pod' in request.data:
                pod = voteModels.Pod.objects.get(code=request.data['pod'])
            else:
                messages = "POD is required."
                return Response({"message": messages}, status=status.HTTP_400_BAD_REQUEST)

            # get all the pod members.
            podMembers = pod.podmember_set.all()

            data = {
                "pod": apiSerializers.PodSerializer(pod).data,
                "podMembers": apiSerializers.PODMemberSer(podMembers, many=True).data
            }
            return JsonResponse(data)
        except:
            messages = "Something Went Wrong."
            return Response({"message": messages}, status=status.HTTP_400_BAD_REQUEST)


def pod_joining_validation(user, pod):
    """
    this function validate weather a user can enter a pod.
    It check if pod is active.
    It check if user is already a member
    It check if userType is 0
    It checks if the user is the same districts as pod distract
    """
    result = True
    # if not pod.is_active():
    #     print("pod is active")
    #     result = False

    podmembers = pod.podmember_set.all()
    if podmembers.count() >= 12:
        result = False

    if podmembers.filter(user=user):
        result = False

    if user.users.userType > 0:
        result = False

    if user.users.district != pod.district:
        result = False

    return result


class JoinPOD(APIView):
    def post(self, request):
        try:
            pod = NUL
            user = NUL
            if 'pod' in request.data and 'user' in request.data:
                pod = voteModels.Pod.objects.get(
                    invitation_code=request.data['pod'])
                user = User.objects.get(username=request.data['user'])
            else:
                messages = "POD  and user are required."
                return Response({"message": messages}, status=status.HTTP_400_BAD_REQUEST)

            # get the pod and add the user as the member or candidate
            if pod:
                # check if user can join the pod
                if pod_joining_validation(user, pod):
                    podMember = voteModels.PodMember.objects.create(
                        user=user,
                        pod=pod,
                        is_member=False,
                        is_delegate=False,
                        member_number=pod.podmember_set.count()+1
                    )
                    podMember.save()
                    # set the userType of the member to 0
                    # when the user become the member via majority votes, then the userType is set to 1
                    podMember.user.users.userType = 1
                    podMember.user.users.save()
                    return JsonResponse(apiSerializers.PodSerializer(pod).data)
                else:
                    # else of pod is active
                    messages = 'either the pod is not accepting memebers or you are not eligible to join this pod'
                    return Response({"message": messages}, status=status.HTTP_400_BAD_REQUEST)

            messages = 'your request did not get processed.'
            return Response({"message": messages}, status=status.HTTP_400_BAD_REQUEST)

        except:
            messages = "Something Went Wrong."
            return Response({"message": messages}, status=status.HTTP_400_BAD_REQUEST)


def pod_desolve_check(user, pod):
    members = pod.podmember_set.filter(is_member=True)
    if members.first().user.username != user.username:
        return False
    if not members.first().is_delegate:
        return False
    if members.count() > 1:
        return False

    return True


class DesolvePod(APIView):
    def post(self, request):

        try:
            pod = NUL
            user = NUL
            if 'pod' in request.data and 'user' in request.data:
                pod = voteModels.Pod.objects.get(code=request.data['pod'])
                user = User.objects.get(username=request.data['user'])
            else:
                messages = "Pod  and user are required."
                return Response({"message": messages}, status=status.HTTP_400_BAD_REQUEST)

            # get the pod and check weather the pod is eligible to be desolved!
            if pod:
                # check if user can join the pod
                if pod_desolve_check(user, pod):
                    pod.delete()
                    user.users.userType = 0
                    user.users.save()
                    # the user automatically sets back to userType = 0
                    return JsonResponse({"status": "desolved"})
                else:
                    # else of pod is active
                    messages = 'can not desolve the pod at the moment.'
                    return Response({"message": messages}, status=status.HTTP_400_BAD_REQUEST)
        except:
            messages = "Something Went Wrong."
            return Response({"message": messages}, status=status.HTTP_400_BAD_REQUEST)


# do we use this view ?
class PodBackNForth(APIView):
    # list all the messsages to that Pod
    def post(self, request, pod):
        try:
            chats = voteModels.PodBackNForth.objects.all()
            return Response(apiSerializers.PodBackNForthSerializer(chats, many=True).data, status=status.HTTP_200_OK)
        except:
            return JsonResponse({False: pod})

# do we use this view as well ?


class PodBackNForthAdd(APIView):
    # add a message to Pod Back and Forth
    def post(self, request, pod):
        try:
            return Response({"date": "added one message to the pod: " + pod}, status=status.HTTP_200_OK)
        except:
            return JsonResponse({False: pod})


# get the vote in for user for a circle
class PodMemeber_voteIn(generics.ListAPIView):
    serializer_class = apiSerializers.PodMember_VoteInSer
    queryset = voteModels.PodMember_vote_in.objects.filter()
    permission_classes = [AllowAny]

    def get_queryset(self):
        candidate_id = self.request.query_params.get('candidate')
        if candidate_id:
            self.queryset = self.queryset.filter(condidate__pk=candidate_id)
        return self.queryset

# get the vote out for user of a circle


class PodMemeber_voteOut(generics.ListAPIView):
    serializer_class = apiSerializers.PodMember_VoteOutSer
    queryset = voteModels.PodMember_vote_out.objects.filter()
    permission_classes = [AllowAny]

    def get_queryset(self):
        member_id = self.request.query_params.get('member')
        if member_id:
            self.queryset = self.queryset.filter(condidate__pk=member_id)
        return self.queryset

# get the put farward for gelegation of a member of a circle


class PodMemeber_putfarward(generics.ListAPIView):
    serializer_class = apiSerializers.PodMember_put_farwardSer
    queryset = voteModels.PodMember_put_farward.objects.filter()
    permission_classes = [AllowAny]

    def get_queryset(self):
        member_id = self.request.query_params.get('member')
        if member_id:
            self.queryset = self.queryset.filter(recipient__pk=member_id)
        return self.queryset


class CircleList(viewsets.ModelViewSet):
    serializer_class = apiSerializers.PodSerializer
    queryset = voteModels.Pod.objects.all()
    pagination_class = CustomPagination
    permission_classes = [AllowAny]


class CircleStatus(generics.ListAPIView):
    serializer_class = apiSerializers.CircleStatusSerializer
    queryset = voteModels.CircleStatus.objects.all()
    permission_classes = [AllowAny]

class TestingView(generics.ListAPIView):
    serializer_class = apiSerializers.TestingSerializer
    queryset = apiModels.TestingModel.objects.all()
    permission_classes = [AllowAny]