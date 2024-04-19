from django.db import models
from django.contrib.auth.models import User

# District model (table) is for listing of all US districts
class Districts(models.Model):
    name = models.CharField(max_length=60, null=True, blank=True)
    # code is the 5-digit entry code for the district
    code = models.CharField(max_length=4, null=True, blank=True)

    # to loaddata into district tables, run the loaddata command for fixture
    # python loaddata <path>fileName.json

    class Meta:
        ordering = ['code']


    def __str__(self):
        return str(self.code)


#  the django user model has the follow feilds and i only need to add to it.
# firstName, lastName,userName, email, password, isActive,
class Users(models.Model):
    # the username is districtCode + 5-digit entry code
    user        = models.OneToOneField(User, on_delete=models.CASCADE)
    legalName   = models.CharField(max_length=60,null=True,blank=True)
    district    = models.ForeignKey(Districts, on_delete=models.DO_NOTHING, null=True, blank=True)
    # i am registered to vote in this district
    is_reg      = models.BooleanField(default=False)
    # this is for if the user is registered with conditional.
    verificationScore = models.SmallIntegerField(default=0,null=True, blank=True)
    address     = models.CharField(max_length=150, null=True, blank=True)
    # userType is the from 0 to 5.
    userType    = models.PositiveSmallIntegerField(default=0)
    VVAT_Number = models.CharField(max_length=15, null=True, blank=True)

    def __str__(self):
        return str(self.user.username)

import random
class Circle(models.Model):
    code            = models.CharField(max_length=5, unique=True)
    district        = models.ForeignKey(Districts, on_delete=models.CASCADE)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)
    invitation_code = models.CharField(max_length=10)
    FDel_election   =  models.BooleanField(default=False)

    def __str__(self):
        return str(self.code)

    @property
    def is_active(self):
        # check if the member <= 12 and return true
        if 6 <= self.circlemember_set.filter(is_member = True).count() <= 12:
            return True
        return False

class CircleMember(models.Model):
    user    = models.ForeignKey(User, on_delete=models.CASCADE)
    circle     = models.ForeignKey(Circle, on_delete=models.CASCADE)
    date_joined     = models.DateTimeField(auto_now_add=True)
    date_updated    = models.DateTimeField(auto_now=True)
    is_member       = models.BooleanField(default=False)
    is_delegate     = models.BooleanField(default=False)
    member_number   = models.PositiveSmallIntegerField(null=True, blank=True)

    def __str__(self):
        return str(self.user.username)

    class Meta:
        ordering = ['-is_delegate', 'date_joined']

    def check_for_majority(self):
        total_members = CircleMember.objects.filter(circle=self.circle).filter(is_member = True).count()
        majority_threshold = total_members // 2 + 1  # Majority is (total_members // 2 + 1)
        if self.count_vote_in() >= majority_threshold:
            self.is_member = True
            self.save()
            # Delete related CircleMember_vote_in instances
            CircleMember_vote_in.objects.filter(candidate=self).delete()

    def check_for_removing(self):
        total_members = CircleMember.objects.filter(circle=self.circle).filter(is_member = True).count()
        majority_threshold = total_members // 2 + 1  # Majority is (total_members // 2 + 1)
        if self.count_vote_out() >= majority_threshold:
            self.user.users.userType = 0
            self.user.users.save()
            self.delete()
            # set the deleted user.users userType to 0

    def check_put_forward(self):
        total_members = CircleMember.objects.filter(circle=self.circle).filter(is_member = True).count()
        majority_threshold = total_members // 2 + 1  # Majority is (total_members // 2 + 1)
        if self.count_put_forward() >= majority_threshold:
            # find the current delegate and set is_delegate false.
            current_delegate = CircleMember.objects.filter(circle=self.circle).filter(is_delegate = True).first()
            current_delegate.is_delegate = False
            current_delegate.save()

            # set the current member to delegate and set is_delegate true.
            self.is_delegate = True
            self.save()

            # Delete related CircleMember_put_forward instances
            CircleMember_put_forward.objects.filter(recipient=self).delete()

    def count_vote_in(self):
        return CircleMember_vote_in.objects.filter(candidate=self).count()
    def count_vote_out(self):
        return CircleMember_vote_out.objects.filter(candidate=self).count()
    def count_put_forward(self):
        return CircleMember_put_forward.objects.filter(recipient=self).count()

class CircleMember_vote_in(models.Model):
    candidate   = models.ForeignKey(CircleMember,related_name='voteIns', on_delete=models.CASCADE) #
    voter       = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        super(CircleMember_vote_in, self).save(*args, **kwargs)
        self.candidate.check_for_majority()

    def __str__(self):
        return str(self.voter) + '-'+ str(self.candidate)

class CircleMember_vote_out(models.Model):
    candidate   = models.ForeignKey(CircleMember, related_name='voteOuts', on_delete=models.CASCADE)
    voter       = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        super(CircleMember_vote_out, self).save(*args, **kwargs)
        self.candidate.check_for_removing()

    def __str__(self):
        return str(self.voter) + '-'+str(self.candidate)

class CircleMember_put_forward(models.Model):
    recipient   = models.ForeignKey(CircleMember,related_name='putForward', on_delete=models.CASCADE) # recipient
    voter       = models.ForeignKey(User, on_delete=models.CASCADE)  #
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        super(CircleMember_put_forward, self).save(*args, **kwargs)
        self.recipient.check_put_forward()

    def __str__(self):
        return str(self.voter) + '-'+str(self.recipient)


class CircleBackNForth(models.Model):
    circle = models.ForeignKey(Circle, on_delete=models.CASCADE)
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateTimeField(auto_created=True, auto_now_add=True)
    message = models.TextField(max_length=5000)


    def __str__(self) -> str:
        return str(self.sender.username) + " - " + str(self.circle.code)


class CircleStatus(models.Model):
    message = models.TextField()
    is_candidate = models.BooleanField(default=False)
    is_member = models.BooleanField(default=False)
    is_delegate = models.BooleanField(default=False)
    is_activeCircle =  models.BooleanField(default=False)

    def __str__(self) -> str:
        return str(self.message)


class CircleMemberContact(models.Model):
    circle = models.ForeignKey(Circle, on_delete=models.CASCADE)
    member = models.ForeignKey(CircleMember, on_delete=models.CASCADE)
    email = models.CharField(max_length=250)
    phone = models.CharField(max_length=250)

    def __str__(self) -> str:
        return str(self.member.user.username) + " - " + str(self.circle.code)
