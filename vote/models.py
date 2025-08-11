from django.db import models
from django.contrib.auth.models import User

# District model (table) is for listing of all US districts
class Districts(models.Model):
    name = models.CharField(max_length=60, null=True, blank=True)
    # code is the 5-digit entry code for the district
    code = models.CharField(max_length=4, null=True, blank=True, unique=True)

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
    # verificationScore is named ConnectionScore everywhere
    verificationScore = models.PositiveIntegerField(default=0,null=True, blank=True)
    address     = models.CharField(max_length=150, null=True, blank=True)
    userType = models.CharField(max_length=4, default='U0D0')
    VVAT_Number = models.CharField(max_length=15, null=True, blank=True)

    def __str__(self):
        return str(self.user.username)

class Group(models.Model):
    code            = models.CharField(max_length=5, unique=True)
    district        = models.ForeignKey(Districts, on_delete=models.CASCADE)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)
    invitation_code = models.CharField(max_length=10)
    FDel_election   = models.BooleanField(default=False)
    status          = models.BooleanField(default=False, null=True, blank=True)
    group_type = models.IntegerField()
    parent_group = models.ForeignKey('self', null=True,blank=True,  on_delete=models.CASCADE)

    def __str__(self):
        return str(self.code)

    @property
    def is_active(self):
        # check if the member <= 12 and return true
        member_count = self.groupmember_set.filter(is_member = True).count()
        is_currently_active = 3 <= member_count <= 12
        if is_currently_active:
            if(self.status == False):
                self.status = True
                self.save()
                self._update_member_verification_scores(10)
            return True
        else:
            if(self.status==True):
                self.status = False
                self.save()
                self._update_member_verification_scores(0)
            return False

    def delete(self):
        members = self.groupmember_set.all()
        for member in members:
            member.user.users.userType ="U0D0"
            member.user.users.verificationScore = 0
            member.user.users.save()
            member.delete()


    def _update_member_verification_scores(self, score):
        """Helper method to update verification scores for all group members"""
        members = self.groupmember_set.filter(is_member=True)
        for member in members:
            member.user.users.verificationScore = score
            member.user.users.save()

    
    @property
    def member_count(self):
        return self.groupmember_set.filter(is_member = True).count()


# for maximum f-link membership validation
from django.core.exceptions import ValidationError
class MaxMembershipReached(ValidationError):
    def __init__(self, message="Circle has reached the max membership status. No longer accepting candidates."):
        super().__init__(message)

class GroupMember(models.Model):
    user    = models.ForeignKey(User, on_delete=models.CASCADE)
    group     = models.ForeignKey(Group, on_delete=models.CASCADE)
    is_member       = models.BooleanField(default=False)
    date_joined     = models.DateTimeField(auto_now_add=True)
    date_updated    = models.DateTimeField(auto_now=True)
    member_type = models.CharField(max_length=10, null=True, blank=True)
    is_delegate     = models.BooleanField(default=False)
    member_number   = models.PositiveSmallIntegerField(null=True, blank=True)

    def __str__(self):
        return str(self.user.username)

    class Meta:
        ordering = ['-is_delegate', 'date_joined']

    def save(self, *args, **kwargs):
        # check for max membership 
        if GroupMember.objects.filter(is_member=True, group = self.group).count() > 12:
            raise MaxMembershipReached()  # Raise maxMember validation
        # on each first member, make the member the delegate member by default.
        if not self.pk and not self.group.groupmember_set.exists():
            self.is_delegate = True
            self.is_member = True
            self.user.users.userType = 'U1D1'
            self.user.users.save()


        super(GroupMember, self).save(*args, **kwargs)
        if self.group:
            self.group.is_active

        if self.is_member:
            ContactInfo.objects.get_or_create(
                member=self,
                legal_name=self.user.users.legalName,
                address=self.user.users.address,
                email=self.user.email,
                group=self.group
            )

    def delete(self, *args, **kwargs):
        # set the userType to U0D0 and verification score to 0
        self.user.users.userType = "U0D0"
        self.user.users.verificationScore = 0
        self.user.users.save()
        super().delete(*args, **kwargs)

        # once the member is removed, check the grou status and update the status and that will update the 
        # members connection scores (verification score) as well.
        if self.group:
            self.group.is_active

        
    def check_for_majority(self): 
        total_members = GroupMember.objects.filter(group=self.group).filter(is_member = True).count()
        majority_threshold = total_members // 2 + 1  # Majority is (total_members // 2 + 1)
        if self.count_vote_in() >= majority_threshold:
            self.is_member = True
            # set the user.users userType to U1D0 (member, not delegate)
            self.user.users.userType = 'U1D0'
            
            # Set verification score based on group status
            if self.group.is_active:
                self.user.users.verificationScore = 10
            # else:
            #     self.user.users.verificationScore = 2
                
            self.user.users.save()
            self.save()
            # Delete related CircleMember_vote_in instances
            CircleMember_vote_in.objects.filter(recipient=self).delete()

            # create an instance of the contact info
            ContactInfo.objects.get_or_create(
                member=self,
                legal_name=self.user.users.legalName,
                address=self.user.users.address,
                email=self.user.email,
                group=self.group
            )


    def check_for_removing(self):
        total_members = GroupMember.objects.filter(group=self.group).filter(is_member = True).count()
        majority_threshold = total_members // 2 + 1  # Majority is (total_members // 2 + 1)
        if self.count_vote_out() >= majority_threshold:
            # Delete related vote instances
            CircleMember_vote_out.objects.filter(candidate=self).delete()
            
            # Delete the member - this will trigger the custom delete method
            self.delete()


    def check_put_farward(self):
        total_members = GroupMember.objects.filter(group=self.group).filter(is_member = True).count()
        majority_threshold = total_members // 2 + 1  # Majority is (total_members // 2 + 1)
        if self.count_put_forward() >= majority_threshold:

            # find the current delegate and set is_delegate false.
            current_delegate = GroupMember.objects.filter(group=self.group).filter(is_delegate = True).first()
            old_delegate_user = current_delegate.user
            
            current_delegate.is_delegate = False
            current_delegate.save()
            # set the current delegate user.users userType to U1D0
            current_delegate.user.users.userType = 'U1D0'
            current_delegate.user.users.save()
            # set the current member to delegate and set is_delegate true.
            self.is_delegate = True
            self.user.users.userType = 'U1D1'
            self.user.users.save()
            self.save()
            # Delete related CircleMember_put_forward instances
            CircleMember_put_forward.objects.filter(recipient=self).delete()
            
            # Trigger succession line for higher groups
            try:
                from succession_line import succession_manager
                succession_manager.handle_delegate_change(
                    'circle', 
                    old_delegate_user, 
                    self.user, 
                    self.group
                )
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error in succession line: {str(e)}")

    def count_vote_in(self):
        return CircleMember_vote_in.objects.filter(recipient=self).count()
    def count_vote_out(self):
        return CircleMember_vote_out.objects.filter(candidate=self).count()
    def count_put_forward(self):
        return CircleMember_put_forward.objects.filter(recipient=self).count()

class CircleBackNForth(models.Model):
    circle = models.ForeignKey(Group, on_delete=models.CASCADE)
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateTimeField(auto_created=True, auto_now_add=True)
    message = models.TextField(max_length=5000)
    handle = models.PositiveSmallIntegerField(default=0)

    def __str__(self) -> str:
        return str(self.sender.username) + " - " + str(self.circle.code)

class CircleMember_vote_in(models.Model):
    recipient   = models.ForeignKey(GroupMember,related_name='voteIns', on_delete=models.CASCADE, default=False)
    voter       = models.ForeignKey(User, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        super(CircleMember_vote_in, self).save(*args, **kwargs)
        self.recipient.check_for_majority()

    def __str__(self):
        return str(self.voter) + '-'+ str(self.recipient)

class CircleMember_vote_out(models.Model):
    candidate   = models.ForeignKey(GroupMember, related_name='voteOuts', on_delete=models.CASCADE)
    voter       = models.ForeignKey(User, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        super(CircleMember_vote_out, self).save(*args, **kwargs)
        self.candidate.check_for_removing()

    def __str__(self):
        return str(self.voter) + '-'+str(self.candidate)

class CircleMember_put_forward(models.Model):
    recipient   = models.ForeignKey(GroupMember,related_name='putForward', on_delete=models.CASCADE, default=False) # recipient
    voter       = models.ForeignKey(User, on_delete=models.CASCADE)  #
    group = models.ForeignKey(Group, on_delete=models.CASCADE, null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        super(CircleMember_put_forward, self).save(*args, **kwargs)
        self.recipient.check_put_farward()

    def __str__(self):
        return str(self.voter) + '-'+str(self.recipient)

class CircleStatus(models.Model):
    message = models.TextField()
    is_candidate = models.BooleanField(default=False)
    is_member = models.BooleanField(default=False)
    is_delegate = models.BooleanField(default=False)
    is_activeCircle =  models.BooleanField(default=False)

    def __str__(self) -> str:
        return str(self.message)

#stores required fields in the contacts table
class ContactInfo(models.Model):
    member = models.OneToOneField(GroupMember, null=True, blank=True, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    legal_name = models.CharField(max_length=255, null=True, blank=True)
    phone = models.CharField(max_length=15, null=True, blank=True)
    email = models.EmailField(max_length=255, blank=True, null=True)
    contact_rules = models.TextField(null=True, blank=True)
    contact = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)

    def __str__(self):
        return str(self.member)

    class Meta:
        ordering = ['created_at']


class SuccessionLog(models.Model):
    """
    Log entry for each succession line event.
    """
    # Event details
    trigger_group_type = models.CharField(max_length=20, help_text="Type of group where change originated")
    trigger_group_id = models.PositiveIntegerField(help_text="ID of group where change originated")
    old_delegate_username = models.CharField(max_length=150, help_text="Username of old delegate")
    new_delegate_username = models.CharField(max_length=150, help_text="Username of new delegate")
    
    # Timestamp
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Status
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('partial', 'Partial Success'),
        ('failed', 'Failed'),
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='success')
    error_message = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['trigger_group_type']),
            models.Index(fields=['old_delegate_username']),
        ]
    
    def __str__(self):
        return f"Succession {self.trigger_group_type} {self.old_delegate_username}->{self.new_delegate_username}"


class SuccessionAction(models.Model):
    """
    Individual action taken during succession process.
    """
    log = models.ForeignKey(SuccessionLog, on_delete=models.CASCADE, related_name='actions')
    
    # Action details
    ACTION_CHOICES = [
        ('removed', 'Removed from group'),
        ('promoted', 'Promoted to delegate'),
        ('demoted', 'Demoted from delegate'),
        ('cascade_removal', 'Cascade removal due to ineligibility'),
        ('user_type_update', 'Updated user type after removal'),
    ]
    action = models.CharField(max_length=25, choices=ACTION_CHOICES)
    
    # Target details
    target_group_type = models.CharField(max_length=20)
    target_group_id = models.PositiveIntegerField(null=True, blank=True)
    target_username = models.CharField(max_length=150)
    
    # Context
    was_delegate = models.BooleanField(default=False)
    promotion_method = models.CharField(max_length=50, blank=True, null=True, 
                                      help_text="How delegate was chosen (votes, earliest_joined, etc)")
    
    # Timestamp
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['timestamp']
    
    def __str__(self):
        return f"{self.action} {self.target_username} in {self.target_group_type}"


class DelegateEligibilityCheck(models.Model):
    """
    Track eligibility checks during succession.
    """
    log = models.ForeignKey(SuccessionLog, on_delete=models.CASCADE, related_name='eligibility_checks')
    
    # Check details
    username = models.CharField(max_length=150)
    target_group_type = models.CharField(max_length=20)
    required_lower_group_type = models.CharField(max_length=20, blank=True, null=True)
    
    # Result
    is_eligible = models.BooleanField()
    reason = models.CharField(max_length=200, blank=True, null=True)
    
    # Timestamp
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['timestamp']
    
    def __str__(self):
        status = "eligible" if self.is_eligible else "ineligible"
        return f"{self.username} {status} for {self.target_group_type}"
    
