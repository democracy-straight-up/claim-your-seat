import random
from django.db import models, transaction
from succession_notifications import (
    notify_delegate_change,
    notify_delegate_promotion_after_removal,
    post_succession_update,
    user_display_name,
)
from succession_helpers import remove_dependent_memberships
from vote.models import Districts
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

# imports for the dummy model
from api.utils import entry_code_generator 
from vote import models as vote_models

def generate_unique_code():
    while True:
        code = random.randint(1000, 9999)
        if not SecDelModel.objects.filter(code=code).exists():
            return code

def generate_unique_invitation_key():
    while True:
        invitation_key = random.randint(1000000000, 9999999999)
        if not SecDelModel.objects.filter(invitation_key=invitation_key).exists():
            return invitation_key

class SecDelModel(models.Model):
    code = models.PositiveIntegerField(unique=True, default=generate_unique_code)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    district = models.ForeignKey(Districts, on_delete=models.CASCADE)
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
        members = self.secdelmembers_set.all()
        for member in members:
            member.user.users.userType ="U1D1"
            member.user.users.verificationScore = 10
            member.user.users.save()
            member.delete()

    @property
    def is_active(self):
        # check if the member <= 12 and return true
        member_count = self.secdelmembers_set.filter(is_member = True).count()
        is_currently_active = 6 <= member_count <= 12
        if is_currently_active:
            if(self.status == False):
                self.status = True
                self.save()
                self._update_member_verification_scores(100)
            return True
        else:
            if(self.status==True):
                self.status = False
                self.save()
                self._update_member_verification_scores(10)
            return False
    
    def _update_member_verification_scores(self, score):
        """Helper method to update verification scores for all sec_del members"""
        members = self.secdelmembers_set.filter(is_member=True)
        for member in members:
            member.user.users.verificationScore = score
            member.user.users.save()

    @property
    def member_count(self):
        return self.secdelmembers_set.filter(is_member = True).count()


# for maximum f-link membership validation
from django.core.exceptions import ValidationError
class MaxMembershipReached(ValidationError):
    def __init__(self, message="F-link has reached the max membership status. No longer accepting candidates."):
        super().__init__(message)

# the user can be changed to be F-Del only. but being a user is much better
class SecDelMembers(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    sec_del = models.ForeignKey(SecDelModel, on_delete=models.CASCADE)
    is_delegate = models.BooleanField(default=False)
    is_member = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    succession_position = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['-is_delegate', 'joined_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.sec_del.code}"
    
    def delete(self, *args, **kwargs):
        # set the userType to U0D0 and verification score to 0
        self.user.users.userType = "U1D1"
        self.user.users.verificationScore = 10
        self.user.users.save()
        super().delete(*args, **kwargs)

        # once the member is removed, check the grou status and update the status and that will update the 
        # members connection scores (verification score) as well.
        if self.sec_del:
            self.sec_del.is_active
    
    def save(self, *args, **kwargs):
        was_member = False
        if self.pk:
            was_member = (
                SecDelMembers.objects.filter(pk=self.pk)
                .values_list("is_member", flat=True)
                .first()
                is True
            )

        # Check for max membership.
        if SecDelMembers.objects.filter(
            is_member=True,
            sec_del=self.sec_del,
        ).count() > 12:
            raise MaxMembershipReached()

        # The first member becomes the Sec-Del delegate automatically.
        if not self.pk and not self.sec_del.secdelmembers_set.exists():
            self.is_delegate = True
            self.is_member = True
            self.user.users.userType = "U2D2"
            self.user.users.save()

        # Assign succession position when a member is first accepted.
        if (
            self.is_member
            and not was_member
            and self.succession_position is None
        ):
            max_position = (
                SecDelMembers.objects.filter(
                    sec_del=self.sec_del,
                    is_member=True,
                    succession_position__isnull=False,
                )
                .exclude(pk=self.pk)
                .aggregate(models.Max("succession_position"))[
                    "succession_position__max"
                ]
            )

            self.succession_position = (
                0 if max_position is None else max_position + 1
            )

        super(SecDelMembers, self).save(*args, **kwargs)

        if self.is_member:
            ContactInfo.objects.get_or_create(
                member=self,
                legal_name=self.user.users.legalName,
                address=self.user.users.address,
                email=self.user.email,
                sec_del=self.sec_del,
            )

    def move_forward_one_position(self):
        with transaction.atomic():
            current_member = SecDelMembers.objects.select_for_update().get(
                pk=self.pk
            )

            if (
                not current_member.is_member
                or current_member.succession_position is None
                or current_member.succession_position == 0
            ):
                return False

            member_ahead = (
                SecDelMembers.objects.select_for_update()
                .filter(
                    sec_del=current_member.sec_del,
                    is_member=True,
                    succession_position=(
                        current_member.succession_position - 1
                    ),
                )
                .first()
            )

            if member_ahead is None:
                return False

            current_position = current_member.succession_position
            ahead_position = member_ahead.succession_position

            if ahead_position == 0:
                SecDelMembers.objects.filter(pk=member_ahead.pk).update(
                    succession_position=current_position,
                    is_delegate=False,
                )
                SecDelMembers.objects.filter(pk=current_member.pk).update(
                    succession_position=0,
                    is_delegate=True,
                )

                # Second-Link membership depends on holding a First-Link
                # delegate mandate. The incoming Sec-Del
                # does not automatically inherit that membership.
                from moda.models import (
                    ModaBackNForthChat,
                    ModaMembers,
                )

                remove_dependent_memberships(
                    membership_model=ModaMembers,
                    user=member_ahead.user,
                    group_field="moda",
                    delegate_user_type="U4D3",
                    message_model=ModaBackNForthChat,
                    dependent_group_title="Second Link",
                    required_mandate_title="Sec-Del",
                    delegate_title="Caucus Delegate",
                )

                member_ahead.user.users.userType = "U2D1"
                member_ahead.user.users.save(update_fields=["userType"])

                current_member.user.users.userType = "U2D2"
                current_member.user.users.save(update_fields=["userType"])

                notify_delegate_change(
                    message_model=BackNForthChat,
                    group_field="sec_del",
                    group=current_member.sec_del,
                    group_name=f"First Link {current_member.sec_del.code}",
                    delegate_title="Sec-Del",
                    outgoing_user=member_ahead.user,
                    incoming_user=current_member.user,
                    outgoing_position=current_position,
                )

                self.succession_position = 0
                self.is_delegate = True

                return True

            SecDelMembers.objects.filter(pk=member_ahead.pk).update(
                succession_position=current_position
            )
            SecDelMembers.objects.filter(pk=current_member.pk).update(
                succession_position=ahead_position
            )

            current_name = (
                current_member.user.users.legalName
                or current_member.user.username
            )
            ahead_name = (
                member_ahead.user.users.legalName
                or member_ahead.user.username
            )

            post_succession_update(
                message_model=BackNForthChat,
                group_field="sec_del",
                group=current_member.sec_del,
                message=(
                    f"Succession update: {current_name} advanced from "
                    f"position {current_position} to position "
                    f"{ahead_position}; {ahead_name} moved from "
                    f"position {ahead_position} to position "
                    f"{current_position}."
                ),
            )

            self.succession_position = ahead_position

            return True

    def count_vote_out(self):
        return VoteOutSecDelMember.objects.filter(candidate=self).count()

    def count_vote_in(self):
        return VoteInSecDelMember.objects.filter(candidate=self).count()
      
    def count_put_forward(self):
        return PutFarwardSecDelMember.objects.filter(candidate=self).count()
    
    def check_for_majority(self): 
        total_members = SecDelMembers.objects.filter(sec_del=self.sec_del).filter(is_member = True).count()
        majority_threshold = total_members // 2 + 1  # Majority is (total_members // 2 + 1)
        if self.count_vote_in() >= majority_threshold:
            self.is_member = True
            # set the user.users userType to U1D0
            self.save()
            self.user.users.userType = 'U2D1'
            self.user.users.save()
            # create an instance of the contact info
            ContactInfo.objects.get_or_create(
                member=self,
                legal_name=self.user.users.legalName,
                address=self.user.users.address,
                email=self.user.email,
                sec_del=self.sec_del
            )

            return self
        return self
    
    def check_for_removing(self):
        total_members = SecDelMembers.objects.filter(
            sec_del=self.sec_del,
            is_member=True,
        ).count()
        majority_threshold = total_members // 2 + 1

        if self.count_vote_out() >= majority_threshold:
            with transaction.atomic():
                first_link = self.sec_del
                removed_position = self.succession_position
                removed_name = user_display_name(self.user)
                was_delegate = self.is_delegate

                successor = None
                if was_delegate:
                    successor = SecDelMembers.objects.filter(
                        sec_del=first_link,
                        is_member=True,
                        succession_position=1,
                    ).first()

                compacted_memberships = []

                if removed_position is not None:
                    compacted_memberships = list(
                        SecDelMembers.objects.filter(
                            sec_del=first_link,
                            is_member=True,
                            succession_position__gt=removed_position,
                        ).order_by("succession_position")
                    )

                if was_delegate:
                    from moda.models import (
                        ModaBackNForthChat,
                        ModaMembers,
                    )

                    remove_dependent_memberships(
                        membership_model=ModaMembers,
                        user=self.user,
                        group_field="moda",
                        delegate_user_type="U4D3",
                        message_model=ModaBackNForthChat,
                        dependent_group_title="Second Link",
                        required_mandate_title="Sec-Del",
                        delegate_title="Caucus Delegate",
                    )

                self.delete()

                if removed_position is not None:
                    SecDelMembers.objects.filter(
                        sec_del=first_link,
                        is_member=True,
                        succession_position__gt=removed_position,
                    ).update(
                        succession_position=(
                            models.F("succession_position") - 1
                        )
                    )

                    for compacted_member in compacted_memberships:
                        old_position = compacted_member.succession_position
                        new_position = old_position - 1

                        post_succession_update(
                            message_model=BackNForthChat,
                            group_field="sec_del",
                            group=first_link,
                            message=(
                                f"Succession update: "
                                f"{user_display_name(compacted_member.user)} "
                                f"moved from position {old_position} to "
                                f"position {new_position} after "
                                f"{removed_name} was removed."
                            ),
                        )

                if was_delegate and successor is not None:
                    SecDelMembers.objects.filter(
                        pk=successor.pk
                    ).update(
                        is_delegate=True,
                    )

                    successor.user.users.userType = "U2D2"
                    successor.user.users.save(
                        update_fields=["userType"]
                    )
                    notify_delegate_promotion_after_removal(
                        message_model=BackNForthChat,
                        group_field="sec_del",
                        group=first_link,
                        group_name=f"First Link {first_link.code}",
                        delegate_title="Sec-Del",
                        outgoing_user=self.user,
                        incoming_user=successor.user,
                    )

    def check_put_farward(self):
        total_members = SecDelMembers.objects.filter(sec_del=self.sec_del).filter(is_member = True).count()
        majority_votes = total_members // 2 + 1  # Majority is (total_members // 2 + 1)
        if self.count_put_forward() >= majority_votes:
            current_delegate = SecDelMembers.objects.filter(
                sec_del=self.sec_del,
                is_member=True,
                is_delegate=True,
            ).first()

            if current_delegate is None:
                return

            incumbent_position = current_delegate.succession_position
            candidate_position = self.succession_position

            current_delegate.is_delegate = False
            current_delegate.succession_position = candidate_position
            current_delegate.save(
                update_fields=[
                    "is_delegate",
                    "succession_position",
                    "updated_at",
                ]
            )

            # Second-Link membership depends on holding the Sec-Del
            # mandate. The incoming Sec-Del does not automatically
            # inherit that membership.
            from moda.models import (
                ModaBackNForthChat,
                ModaMembers,
            )

            remove_dependent_memberships(
                membership_model=ModaMembers,
                user=current_delegate.user,
                group_field="moda",
                delegate_user_type="U4D3",
                message_model=ModaBackNForthChat,
                dependent_group_title="Second Link",
                required_mandate_title="Sec-Del",
                delegate_title="Caucus Delegate",
            )

            current_delegate.user.users.userType = "U2D1"
            current_delegate.user.users.save(
                update_fields=["userType"]
            )

            self.is_delegate = True
            self.succession_position = incumbent_position
            self.user.users.userType = "U2D2"
            self.user.users.save(
                update_fields=["userType"]
            )
            self.save(
                update_fields=[
                    "is_delegate",
                    "succession_position",
                    "updated_at",
                ]
            )
            notify_delegate_change(
                message_model=BackNForthChat,
                group_field="sec_del",
                group=self.sec_del,
                group_name=f"First Link {self.sec_del.code}",
                delegate_title="Sec-Del",
                outgoing_user=current_delegate.user,
                incoming_user=self.user,
                outgoing_position=candidate_position,
            )


class VoteOutSecDelMember(models.Model):
    voter = models.ForeignKey(User, on_delete=models.CASCADE)
    candidate = models.ForeignKey(SecDelMembers, related_name='vote_outs', on_delete=models.CASCADE)
    sec_del = models.ForeignKey(SecDelModel, on_delete=models.CASCADE, null=True, blank=True)
    voted_at = models.DateTimeField(auto_now_add=True)

    # do not edit the return def as it is used on the frontend
    def __str__(self):
        return f"Voter: {self.voter.username}, Candidate: {self.candidate.id}"
    
    def save(self, *args, **kwargs):
        super(VoteOutSecDelMember, self).save(*args, **kwargs)
        self.candidate.check_for_removing()


class VoteInSecDelMember(models.Model):
    voter = models.ForeignKey(User, on_delete=models.CASCADE)
    candidate = models.ForeignKey(SecDelMembers, related_name='vote_ins', on_delete=models.CASCADE)
    sec_del = models.ForeignKey(SecDelModel, on_delete=models.CASCADE, null=True, blank=True)
    voted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Voter: {self.voter.username}, Candidate: {self.candidate.id}"
    
    def save(self, *args, **kwargs):
        super(VoteInSecDelMember, self).save(*args, **kwargs)
        self.candidate.check_for_majority()
        # self.candidate.save()
        return self 


class PutFarwardSecDelMember(models.Model):
    voter = models.ForeignKey(User, on_delete=models.CASCADE)
    candidate = models.ForeignKey(SecDelMembers, related_name='put_farward', on_delete=models.CASCADE)
    sec_del = models.ForeignKey(SecDelModel, on_delete=models.CASCADE, null=True, blank=True)
    voted_at = models.DateTimeField(auto_now_add=True)

    # do not edit the return def as it is used on the frontend
    def __str__(self):
        return f"Voter: {self.voter.username}, Candidate: {self.candidate.id}"
    
    def save(self, *args, **kwargs):
        super(PutFarwardSecDelMember, self).save(*args, **kwargs)
        self.candidate.check_put_farward()


#sed del contact information
class ContactInfo(models.Model):
    member = models.OneToOneField(SecDelMembers, null=True, blank=True, on_delete=models.CASCADE)
    sec_del = models.ForeignKey(SecDelModel, on_delete=models.CASCADE, null=True, blank=True)
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

# below is some code to generaate voters, circles and f-links
from vote.views import circle_code_generator, circle_invitation_generator
import random

def group_invite_key():
    code = str(random.randint(0, 9999999999))
    is_exist = vote_models.Group.objects.filter(invitation_code=code).exists()
    if is_exist:
        circle_invitation_generator()
    return code

def group_code():
    code = str(random.randint(1, 99999))
    is_exist = vote_models.Group.objects.filter(code=code).exists()
    if is_exist:
        circle_code_generator()
    return code

def create_voters(voters, district_code):
    users = []
    for i in range(voters):
        # create a User 
        instance = User.objects.create(username=entry_code_generator(), email=f'test_voter{i}@gmail.com', is_active=True, is_staff=True)
        instance.set_password('A123123a@')
        instance.save()
        instance.users.userType = 'U0D0'
        instance.users.district = vote_models.Districts.objects.get(code=district_code)
        instance.users.legalName = f"Test-Voter-{instance.username}"
        instance.users.address = 'just an address in the middle of nowhere'
        instance.users.is_reg = True
        instance.users.save()
        users.append(instance)
        
    return users

# below is some code to generaate voters, circles and f-links
from vote.views import circle_code_generator, circle_invitation_generator
import random

def group_invite_key():
    code = str(random.randint(0, 9999999999))
    is_exist = vote_models.Group.objects.filter(invitation_code=code).exists()
    if is_exist:
        circle_invitation_generator()
    return code

def group_code():
    code = str(random.randint(1, 99999))
    is_exist = vote_models.Group.objects.filter(code=code).exists()
    if is_exist:
        circle_code_generator()
    return code

def create_voters(voters, district_code):
    users = []
    for i in range(voters):
        # create a User 
        instance = User.objects.create(username=entry_code_generator(), email=f'test_voter{i}@gmail.com', is_active=True, is_staff=True)
        instance.set_password('A123123a@')
        instance.save()
        instance.users.userType = 'U0D0'
        instance.users.district = vote_models.Districts.objects.get(code=district_code)
        instance.users.legalName = f"Test Voter-{instance.username}"
        instance.users.address = 'just an address in the middle of nowhere'
        instance.users.is_reg = True
        instance.users.save()
        users.append(instance)
        
    return users
  
def create_circle(circle, district_code, voters):
    groups =[]
    members =[]
    for i in range(circle):
        dist = vote_models.Districts.objects.get(code=district_code)
        crcl = vote_models.Group.objects.create(district=dist,code=group_code(),invitation_code=group_invite_key(),group_type=0,parent_group=None)
        crcl.save()
        # create members for the circle
        votersInstance = create_voters(voters, district_code)
        for index, voter in enumerate(votersInstance):
            instance = vote_models.GroupMember.objects.create(user=voter, group=crcl, is_member=True)
            if index == 0:
                instance.is_delegate = True
            instance.save()
            # update the userType
            voter.users.userType = 'U1D0'
            voter.users.save()
            members.append(instance)

        groups.append(crcl)
    return [members,groups]

class BackNForthChat(models.Model):
    """Model to store chat messages for F-Links (SecDel)."""

    sec_del = models.ForeignKey(
        SecDelModel,
        on_delete=models.CASCADE,
        related_name="chat_messages",
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sent_messages",
        null=True,
        blank=True,
    )
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_edited = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    is_system = models.BooleanField(default=False)
    reply_to = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="replies",
    )

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "BackNForth Chat Message"
        verbose_name_plural = "BackNForth Chat Messages"

    def __str__(self):
        if self.is_system:
            return f"System in F-Link {self.sec_del.code}: {self.message[:50]}..."

        return (
            f"{self.sender.username} in F-Link "
            f"{self.sec_del.code}: {self.message[:50]}..."
        )

    def save(self, *args, **kwargs):
        if not self.is_system:
            if not SecDelMembers.objects.filter(
                user=self.sender,
                sec_del=self.sec_del,
                is_member=True,
            ).exists():
                raise ValidationError(
                    "Only F-Link members can send messages"
                )

        super().save(*args, **kwargs)

class DummyVoters(models.Model):
    text = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True,null=True, blank=True)
    voters = models.PositiveSmallIntegerField(default=0, null=True, blank=True)
    circle = models.PositiveSmallIntegerField(default=0, null=True, blank=True)
    f_link = models.PositiveSmallIntegerField(default=0, null=True, blank=True)
    district = models.CharField(max_length=4, null=True, blank=True)
    made_by = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return f"{self.created_at}"
    
    def save(self, *args, **kwargs):
        # check if the user is a member of the sec_del
        district_code = self.district
        # create the circles
        if self.circle > 0:
            instances = create_circle(self.circle, district_code, self.voters)
            self.text = self.text + str(instances)
        
        if self.voters > 0:
            objects = create_voters(self.voters, district_code)
            self.text = self.text + str(objects)

        super().save(*args, **kwargs)
        

class StatusItems(models.Model):
    message = models.TextField(help_text="The message to be displayed.")
    sort = models.PositiveSmallIntegerField(default=0, blank=True, null=True, help_text="The sort order of the message.")
    item_list   = models.TextField(null=True, blank=True, help_text="This field is for the list of items that the message is about.")
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)
    is_candidate_waiting = models.BooleanField(default=False, help_text="check this if the message is for the candidate waiting status.")
    is_active   = models.BooleanField(default=True, help_text="check this if the message is active status for circle...")
    is_for_candidate = models.BooleanField(verbose_name="Candidates?", default=False, help_text="This message is for the candidate view.")
    is_for_member   = models.BooleanField(verbose_name="Members?", default=False, help_text="This message is for the member view.")
    is_for_delegate = models.BooleanField(verbose_name="Delegates?", default=False, help_text="This message is for the delegate view.")
    is_for_circle   = models.BooleanField(verbose_name="Circle?", default=False, help_text="Check this option if this message is associated with the circle.")
    is_for_sec_del  = models.BooleanField(verbose_name="Second Delegate?", default=False, help_text="Check this option if this message is associated with the Second Delegate.")
    is_for_moda     = models.BooleanField(verbose_name="District Assembly?",default=False, help_text="Check this option if this message is associated with the Member of District Assembly.")
    is_for_co_rep   = models.BooleanField(verbose_name="Legislative Caucus?", default=False, help_text="Check this option if this message is associated with the Member of Legislative Caucus.")
    is_for_house_rep= models.BooleanField(verbose_name="Head of Caucus?",default=False, help_text="Check this option if this message is associated with the Head of Legislative Caucus.")

    def __str__(self):
        return self.message