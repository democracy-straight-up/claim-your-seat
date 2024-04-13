from rest_framework.views import APIView
from .serializers import CircleMemberContactSerializer
from .models import CircleMemberContact
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import render, HttpResponse, redirect
from django.views.generic import DetailView, DeleteView
from vote import models as voteModels
from vote import forms as voteForms
from django.contrib.auth.models import User
from django.contrib import messages
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes,force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from vote.serializers import CircleMemberContactSerializer
from vote.token import account_activation_token
from django.core.mail import EmailMessage
from django.contrib.sites.shortcuts import get_current_site
from django.contrib.auth import authenticate, login,logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
import os

def entry_code_generator():
    """
    this is the entry code generator.
    It uses random and checks for the database.
    return the code if it's not taken
    """
    import random
    code  = str(random.choice('abcdefghijklmnpqrstuvwxyz'))
    code += str(random.randint(1,9))
    code += str(random.choice('abcdefghijklmnpqrstuvwxyz'))
    code += str(random.randint(1,9))
    code += str(random.choice('abcdefghijklmnpqrstuvwxyz'))
    code = code.upper()
    is_exist = User.objects.filter(username = code).exists()

    if is_exist:
        entry_code_generator()
    return code


def ClaimYourSeat(request):
    """this is the user creation function. It create a user and assign entry code and relevent info"""
    form = voteForms.ClaimYourSeatForm()
    if request.method == 'POST':
        form = voteForms.ClaimYourSeatForm(request.POST or None)
        if form.is_valid():
            # set the username to 5 digit random unique and set password
            user = form.save(commit=False)
            user.username = entry_code_generator()
            user.email = form.cleaned_data.get('email')
            user.is_active = False
            user.save()

            user.users.legalName = form.cleaned_data.get('legalName')
            user.users.address = form.cleaned_data.get('address')
            usersDistrict = voteModels.Districts.objects.get(code = form.cleaned_data.get('district').upper())
            if usersDistrict:
                user.users.district = usersDistrict

            # set the is_reg true of the user is going to vote within 30 days
            if request.POST.get('is_reg1'):
                user.users.is_reg = True

            user.save()
            messages.success(
                request,
                ("We've sent an email to the address you provided."
                "Open it and click on the link to confirm and Enter the Floor."),
                extra_tags='success'
            )

            # send email
            current_site = get_current_site(request)
            mail_subject = 'Activate your account.'
            message = render_to_string('vote/accountActiveEmail.html', {
                'user': user,
                # 'domain': current_site.domain,
                'domain': os.environ.get('APP_DOMAIN'),
                'uid':urlsafe_base64_encode(force_bytes(user.pk)),
                'token':account_activation_token.make_token(user),
            })
            to_email = user.email
            email = EmailMessage( mail_subject,  message,  to=[to_email] )
            email.send()

            # redirect to confirmation page
            return render(request, 'vote/signUpConfirm.html')
        else:
            return render(request, 'vote/ClaimYourSeat.html',{'form':form})
    return render(request, 'vote/ClaimYourSeat.html',{'form':form})


def activate(request, uidb64, token):
    """after the claiming your seat, this function handles the activation of user via email"""
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        users = User.objects.get(id=uid)
    except(TypeError, ValueError, OverflowError, User.DoesNotExist):
        users = None
    if users is not None and account_activation_token.check_token(users, token):
        users.is_active = User.objects.filter(id=uid).update(is_active=True, is_staff= True)
        login(request, users)
        return render(request, 'vote/activationConfirmation.html',{'entry_code':users.username})
    else:
        return HttpResponse('Activation link is invalid!')


def EnterTheFloor(request):
  """
  this is the login function. it asks for a POST request
  and looks for districts code, entry_code and password.
  """
  if request.method == "POST":
    district = request.POST.get('district').upper()
    userName = request.POST.get('userName').upper()
    upass = request.POST.get('password')
    authedUser = authenticate(request,  username=userName, password=upass)

    if authedUser is not None:

        # authenticate if has the same district code
        if authedUser.users.district.code != district:
            messages.error(
                request,
                'Invalid Credential. Check if you have entered the right district code.',
                extra_tags='danger'
            )
            return redirect('EnterTheFloor')

        login(request,authedUser)
        return redirect('voterPage')
    else:
      messages.error(request,"Invalid Credential", extra_tags='danger')
      return redirect('EnterTheFloor')

  return render(request,"vote/EnterTheFloor.html")

def userLogout(request):
  logout(request)
  return redirect('/')

@login_required(login_url = 'EnterTheFloor')
def voterPage(request):
    circleMember = False

    # get the user if he/she is a member of a circle
    if request.user.users.userType ==1:
        circleMember = voteModels.CircleMember.objects.get(user = request.user)

    time = request.user.date_joined
    if request.user.users.is_reg:
        from datetime import timedelta
        time = request.user.date_joined + timedelta(30)
    data={
        'circle': circleMember,
        'title': 'Voter Page',
        'is_reg': time
    }
    return render(request, 'vote/VoterPage.html',data)


# this the home page of a circle
class HouseKeepingCircle(LoginRequiredMixin,DetailView):
    model = voteModels.Circle
    template_name = 'vote/HouseKeeping.html'

    def post(self,request, *args, **kwargs):
        circle = voteModels.Circle.objects.get(code = request.POST['circle'])
        circle.invitation_code = circle_invitation_generator()
        circle.save()
        messages.success(request, "The circle key has been updated.", extra_tags="success")
        return redirect('circle', pk=circle.pk)


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # check if the user is the circle delegate
        circle = voteModels.Circle.objects.get(pk = self.kwargs['pk'])
        is_delegate = False
        candidate = circle.circlemember_set.filter(is_member = False).first()
        for member in circle.circlemember_set.all():
            if member.is_delegate and member.user == self.request.user:
                is_delegate = True

        # check the candidates vote in/out list and if the logged in user is on the list, set current_used_voted to true
        current_user_voted = False
        if candidate:
            # vote in
            voteINs = candidate.circlemember_vote_in_set.filter(voter = self.request.user)
            for voter in voteINs:
                if voter.voter == self.request.user:
                    current_user_voted = True

            # vote out
            voteINs = candidate.circlemember_vote_out_set.filter(voter = self.request.user)
            for voter in voteINs:
                if voter.voter == self.request.user:
                    current_user_voted = True

        # if user is_member
        # to check if the logged in user has voted for delegated
        current_user_delegated = False
        # circle_delegates = voteModels.CircleMember_put_farward.objects.filter(delegated__circle = circle)
        # for i in circle_delegates:
        #     if i.voter == self.request.user:
        #         current_user_delegated = True

        context['title'] = "DSU - House Keeping Page"
        context['candidate'] = candidate
        context['is_delegate'] = is_delegate
        context['voted'] = current_user_voted
        context['delegated'] = current_user_delegated
        return context

def circle_invitation_generator():
    """
    this is the circle code generator.
    It uses random and checks for the database.
    return the code if it's not taken
    """
    import random
    code = str(random.randint(0,9999999999))
    is_exist = voteModels.Circle.objects.filter(invitation_code = code).exists()
    if is_exist:
        circle_invitation_generator()
    return code

def circle_code_generator():
    """
    this is the circle code generator.
    It uses random and checks for the database.
    return the code if it's not taken
    """
    import random
    code = str(random.randint(1,99999))
    is_exist = voteModels.Circle.objects.filter(code = code).exists()

    if is_exist:
        circle_code_generator()
    return code

@login_required(login_url='EnterTheFloor')
def CreateCircle(request):
    """
    this function creates a circle.
    it set the userType to 1.
    it set the user as a delegate circle member
    """
    # create a circle
    circle = voteModels.Circle.objects.create(
        code = circle_code_generator(),
        district = request.user.users.district,
        invitation_code = circle_invitation_generator()
    )
    circle.save()

    # set the userType attribute of the creator to 1
    user = request.user
    user.users.userType +=1
    user.save()

    # add the user to circle member as delegate
    circle_member_obj = voteModels.CircleMember.objects.create(
        user = request.user,
        circle = circle,
        is_delegate = True,
        is_member = True,
        member_number = 1,
    )
    circle_member_obj.save()

    return redirect('circle', pk = circle.pk)


def circle_joining_validation(user,circle):
    """
    this function validate weather a user can enter a circle.
    It check if circle is active.
    It check if user is already a member
    It check if userType is 0
    """
    result = True
    # if not circle.is_active():
    #     print("circle is active")
    #     result = False

    circlemembers = circle.circlemember_set.all()
    if circlemembers.count() >= 12:
        result = False

    if circlemembers.filter(user = user):
        result = False

    if user.users.userType > 0:
        result = False

    return result


@login_required(login_url='EnterTheFloor')
def joinCircle(request):
    form = voteForms.JoinCircleMemberForm()
    if request.method =="POST":
        form = voteForms.JoinCircleMemberForm(request.POST or None)
        if form.is_valid():
            invitationCode = form.cleaned_data.get('invitationCode').upper()
            # check if circle exist
            circles = voteModels.Circle.objects.filter(invitation_code = invitationCode)
            if circles.exists():
                # check if user can join the circle
                if circle_joining_validation(request.user, circles.first()):
                    circleMember = voteModels.CircleMember.objects.create(
                        user = request.user,
                        circle = circles.first(),
                        is_member = False,
                        is_delegate = False,
                        member_number = circles.first().circlemember_set.count()+1
                    )
                    circleMember.save()

                    messages.success(
                        request,
                        ('In order to become a member of this Circle you need to be'
                         '‘voted in’ by a majority of the existing members. '
                         'You can wait and see if you are voted in, or you can contact '
                         'your F-Del IRL and ask them to start a vote among existing members.'),
                        extra_tags="success"
                    )
                    return redirect('circle', pk = circles.first().pk)
                else:
                    # else of circle is active
                    messages.error(request, 'Circle is not accepting member anymore', extra_tags='danger')
                    return redirect('joinCircle')
            else:
                # else of circle_obj
                messages.error(request, 'there is not circle with this code.',extra_tags='danger')
                return redirect('joinCircle')
        else:
            # else of form is_valid
            return render(request,'vote/joinCircle.html', {'form':form})

    return render(request,'vote/joinCircle.html', {'form':form})


def majorityVotes(circle, member):
    circle_members = circle.circlemember_set.filter(is_member = True)
    member_vote = member.circlemember_vote_in_set.all()
    if member_vote.count() > (circle_members.count()/2):
        return True
    return False


# vote members in a circle (IN, OUT)
@login_required(login_url='EnterTheFloor')
def circleVoteIN(request):
    if request.method == "POST":
        """vote the member in to become a member of the circle
            check if the vote in is 50% + 1 to become the member (majority votes)
            make sure that members can only vote in/out once"""
        member = voteModels.CircleMember.objects.get(pk = request.POST.get('member'))
        voteIN = voteModels.CircleMember_vote_in.objects.create(candidate = member, voter = request.user)
        voteIN.save()
        # check if he/she has got the majority votes
        if majorityVotes(member.circle, member):
            member.is_member = True
            member.save()
            # set the member.user.users.userType to 1 as it becomes the member in a circle.
            userType = member.user
            userType.users.userType = 1
            userType.save()

        messages.success(request,'Voted in', extra_tags='success')
        return redirect('circle', pk = member.circle.pk)


# check if the member shall be remove
def removeCircleMember(circle, member):
    # remove when only all the members of a circle vote_in or vote_out
    circle_members = circle.circlemember_set.all().filter(is_member= True)

    vote_INs = member.circlemember_vote_in_set.all()
    vote_OUTs = member.circlemember_vote_out_set.all()

    if (vote_INs.count() + vote_OUTs.count()) == circle_members.count():
        # now that we have all members voted for this member,
        # we have to check if the member has the majority of vote out to be removed
        if vote_OUTs.count() >= circle_members.count()/2:
            return True

    return False

@login_required(login_url='EnterTheFloor')
def circleVoteOUT(request):
    if request.method == "POST":
        """ vote out the member.
            check if the vote does not have the majority, he/she has to leave the circle
            leaving means that that record has to be removed from circlemember """
        member = voteModels.CircleMember.objects.get(pk = request.POST.get('member'))
        voteOUT = voteModels.CircleMember_vote_out.objects.create(candidate = member, voter = request.user)
        voteOUT.save()

        if not majorityVotes(member.circle, member):
            # remove the member
            if removeCircleMember(member.circle, member):
                # now remove the member
                member.delete()

        messages.success(request,'Voted out', extra_tags='success')
        return redirect('circle', pk = member.circle.pk)


@login_required(login_url= 'EnterTheFloor')
def removeCircleMember(request):
    if request.method == 'POST':
        member = voteModels.CircleMember.objects.get(pk = request.POST.get('member'))
        member.delete()

        user = member.user
        user.users.userType = 0
        user.save()
        messages.error(request, 'removed...', extra_tags='success')
        return redirect('circle', pk = member.circle.pk)

    messages.error(request, 'something went wrong.', extra_tags='danger')
    return redirect('home')

def Can_be_delegate(member):
    """checks for member if it can be delegate.
    first, get the highest delegated member.
    then, check if the member has (50% + 1) votes.
    """
    result = False
    circlemembers = member.circle.circlemember_set.all()
    delegated = member.circlemember_put_farward_set.all()

    if delegated.count() > circlemembers.count()/2:
        result = True

    return result

@login_required(login_url='EnterTheFloor')
def putFarward(request):
    if request.method == 'POST':
        member = voteModels.CircleMember.objects.get(pk = request.POST.get('member'))
        # save one record in put_farward and
        delegated = voteModels.CircleMember_put_farward.objects.create(recipient = member, voter = request.user)
        delegated.save()
        # check if the member is eligible to be delegate

        if Can_be_delegate(member):
            # now make the delegated member the delegate
            circle = member.circle
            prev_delegate = circle.circlemember_set.filter(is_delegate = True).first()
            prev_delegate.is_delegate = False
            prev_delegate.save()

            member.is_delegate = True
            member.save()

        messages.success(request,"successfully voted", extra_tags='success')
        return redirect('circle', pk = member.circle.pk)


class Circle_members(LoginRequiredMixin, DetailView):
    model = voteModels.Circle
    template_name = 'vote/circle_members.html'


# this is for testing.

def creating():
    users_list = ('a','b','c','d','e','f','g','h','i','j','k','l','ab','ac','ae','ad',
    'ad','gd','fg','ge','dv','df','bg','hr','tf','vd','vd','dt','yu','nv','ze',
    'm','n','o','p','q','r','s','t','u','v','t','x','y','z')
    usersnames = []
    district = voteModels.Districts.objects.get(code = 'NY01')
    for i in users_list:
        # create user objects: legalName = i, entry_code = entry_code_generator, district = ny01
        user = User.objects.create(username = entry_code_generator())
        user.set_password('A123123a')
        user.save()
        user.users.legalName = i
        user.users.district = district
        user.save()
        usersnames.append(user.username)
    # export the usernames into a text files

    with open('usernames.txt', 'w') as fp:
        for i in usersnames:
            print(i)
            fp.writelines(i+"\n")
    print("done.....")


class Delete_CIRCLE(LoginRequiredMixin, DeleteView):
    model = voteModels.Circle
    template_name = "vote/circle_remove.html"
    success_url = '/home'

    def get_context_data(self, *args, **kwargs):
        data = super(Delete_CIRCLE, self).get_context_data(*args, **kwargs)
        data['page_title'] = 'Voter Page'
        return data


class CircleMemberContactAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        # check if the user has already a contact
        try:
            circle_member_contact = CircleMemberContact.objects.get(
                member__user=request.user)
            serializer = CircleMemberContactSerializer(circle_member_contact)

            return self.put(request, *args, **kwargs)
        except CircleMemberContact.DoesNotExist:
            # create a new contact
            serializer = CircleMemberContactSerializer(
                data=request.data, context={'request': request})
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            else:
                return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, *args, **kwargs):
        try:
            circle_member_contact = CircleMemberContact.objects.get(
                member__user=request.user)
        except CircleMemberContact.DoesNotExist:
            return Response({'error': 'CircleMemberContact not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = CircleMemberContactSerializer(
            circle_member_contact, data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
