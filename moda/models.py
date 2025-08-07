import random
from django.db import models
from vote.models import Districts
from django.contrib.auth.models import User

def generate_unique_code():
    while True:
        code = random.randint(100, 999)
        if not ModaModel.objects.filter(code=code).exists():
            return code

def generate_unique_invitation_key():
    while True:
        invitation_key = random.randint(1000000000, 9999999999)
        if not ModaModel.objects.filter(invitation_key=invitation_key).exists():
            return invitation_key

class ModaModel(models.Model):
    code = models.PositiveIntegerField(unique=True, default=generate_unique_code)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    district = models.ForeignKey(Districts, on_delete=models.DO_NOTHING)
    invitation_key = models.PositiveBigIntegerField(unique=True, default=generate_unique_invitation_key)
    status = models.BooleanField(default=False, null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = generate_unique_code()
        if not self.invitation_key:
            self.invitation_key = generate_unique_invitation_key()
        super().save(*args, **kwargs)

    def __str__(self):
        return str(self.code)
    
    def delete(self):
        members = self.modamembers_set.all()
        for member in members:
            member.user.users.userType ="U2D2"
            member.user.users.verificationScore = 100
            member.user.users.save()
            member.delete()


    @property
    def is_active(self):
        # check if the member <= 12 and return true
        member_count = self.modamembers_set.filter(is_member = True).count()
        is_currently_active = 3 <= member_count <= 12
        if is_currently_active:
            if(self.status == False):
                self.status = True
                self.save()
                self._update_member_verification_scores(1000)
            return True
        else:
            if(self.status==True):
                self.status = False
                self.save()
                self._update_member_verification_scores(100)
            return False
    
    def _update_member_verification_scores(self, score):
        """Helper method to update verification scores for all sec_del members"""
        members = self.modamembers_set.filter(is_member=True)
        for member in members:
            member.user.users.verificationScore = score
            member.user.users.save()


    @property
    def member_count(self):
        return self.modamembers_set.filter(is_member = True).count()


# for maximum f-link membership validation
from django.core.exceptions import ValidationError
class MaxMembershipReached(ValidationError):
    def __init__(self, message="S-Link has reached the max membership status. No longer accepting candidates."):
        super().__init__(message)

# the user can be changed to be Circle delegate only. but being a user is much better
class ModaMembers(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    moda = models.ForeignKey(ModaModel, on_delete=models.CASCADE)
    is_delegate = models.BooleanField(default=False)
    is_member = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_delegate', 'joined_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.moda.code}"
    
    def delete(self, *args, **kwargs):
        # set the userType to U0D0 and verification score to 0
        self.user.users.userType = "U2D2"
        self.user.users.verificationScore = 100
        self.user.users.save()
        super().delete(*args, **kwargs)

        # once the member is removed, check the grou status and update the status and that will update the 
        # members connection scores (verification score) as well.
        if self.moda:
            self.moda.is_active
            
    def delete(self, *args, **kwargs):
        # set the userType to U0D0 and verification score to 0
        self.user.users.userType = "U2D2"
        self.user.users.verificationScore = 100
        self.user.users.save()
        super().delete(*args, **kwargs)

        # once the member is removed, check the grou status and update the status and that will update the 
        # members connection scores (verification score) as well.
        if self.moda:
            self.moda.is_active

    def save(self, *args, **kwargs):
        # check for max membership 
        if ModaMembers.objects.filter(is_member=True).count() > 12:
            raise MaxMembershipReached()  # Raise maxMember validation
        
        # on each first member, make the member the delegate member by default.
        if not self.pk and not self.moda.modamembers_set.exists():
            self.is_delegate = True
            self.is_member = True
            self.user.users.userType = 'U3D3'
            self.user.users.save()
        
        super(ModaMembers, self).save(*args, **kwargs)
    
    def count_vote_out(self):
        return VoteOutModaMember.objects.filter(candidate=self).count()

    def count_vote_in(self):
        return VoteInModaMember.objects.filter(candidate=self).count()
      
    def count_put_forward(self):
        return PutFarwardModaMember.objects.filter(candidate=self).count()

    def check_for_majority(self): 
        total_members = ModaMembers.objects.filter(moda=self.moda).filter(is_member = True).count()
        majority_threshold = total_members // 2 + 1  # Majority is (total_members // 2 + 1)
        if self.count_vote_in() >= majority_threshold:
            self.is_member = True
            # set the user.users userType to U3D2
            self.save()
            self.user.users.userType = 'U3D2'
            self.user.users.save()
            return self
        
        return self

    def check_for_removing(self):
        total_members = ModaMembers.objects.filter(moda=self.moda).filter(is_member = True).count()
        majority_threshold = total_members // 2 + 1  # Majority is (total_members // 2 + 1)
        if self.count_vote_out() >= majority_threshold:
            self.user.users.userType = 'U2D2'
            self.user.users.verificationScore = 100
            self.user.users.save()
            self.delete()

    def check_put_farward(self):
        total_members = ModaMembers.objects.filter(moda=self.moda).filter(is_member = True).count()
        majority_votes = total_members // 2 + 1  # Majority is (total_members // 2 + 1)
        if self.count_put_forward() >= majority_votes:
            # find the current delegate and set is_delegate false.
            current_delegate = ModaMembers.objects.filter(moda=self.moda).filter(is_delegate = True).first()
            current_delegate.is_delegate = False
            current_delegate.save()
            # set the user.users userType to U1D1
            current_delegate.user.users.userType = 'U3D2'
            current_delegate.user.users.save()
            # set the current member to delegate and set is_delegate true.
            self.is_delegate = True
            # set the self instance user.users userType to U2D2
            self.user.users.userType = 'U3D3'
            self.user.users.save()
            # save the current member instance
            self.save()


class VoteOutModaMember(models.Model):
    voter = models.ForeignKey(User, on_delete=models.CASCADE)
    candidate = models.ForeignKey(ModaMembers, related_name='vote_outs', on_delete=models.CASCADE)
    moda = models.ForeignKey(ModaModel, on_delete=models.CASCADE, null=True, blank=True)
    voted_at = models.DateTimeField(auto_now_add=True)
    def save(self, *args, **kwargs):
        super(VoteOutModaMember, self).save(*args, **kwargs)
        self.candidate.check_for_removing()


class VoteInModaMember(models.Model):
    voter = models.ForeignKey(User, on_delete=models.CASCADE)
    candidate = models.ForeignKey(ModaMembers, related_name='vote_ins', on_delete=models.CASCADE)
    moda = models.ForeignKey(ModaModel, on_delete=models.CASCADE, null=True, blank=True)
    voted_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        super(VoteInModaMember, self).save(*args, **kwargs)
        self.candidate.check_for_majority()
        return self 


class PutFarwardModaMember(models.Model):
    voter = models.ForeignKey(User, on_delete=models.CASCADE)
    candidate = models.ForeignKey(ModaMembers, related_name='put_farward', on_delete=models.CASCADE)
    moda = models.ForeignKey(ModaModel, on_delete=models.CASCADE, null=True, blank=True)
    voted_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        super(PutFarwardModaMember, self).save(*args, **kwargs)
        self.candidate.check_put_farward()
