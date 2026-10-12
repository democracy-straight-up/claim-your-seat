from django.db import models, transaction
from succession_helpers import remove_dependent_memberships
from succession_notifications import (
    notify_delegate_change,
    notify_delegate_promotion_after_removal,
    post_succession_update,
    user_display_name,
)
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
    eligibility_attested = models.BooleanField(default=False)
    eligibility_attested_at = models.DateTimeField(null=True, blank=True)
    eligibility_attestation_version = models.CharField(max_length=20, null=True, blank=True)
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
        is_currently_active = 6 <= member_count <= 12
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

class CircleKey(models.Model):
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name='encryption_keys'
    )
    version = models.PositiveIntegerField(default=1)
    public_key = models.TextField()
    algorithm = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['group', 'version'],
                name='unique_circle_key_version'
            )
        ]

    def __str__(self):
        return f"{self.group.code} key v{self.version}"


class AccountKey(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='encryption_keys'
    )
    version = models.PositiveIntegerField(default=1)
    public_key = models.TextField()
    algorithm = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'version'],
                name='unique_account_key_version'
            )
        ]

    def __str__(self):
        return f"{self.user.username} key v{self.version}"

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
    succession_position = models.PositiveSmallIntegerField(null=True, blank=True)

    def __str__(self):
        return str(self.user.username)

    class Meta:
        ordering = ['-is_delegate', 'date_joined']

    def save(self, *args, **kwargs):
        was_member = False
        if self.pk:
            was_member = (
                GroupMember.objects.filter(pk=self.pk)
                .values_list("is_member", flat=True)
                .first()
                is True
            )

        # Check for max membership.
        if GroupMember.objects.filter(is_member=True, group=self.group).count() > 12:
            raise MaxMembershipReached()

        # The first member becomes the F-Del automatically.
        if not self.pk and not self.group.groupmember_set.exists():
            self.is_delegate = True
            self.is_member = True
            self.user.users.userType = "U1D1"
            self.user.users.save()

        # Assign succession position when a member is first accepted.
        if (
            self.is_member
            and not was_member
            and self.succession_position is None
        ):
            max_position = (
                GroupMember.objects.filter(
                    group=self.group,
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

        super(GroupMember, self).save(*args, **kwargs)

        if self.group:
            self.group.is_active

        if self.is_member:
            ContactInfo.objects.get_or_create(
                member=self,
                legal_name=self.user.users.legalName,
                address=self.user.users.address,
                email=self.user.email,
                group=self.group,
            )

    def move_forward_one_position(self):
        with transaction.atomic():
            current_member = GroupMember.objects.select_for_update().get(
                pk=self.pk
            )

            if (
                not current_member.is_member
                or current_member.succession_position is None
                or current_member.succession_position == 0
            ):
                return False

            member_ahead = (
                GroupMember.objects.select_for_update()
                .filter(
                    group=current_member.group,
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
                GroupMember.objects.filter(pk=member_ahead.pk).update(
                    succession_position=current_position,
                    is_delegate=False,
                )
                GroupMember.objects.filter(pk=current_member.pk).update(
                    succession_position=0,
                    is_delegate=True,
                )

                # First-Link membership depends on holding a Circle
                # delegate mandate. The incoming F-Del does
                # not automatically inherit that membership.
                from api.models import BackNForthChat, SecDelMembers

                remove_dependent_memberships(
                    membership_model=SecDelMembers,
                    user=member_ahead.user,
                    group_field="sec_del",
                    delegate_user_type="U2D2",
                    message_model=BackNForthChat,
                    dependent_group_title="First Link",
                    required_mandate_title="F-Del",
                    delegate_title="Sec-Del",
                )

                member_ahead.user.users.userType = "U1D0"
                member_ahead.user.users.save(update_fields=["userType"])
                notify_delegate_change(
                    message_model=CircleBackNForth,
                    group_field="circle",
                    group=current_member.group,
                    group_name=f"Circle {current_member.group.code}",
                    delegate_title="F-Del",
                    outgoing_user=member_ahead.user,
                    incoming_user=current_member.user,
                    outgoing_position=current_position,
                )

                current_member.user.users.userType = "U1D1"
                current_member.user.users.save(update_fields=["userType"])

                self.succession_position = 0
                self.is_delegate = True

                return True

            GroupMember.objects.filter(pk=member_ahead.pk).update(
                succession_position=current_position
            )
            GroupMember.objects.filter(pk=current_member.pk).update(
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
                message_model=CircleBackNForth,
                group_field="circle",
                group=current_member.group,
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
        total_members = GroupMember.objects.filter(
            group=self.group,
            is_member=True,
        ).count()
        majority_threshold = total_members // 2 + 1

        if self.count_vote_out() >= majority_threshold:
            with transaction.atomic():
                group = self.group
                removed_position = self.succession_position
                removed_name = user_display_name(self.user)
                was_delegate = self.is_delegate

                successor = None
                if was_delegate:
                    successor = GroupMember.objects.filter(
                        group=group,
                        is_member=True,
                        succession_position=1,
                    ).first()

                compacted_memberships = []

                if removed_position is not None:
                    compacted_memberships = list(
                        GroupMember.objects.filter(
                            group=group,
                            is_member=True,
                            succession_position__gt=removed_position,
                        ).order_by("succession_position")
                    )

                CircleMember_vote_out.objects.filter(
                    candidate=self
                ).delete()

                if was_delegate:
                    from api.models import BackNForthChat, SecDelMembers

                    remove_dependent_memberships(
                        membership_model=SecDelMembers,
                        user=self.user,
                        group_field="sec_del",
                        delegate_user_type="U2D2",
                        message_model=BackNForthChat,
                        dependent_group_title="First Link",
                        required_mandate_title="F-Del",
                        delegate_title="Sec-Del",
                    )

                self.delete()

                if removed_position is not None:
                    GroupMember.objects.filter(
                        group=group,
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
                            message_model=CircleBackNForth,
                            group_field="circle",
                            group=group,
                            message=(
                                f"Succession update: "
                                f"{user_display_name(compacted_member.user)} "
                                f"moved from position {old_position} to "
                                f"position {new_position} after "
                                f"{removed_name} was removed."
                            ),
                        )

                if was_delegate and successor is not None:
                    GroupMember.objects.filter(
                        pk=successor.pk
                    ).update(
                        is_delegate=True,
                    )

                    successor.user.users.userType = "U1D1"
                    successor.user.users.save(
                        update_fields=["userType"]
                    )
                    notify_delegate_promotion_after_removal(
                        message_model=CircleBackNForth,
                        group_field="circle",
                        group=group,
                        group_name=f"Circle {group.code}",
                        delegate_title="F-Del",
                        outgoing_user=self.user,
                        incoming_user=successor.user,
                    )

    def check_put_forward(self):
        total_members = GroupMember.objects.filter(group=self.group).filter(is_member = True).count()
        majority_threshold = total_members // 2 + 1  # Majority is (total_members // 2 + 1)
        if self.count_put_forward() >= majority_threshold:

            current_delegate = GroupMember.objects.filter(
                group=self.group,
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
                    "date_updated",
                ]
            )

            # First-Link membership depends on holding the F-Del
            # mandate. The incoming F-Del does not automatically
            # inherit that membership.
            from api.models import BackNForthChat, SecDelMembers

            remove_dependent_memberships(
                membership_model=SecDelMembers,
                user=current_delegate.user,
                group_field="sec_del",
                delegate_user_type="U2D2",
                message_model=BackNForthChat,
                dependent_group_title="First Link",
                required_mandate_title="F-Del",
                delegate_title="Sec-Del",
            )

            current_delegate.user.users.userType = "U1D0"
            current_delegate.user.users.save(
                update_fields=["userType"]
            )

            self.is_delegate = True
            self.succession_position = incumbent_position
            self.user.users.userType = "U1D1"
            self.user.users.save(
                update_fields=["userType"]
            )
            self.save(
                update_fields=[
                    "is_delegate",
                    "succession_position",
                    "date_updated",
                ]
            )

            CircleMember_put_forward.objects.filter(
                recipient=self
            ).delete()
            notify_delegate_change(
                message_model=CircleBackNForth,
                group_field="circle",
                group=self.group,
                group_name=f"Circle {self.group.code}",
                delegate_title="F-Del",
                outgoing_user=current_delegate.user,
                incoming_user=self.user,
                outgoing_position=candidate_position,
            )

    def count_vote_in(self):
        return CircleMember_vote_in.objects.filter(recipient=self).count()
    def count_vote_out(self):
        return CircleMember_vote_out.objects.filter(candidate=self).count()
    def count_put_forward(self):
        return CircleMember_put_forward.objects.filter(recipient=self).count()

class CircleCredential(models.Model):
    group_member = models.OneToOneField(
        GroupMember,
        on_delete=models.CASCADE,
        related_name='credential'
    )
    key_version = models.PositiveIntegerField(default=1)
    ciphertext = models.TextField()
    algorithm = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Credential for {self.group_member}"

class CircleKeyEnvelope(models.Model):
    circle_key = models.ForeignKey(
        CircleKey,
        on_delete=models.CASCADE,
        related_name='member_envelopes'
    )
    group_member = models.ForeignKey(
        GroupMember,
        on_delete=models.CASCADE,
        related_name='key_envelopes'
    )
    account_key = models.ForeignKey(
        AccountKey,
        on_delete=models.PROTECT,
        related_name='circle_key_envelopes'
    )
    wrapped_key = models.TextField()
    algorithm = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['circle_key', 'group_member'],
                name='unique_circle_key_member_envelope'
            )
        ]

    def __str__(self):
        return f"{self.circle_key} envelope for {self.group_member}"

class CircleBackNForth(models.Model):
    circle = models.ForeignKey(Group, on_delete=models.CASCADE)
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    date = models.DateTimeField(auto_created=True, auto_now_add=True)
    message = models.TextField(max_length=5000)
    handle = models.PositiveSmallIntegerField(default=0)
    is_system = models.BooleanField(default=False)

    def __str__(self) -> str:
        if self.is_system:
            return f"System - {self.circle.code}"

        return f"{self.sender.username} - {self.circle.code}"

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
        self.recipient.check_put_forward()

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

