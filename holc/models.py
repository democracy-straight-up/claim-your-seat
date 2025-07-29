import random
from django.db import models
from vote.models import Districts
from django.contrib.auth.models import User

def generate_unique_code():
    while True:
        code = random.randint(10, 99)
        if not HolcModel.objects.filter(code=code).exists():
            return code

def generate_unique_invitation_key():
    while True:
        invitation_key = random.randint(1000000000, 9999999999)
        if not HolcModel.objects.filter(invitation_key=invitation_key).exists():
            return invitation_key

class HolcModel(models.Model):
    code = models.PositiveIntegerField(unique=True, default=generate_unique_code)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    district = models.ForeignKey(Districts, on_delete=models.DO_NOTHING)
    invitation_key = models.PositiveBigIntegerField(unique=True, default=generate_unique_invitation_key)

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = generate_unique_code()
        if not self.invitation_key:
            self.invitation_key = generate_unique_invitation_key()
        super().save(*args, **kwargs)

    def __str__(self):
        return str(self.code)
    
    @property
    def is_active(self):
        # check if the member <= 12 and return true
        if 4 <= self.holcmembers_set.filter(is_member = True).count() <= 12:
            return True
        return False
    @property
    def member_count(self):
        return self.holcmembers_set.filter(is_member = True).count()


# for maximum f-link membership validation
from django.core.exceptions import ValidationError
class MaxMembershipReached(ValidationError):
    def __init__(self, message="Holc-Link has reached the max membership status. No longer accepting candidates."):
        super().__init__(message)

# the user can be changed to be Circle delegate only. but being a user is much better
class HolcMembers(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    holc = models.ForeignKey(HolcModel, on_delete=models.CASCADE)
    is_delegate = models.BooleanField(default=False)
    is_member = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_delegate', 'joined_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.holc.code}"
    
    def delete(self, using=None, keep_parents=False):
        # check if the user type is correct.
        self.user.users.userType = 'U4D3'
        self.user.users.save()
        super().delete(using, keep_parents)
    
    def save(self, *args, **kwargs):
        # check for max membership 
        if HolcMembers.objects.filter(is_member=True).count() > 12:
            raise MaxMembershipReached()  # Raise maxMember validation
        
        # on each first member, make the member the delegate member by default.
        if not self.pk and not self.holc.holcmembers_set.exists():
            self.is_delegate = True
            self.is_member = True
            self.user.users.userType = 'U4D4'
            self.user.users.save()
        
        super(HolcMembers, self).save(*args, **kwargs)
    
    def count_vote_out(self):
        return VoteOutHolcMember.objects.filter(candidate=self).count()

    def count_vote_in(self):
        return VoteInHolcMember.objects.filter(candidate=self).count()
      
    def count_put_forward(self):
        return PutForwardHolcMember.objects.filter(candidate=self).count()

    def check_for_majority(self): 
        total_members = HolcMembers.objects.filter(holc=self.holc).filter(is_member = True).count()
        majority_threshold = total_members // 2 + 1  # Majority is (total_members // 2 + 1)
        if self.count_vote_in() >= majority_threshold:
            self.is_member = True
            # set the user.users userType to U1D0
            self.save()
            self.user.users.userType = 'U4D3'
            self.user.users.save()
            return self
        
        return self

    def check_for_removing(self):
        total_members = HolcMembers.objects.filter(holc=self.holc).filter(is_member = True).count()
        majority_threshold = total_members // 2 + 1  # Majority is (total_members // 2 + 1)
        if self.count_vote_out() >= majority_threshold:
            self.user.users.userType = 'U3D2'
            self.user.users.save()
            self.user.save()
            super(HolcMembers, self).delete()

    def check_put_forward(self):
        total_members = HolcMembers.objects.filter(holc=self.holc).filter(is_member = True).count()
        majority_votes = total_members // 2 + 1  # Majority is (total_members // 2 + 1)
        if self.count_put_forward() >= majority_votes:
            # find the current delegate and set is_delegate false.
            current_delegate = HolcMembers.objects.filter(holc=self.holc).filter(is_delegate = True).first()
            current_delegate.is_delegate = False
            current_delegate.save()
            # set the user.users userType to U1D1
            current_delegate.user.users.userType = 'U4D3'
            current_delegate.user.users.save()
            # set the current member to delegate and set is_delegate true.
            self.is_delegate = True
            # set the self instance user.users userType to U2D2
            self.user.users.userType = 'U4D4'
            self.user.users.save()
            # save the current member instance
            self.save()


class VoteOutHolcMember(models.Model):
    voter = models.ForeignKey(User, on_delete=models.CASCADE)
    candidate = models.ForeignKey(HolcMembers, related_name='vote_outs', on_delete=models.CASCADE)
    holc = models.ForeignKey(HolcModel, on_delete=models.CASCADE, null=True, blank=True)
    voted_at = models.DateTimeField(auto_now_add=True)
    def save(self, *args, **kwargs):
        super(VoteOutHolcMember, self).save(*args, **kwargs)
        self.candidate.check_for_removing()


class VoteInHolcMember(models.Model):
    voter = models.ForeignKey(User, on_delete=models.CASCADE)
    candidate = models.ForeignKey(HolcMembers, related_name='vote_ins', on_delete=models.CASCADE)
    holc = models.ForeignKey(HolcModel, on_delete=models.CASCADE, null=True, blank=True)
    voted_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        super(VoteInHolcMember, self).save(*args, **kwargs)
        self.candidate.check_for_majority()
        return self 


class PutForwardHolcMember(models.Model):
    voter = models.ForeignKey(User, on_delete=models.CASCADE)
    candidate = models.ForeignKey(HolcMembers, related_name='put_forward', on_delete=models.CASCADE)
    holc = models.ForeignKey(HolcModel, on_delete=models.CASCADE, null=True, blank=True)
    voted_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        super(PutForwardHolcMember, self).save(*args, **kwargs)
        self.candidate.check_put_forward()
