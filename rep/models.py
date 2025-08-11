from django.db import models

# Create your models here.
import random
from django.db import models
from vote.models import Districts
from django.contrib.auth.models import User

def generate_unique_code():
    while True:
        code = random.randint(0, 9)
        if not DistrictCouncil.objects.filter(code=code).exists():
            return code

def generate_unique_invitation_key():
    while True:
        invitation_key = random.randint(1000000000, 9999999999)
        if not DistrictCouncil.objects.filter(invitation_key=invitation_key).exists():
            return invitation_key

class DistrictCouncil(models.Model):
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
        members = self.districtcouncilmembers_set.all()
        for member in members:
            member.user.users.userType ="U4D4"
            member.user.users.verificationScore = 10000
            member.user.users.save()
            member.delete()

    @property
    def is_active(self):
        # check if the member <= 12 and return true
        member_count = self.districtcouncilmembers_set.filter(is_member = True).count()
        is_currently_active = 3 <= member_count <= 10
        if is_currently_active:
            if(self.status == False):
                self.status = True
                self.save()
                self._update_member_verification_scores(100000)
            return True
        else:
            if(self.status==True):
                self.status = False
                self.save()
                self._update_member_verification_scores(10000)
            return False
    
    def _update_member_verification_scores(self, score):
        """Helper method to update verification scores for all sec_del members"""
        members = self.districtcouncilmembers_set.filter(is_member=True)
        for member in members:
            member.user.users.verificationScore = score
            member.user.users.save()

    @property
    def member_count(self):
        return self.districtcouncilmembers_set.filter(is_member = True).count()


# for maximum f-link membership validation
from django.core.exceptions import ValidationError
class MaxMembershipReached(ValidationError):
    def __init__(self, message="District Council has reached the max membership status. No longer accepting candidates."):
        super().__init__(message)

# the user can be changed to be Circle delegate only. but being a user is much better
class DistrictCouncilMembers(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    district_council = models.ForeignKey(DistrictCouncil, on_delete=models.CASCADE)
    is_delegate = models.BooleanField(default=False)
    is_member = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_delegate', 'joined_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.district_council.code}"

    def delete(self, *args, **kwargs):
        # set the userType to U0D0 and verification score to 0
        self.user.users.userType = "U4D4"
        self.user.users.verificationScore = 10000
        self.user.users.save()
        super().delete(*args, **kwargs)

        if self.district_council:
            self.district_council.is_active
    
    def save(self, *args, **kwargs):
        # check for max membership 
        if DistrictCouncilMembers.objects.filter(is_member=True).count() > 10:
            raise MaxMembershipReached()  # Raise maxMember validation
        
        # on each first member, make the member the delegate member by default.
        if not self.pk and not self.district_council.districtcouncilmembers_set.exists():
            self.is_delegate = True
            self.is_member = True
            self.user.users.userType = 'U5D5'
            self.user.users.save()
        
        super(DistrictCouncilMembers, self).save(*args, **kwargs)
        
        # Create contact if member becomes a member (either first delegate or through voting)
        if self.is_member:
            DistrictCouncilMemberContact.objects.get_or_create(
                member=self,
                defaults={
                    'district_council': self.district_council,
                    'legal_name': self.user.users.legalName,
                    'address': self.user.users.address,
                    'email': self.user.email,
                    'contact_rules': 'Please contact during regular hours.',
                    'contact': 'Available via email.',
                }
            )
    
    def count_vote_out(self):
        return VoteOutDistrictCouncilMember.objects.filter(candidate=self).count()

    def count_vote_in(self):
        return VoteInDistrictCouncilMember.objects.filter(candidate=self).count()
      
    def count_put_forward(self):
        return PutForwardDistrictCouncilMember.objects.filter(candidate=self).count()

    def check_for_majority(self): 
        total_members = DistrictCouncilMembers.objects.filter(district_council=self.district_council).filter(is_member = True).count()
        majority_threshold = total_members // 2 + 1  # Majority is (total_members // 2 + 1)
        if self.count_vote_in() >= majority_threshold:
            self.is_member = True
            # set the user.users userType 
            self.save()
            self.user.users.userType = 'U5D4'
            self.user.users.save()
            
            # Create contact info when member is voted in
            DistrictCouncilMemberContact.objects.get_or_create(
                member=self,
                defaults={
                    'district_council': self.district_council,
                    'legal_name': self.user.users.legalName,
                    'address': self.user.users.address,
                    'email': self.user.email,
                    'contact_rules': 'Please contact during regular hours.',
                    'contact': 'Available via email.',
                }
            )
            return self
        
        return self

    def check_for_removing(self):
        total_members = DistrictCouncilMembers.objects.filter(district_council=self.district_council).filter(is_member = True).count()
        majority_threshold = total_members // 2 + 1  # Majority is (total_members // 2 + 1)
        if self.count_vote_out() >= majority_threshold:
            self.user.users.userType = 'U4D4'
            self.user.users.verificationScore = 10000
            self.user.users.save()
            super(DistrictCouncilMembers,self).delete()
        

    def check_put_forward(self):
        total_members = DistrictCouncilMembers.objects.filter(district_council=self.district_council).filter(is_member = True).count()
        majority_votes = total_members // 2 + 1  # Majority is (total_members // 2 + 1)
        if self.count_put_forward() >= majority_votes:
            # find the current delegate and set is_delegate false.
            current_delegate = DistrictCouncilMembers.objects.filter(district_council=self.district_council).filter(is_delegate = True).first()
            old_delegate_user = current_delegate.user
            
            current_delegate.is_delegate = False
            current_delegate.save()
            # set the user.users userType to U1D1
            current_delegate.user.users.userType = 'U5D4'
            current_delegate.user.users.save()
            # set the current member to delegate and set is_delegate true.
            self.is_delegate = True
            # set the self instance user.users userType to U2D2
            self.user.users.userType = 'U5D5'
            self.user.users.save()
            # save the current member instance
            self.save()
            
            # Trigger succession line for higher groups (none for DistrictCouncil as it's top level)
            try:
                from succession_line import succession_manager
                succession_manager.handle_delegate_change(
                    'districtcouncil', 
                    old_delegate_user, 
                    self.user, 
                    self.district_council
                )
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error in succession line: {str(e)}")


class VoteOutDistrictCouncilMember(models.Model):
    voter = models.ForeignKey(User, on_delete=models.CASCADE)
    candidate = models.ForeignKey(DistrictCouncilMembers, related_name='vote_outs', on_delete=models.CASCADE)
    district_council = models.ForeignKey(DistrictCouncil, on_delete=models.CASCADE, null=True, blank=True)
    voted_at = models.DateTimeField(auto_now_add=True)
    def save(self, *args, **kwargs):
        super(VoteOutDistrictCouncilMember, self).save(*args, **kwargs)
        self.candidate.check_for_removing()


class VoteInDistrictCouncilMember(models.Model):
    voter = models.ForeignKey(User, on_delete=models.CASCADE)
    candidate = models.ForeignKey(DistrictCouncilMembers, related_name='vote_ins', on_delete=models.CASCADE)
    district_council = models.ForeignKey(DistrictCouncil, on_delete=models.CASCADE, null=True, blank=True)
    voted_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        super(VoteInDistrictCouncilMember, self).save(*args, **kwargs)
        self.candidate.check_for_majority()
        return self 


class PutForwardDistrictCouncilMember(models.Model):
    voter = models.ForeignKey(User, on_delete=models.CASCADE)
    candidate = models.ForeignKey(DistrictCouncilMembers, related_name='put_forward', on_delete=models.CASCADE)
    district_council = models.ForeignKey(DistrictCouncil, on_delete=models.CASCADE, null=True, blank=True)
    voted_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        super(PutForwardDistrictCouncilMember, self).save(*args, **kwargs)
        self.candidate.check_put_forward()


class DistrictCouncilMemberContact(models.Model):
    member = models.OneToOneField(
        'DistrictCouncilMembers', 
        on_delete=models.CASCADE, 
        related_name='district_contact'
    )
    district_council = models.ForeignKey('DistrictCouncil', on_delete=models.CASCADE)
    
    # Contact information
    legal_name = models.CharField(max_length=255, blank=True, null=True)
    contact_rules = models.TextField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    contact = models.TextField(blank=True, null=True)
    phone = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(max_length=255, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.legal_name} - {self.member}"
    
    class Meta:
        ordering = ['created_at']
