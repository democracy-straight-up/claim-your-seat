from rest_framework.views import APIView
from .serializers import PodMemberContactSerializer
from .models import PodMemberContact
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
from vote.serializers import PodMemberContactSerializer
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
    podMember = False

    # get the user if he/she is a member of a pod
    if request.user.users.userType ==1:
        podMember = voteModels.PodMember.objects.get(user = request.user)

    time = request.user.date_joined
    if request.user.users.is_reg:
        from datetime import timedelta
        time = request.user.date_joined + timedelta(30)
    data={
        'pod': podMember,
        'title': 'Voter Page',
        'is_reg': time
    }
    return render(request, 'vote/VoterPage.html',data)   
    

# this the home page of a pod
class HouseKeepingPod(LoginRequiredMixin,DetailView):
    model = voteModels.Pod
    template_name = 'vote/HouseKeeping.html'

    def post(self,request, *args, **kwargs):
        pod = voteModels.Pod.objects.get(code = request.POST['pod'])
        pod.invitation_code = pod_invitation_generator()
        pod.save()
        messages.success(request, "The pod key has been updated.", extra_tags="success")
        return redirect('pod', pk=pod.pk)

        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # check if the user is the pod delegate
        pod = voteModels.Pod.objects.get(pk = self.kwargs['pk'])
        is_delegate = False
        condidate = pod.podmember_set.filter(is_member = False).first()
        for member in pod.podmember_set.all():
            if member.is_delegate and member.user == self.request.user:
                is_delegate = True

        # check the condidates vote in/out list and if the logged in user is on the list, set current_used_voted to true 
        current_user_voted = False
        if condidate:
            # vote in
            voteINs = condidate.podmember_vote_in_set.filter(voter = self.request.user)
            for voter in voteINs:
                if voter.voter == self.request.user:
                    current_user_voted = True

            # vote out
            voteINs = condidate.podmember_vote_out_set.filter(voter = self.request.user)
            for voter in voteINs:
                if voter.voter == self.request.user:
                    current_user_voted = True

        # if user is_member 
        # to check if the logged in user has voted for delegated
        current_user_delegated = False
        # pod_delegates = voteModels.PodMember_put_farward.objects.filter(delegated__pod = pod)
        # for i in pod_delegates:
        #     if i.voter == self.request.user:
        #         current_user_delegated = True
        
        context['title'] = "DSU - House Keeping Page"
        context['condidate'] = condidate
        context['is_delegate'] = is_delegate
        context['voted'] = current_user_voted
        context['delegated'] = current_user_delegated
        return context

def pod_invitation_generator():
    """
    this is the pod code generator. 
    It uses random and checks for the database. 
    return the code if it's not taken
    """
    import random
    code = str(random.randint(0,9999999999))
    is_exist = voteModels.Pod.objects.filter(invitation_code = code).exists()
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
    code = str(random.randint(1,99999))
    is_exist = voteModels.Pod.objects.filter(code = code).exists()
    
    if is_exist:
        pod_code_generator()
    return code

@login_required(login_url='EnterTheFloor')
def CreatePod(request):
    """
    this function creates a pod. 
    it set the userType to 1.
    it set the user as a delegate pod member
    """
    # create a pod
    pod = voteModels.Pod.objects.create(
        code = pod_code_generator(), 
        district = request.user.users.district,
        invitation_code = pod_invitation_generator()
    )
    pod.save()

    # set the userType attribute of the creator to 1
    user = request.user
    user.users.userType +=1
    user.save()

    # add the user to pod member as delegate
    pod_member_obj = voteModels.PodMember.objects.create(
        user = request.user, 
        pod = pod, 
        is_delegate = True,
        is_member = True,
        member_number = 1,
    )
    pod_member_obj.save()

    return redirect('pod', pk = pod.pk)


def pod_joining_validation(user,pod):
    """
    this function validate weather a user can enter a pod.
    It check if pod is active.
    It check if user is already a member
    It check if userType is 0
    """
    result = True
    # if not pod.is_active():
    #     print("pod is active")
    #     result = False

    podmembers = pod.podmember_set.all()
    if podmembers.count() >= 12:
        result = False

    if podmembers.filter(user = user):
        result = False
    
    if user.users.userType > 0:
        result = False

    return result


@login_required(login_url='EnterTheFloor')
def joinPod(request):
    form = voteForms.JoinPodMemberForm()
    if request.method =="POST":
        form = voteForms.JoinPodMemberForm(request.POST or None)
        if form.is_valid():
            invitationCode = form.cleaned_data.get('invitationCode').upper()
            # check if pod exist
            pods = voteModels.Pod.objects.filter(invitation_code = invitationCode)
            if pods.exists():
                # check if user can join the pod
                if pod_joining_validation(request.user, pods.first()):
                    podMember = voteModels.PodMember.objects.create(
                        user = request.user,
                        pod = pods.first(),
                        is_member = False,
                        is_delegate = False,
                        member_number = pods.first().podmember_set.count()+1
                    )
                    podMember.save()

                    messages.success(
                        request, 
                        ('In order to become a member of this Pod you need to be'
                         '‘voted in’ by a majority of the existing members. ' 
                         'You can wait and see if you are voted in, or you can contact '
                         'your F-Del IRL and ask them to start a vote among existing members.'),
                        extra_tags="success"
                    )
                    return redirect('pod', pk = pods.first().pk)
                else:
                    # else of pod is active 
                    messages.error(request, 'Pod is not accepting member anymore', extra_tags='danger')
                    return redirect('joinPod')
            else:
                # else of pod_obj
                messages.error(request, 'there is not pod with this code.',extra_tags='danger')
                return redirect('joinPod')
        else:  
            # else of form is_valid
            return render(request,'vote/joinPod.html', {'form':form})

    return render(request,'vote/joinPod.html', {'form':form})


def majorityVotes(pod, member):
    pod_members = pod.podmember_set.filter(is_member = True)
    member_vote = member.podmember_vote_in_set.all()
    if member_vote.count() > (pod_members.count()/2):
        return True
    return False


# vote members in a pod (IN, OUT)
@login_required(login_url='EnterTheFloor')
def podVoteIN(request):
    if request.method == "POST":
        """vote the member in to become a member of the pod
            check if the vote in is 50% + 1 to become the member (majority votes)
            make sure that members can only vote in/out once"""
        member = voteModels.PodMember.objects.get(pk = request.POST.get('member'))
        voteIN = voteModels.PodMember_vote_in.objects.create(condidate = member, voter = request.user)
        voteIN.save()
        # check if he/she has got the majority votes
        if majorityVotes(member.pod, member):
            member.is_member = True
            member.save()
            # set the member.user.users.userType to 1 as it becomes the member in a pod.
            userType = member.user
            userType.users.userType = 1
            userType.save()

        messages.success(request,'Voted in', extra_tags='success')
        return redirect('pod', pk = member.pod.pk)


# check if the member shall be remove
def removePodMember(pod, member):
    # remove when only all the members of a pod vote_in or vote_out
    pod_members = pod.podmember_set.all().filter(is_member= True)

    vote_INs = member.podmember_vote_in_set.all()
    vote_OUTs = member.podmember_vote_out_set.all()

    if (vote_INs.count() + vote_OUTs.count()) == pod_members.count():
        # now that we have all members voted for this member, 
        # we have to check if the member has the majority of vote out to be removed
        if vote_OUTs.count() >= pod_members.count()/2:
            return True
            
    return False

@login_required(login_url='EnterTheFloor')
def podVoteOUT(request):
    if request.method == "POST":
        """ vote out the member. 
            check if the vote does not have the majority, he/she has to leave the pod
            leaving means that that record has to be removed from podmember """
        member = voteModels.PodMember.objects.get(pk = request.POST.get('member'))
        voteOUT = voteModels.PodMember_vote_out.objects.create(condidate = member, voter = request.user)
        voteOUT.save()

        if not majorityVotes(member.pod, member):
            # remove the member
            if removePodMember(member.pod, member):
                # now remove the member
                member.delete()
            
        messages.success(request,'Voted out', extra_tags='success')
        return redirect('pod', pk = member.pod.pk)


@login_required(login_url= 'EnterTheFloor')
def removePodMember(request):
    if request.method == 'POST':
        member = voteModels.PodMember.objects.get(pk = request.POST.get('member'))
        member.delete()
        
        user = member.user
        user.users.userType = 0
        user.save()
        messages.error(request, 'removed...', extra_tags='success')
        return redirect('pod', pk = member.pod.pk)

    messages.error(request, 'something went wrong.', extra_tags='danger')
    return redirect('home')

def Can_be_delegate(member):
    """checks for member if it can be delegate.
    first, get the highest delegated member.
    then, check if the member has (50% + 1) votes. 
    """
    result = False
    podmembers = member.pod.podmember_set.all()
    delegated = member.podmember_put_farward_set.all()

    if delegated.count() > podmembers.count()/2:
        result = True

    return result

@login_required(login_url='EnterTheFloor')
def putFarward(request):
    if request.method == 'POST':
        member = voteModels.PodMember.objects.get(pk = request.POST.get('member'))
        # save one record in put_farward and 
        delegated = voteModels.PodMember_put_farward.objects.create(recipient = member, voter = request.user)
        delegated.save()
        # check if the member is eligible to be delegate

        if Can_be_delegate(member):
            # now make the delegated member the delegate
            pod = member.pod
            prev_delegate = pod.podmember_set.filter(is_delegate = True).first()
            prev_delegate.is_delegate = False
            prev_delegate.save()

            member.is_delegate = True
            member.save()
        
        messages.success(request,"successfully voted", extra_tags='success')
        return redirect('pod', pk = member.pod.pk)


class Pod_members(LoginRequiredMixin, DetailView):
    model = voteModels.Pod
    template_name = 'vote/pod_members.html'


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


class Delete_POD(LoginRequiredMixin, DeleteView):
    model = voteModels.Pod
    template_name = "vote/pod_remove.html"
    success_url = '/home'

    def get_context_data(self, *args, **kwargs):
        data = super(Delete_POD, self).get_context_data(*args, **kwargs)
        data['page_title'] = 'Voter Page'
        return data


class PodMemberContactAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        # check if the user has already a contact
        try:
            pod_member_contact = PodMemberContact.objects.get(
                member__user=request.user)
            serializer = PodMemberContactSerializer(pod_member_contact)
            
            return self.put(request, *args, **kwargs)
        except PodMemberContact.DoesNotExist:
            # create a new contact
            serializer = PodMemberContactSerializer(
                data=request.data, context={'request': request})
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            else:
                return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, *args, **kwargs):
        try:
            pod_member_contact = PodMemberContact.objects.get(
                member__user=request.user)
        except PodMemberContact.DoesNotExist:
            return Response({'error': 'PodMemberContact not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = PodMemberContactSerializer(
            pod_member_contact, data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
