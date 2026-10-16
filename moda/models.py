import random
from django.db import models, transaction
from django.core.exceptions import ValidationError
from succession_helpers import remove_dependent_memberships
from succession_notifications import (
    notify_delegate_change,
    notify_delegate_promotion_after_removal,
    post_succession_update,
    user_display_name,
)
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
    
    def delete(self, *args, **kwargs):
        with transaction.atomic():
            # Lock the Second Link during dissolution.
            second_link = type(self).objects.select_for_update().get(
                pk=self.pk
            )

            accepted_members = second_link.modamembers_set.filter(
                is_member=True,
            )

            # Dissolution requires exactly one accepted member,
            # who must be the serving Caucus Delegate.
            if (
                accepted_members.count() != 1
                or not accepted_members.filter(
                    is_delegate=True
                ).exists()
            ):
                raise ValidationError(
                    "A Second Link may be dissolved only when "
                    "its Caucus Delegate is the sole remaining "
                    "accepted member."
                )

            members = list(
                second_link.modamembers_set.select_for_update()
            )

            for member in members:
                member.user.users.userType = "U2D2"
                member.user.users.verificationScore = 100
                member.user.users.save()
                member.delete()

            return super().delete(*args, **kwargs)

    @property
    def is_active(self):
        # check if the member <= 12 and return true
        member_count = self.modamembers_set.filter(is_member = True).count()
        is_currently_active = 6 <= member_count <= 12
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
        """Update member scores and assign newly activated delegates."""
        from holc.models import HolcModel, HolcMembers

        members = self.modamembers_set.filter(is_member=True)

        for member in members:
            member.user.users.verificationScore = score
            member.user.users.save()

            if score != 1000 or not member.is_delegate:
                continue

            # Preserve an existing Caucus membership.
            if HolcMembers.objects.filter(user=member.user).exists():
                continue

            general_caucus, _ = HolcModel.objects.get_or_create(
                district=self.district,
                code=1,
            )

            # HolcMembers.save() makes the first member its HoLC.
            HolcMembers.objects.create(
                user=member.user,
                holc=general_caucus,
                is_member=True,
                is_delegate=False,
            )


    @property
    def member_count(self):
        return self.modamembers_set.filter(is_member = True).count()


# for maximum f-link membership validation
from django.core.exceptions import ValidationError
class MaxMembershipReached(ValidationError):
    def __init__(self, message="S-Link has reached the max membership status. No longer accepting candidates."):
        super().__init__(message)

# the user can be changed to be F-Del only. but being a user is much better
class ModaMembers(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    moda = models.ForeignKey(ModaModel, on_delete=models.CASCADE)
    is_delegate = models.BooleanField(default=False)
    is_member = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    succession_position = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['-is_delegate', 'joined_at']
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                name="moda_one_membership_per_user",
            ),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.moda.code}"
    
    def delete(self, *args, **kwargs):
        # set the userType to U0D0 and verification score to 0
        self.user.users.userType = "U2D2"
        self.user.users.verificationScore = 100
        self.user.users.save()
        super().delete(*args, **kwargs)

        if self.moda:
            self.moda.is_active

    def save(self, *args, **kwargs):
        was_member = False
        if self.pk:
            was_member = (
                ModaMembers.objects.filter(pk=self.pk)
                .values_list("is_member", flat=True)
                .first()
                is True
            )

        # Check for max membership.
        if ModaMembers.objects.filter(is_member=True).count() > 12:
            raise MaxMembershipReached()

        # The first member becomes the Caucus delegate automatically.
        if not self.pk and not self.moda.modamembers_set.exists():
            self.is_delegate = True
            self.is_member = True
            self.user.users.userType = "U4D3"
            self.user.users.save()

        # Assign succession position when a member is first accepted.
        if (
            self.is_member
            and not was_member
            and self.succession_position is None
        ):
            max_position = (
                ModaMembers.objects.filter(
                    moda=self.moda,
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

        super(ModaMembers, self).save(*args, **kwargs)

        # Create contact if member becomes a member.
        if self.is_member:
            ModaMemberContact.objects.get_or_create(
                member=self,
                defaults={
                    "moda": self.moda,
                    "legal_name": self.user.users.legalName,
                    "address": self.user.users.address,
                    "email": self.user.email,
                    "contact_rules": "Please contact during regular hours.",
                    "contact": "Available via email.",
                },
            )

    def move_forward_one_position(self):
        with transaction.atomic():
            current_member = ModaMembers.objects.select_for_update().get(
                pk=self.pk
            )

            if (
                not current_member.is_member
                or current_member.succession_position is None
                or current_member.succession_position == 0
            ):
                return False

            member_ahead = (
                ModaMembers.objects.select_for_update()
                .filter(
                    moda=current_member.moda,
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
                ModaMembers.objects.filter(pk=member_ahead.pk).update(
                    succession_position=current_position,
                    is_delegate=False,
                )
                ModaMembers.objects.filter(pk=current_member.pk).update(
                    succession_position=0,
                    is_delegate=True,
                )

                # Caucus membership depends on holding a Second-Link
                # delegate mandate. The incoming Caucus Delegate
                # does not automatically inherit that membership.
                from holc.models import (
                    HolcBackNForthChat,
                    HolcMembers,
                )

                remove_dependent_memberships(
                    membership_model=HolcMembers,
                    user=member_ahead.user,
                    group_field="holc",
                    delegate_user_type="U4D4",
                    message_model=HolcBackNForthChat,
                    dependent_group_title="Caucus",
                    required_mandate_title="Caucus Delegate",
                    delegate_title="HoLC",
                )

                member_ahead.user.users.userType = "U3D2"
                member_ahead.user.users.save(update_fields=["userType"])

                current_member.user.users.userType = "U4D3"
                current_member.user.users.save(update_fields=["userType"])

                notify_delegate_change(
                    message_model=ModaBackNForthChat,
                    group_field="moda",
                    group=current_member.moda,
                    group_name=f"Second Link {current_member.moda.code}",
                    delegate_title="Caucus Delegate",
                    outgoing_user=member_ahead.user,
                    incoming_user=current_member.user,
                    outgoing_position=current_position,
                )

                self.succession_position = 0
                self.is_delegate = True

                return True

            ModaMembers.objects.filter(pk=member_ahead.pk).update(
                succession_position=current_position
            )
            ModaMembers.objects.filter(pk=current_member.pk).update(
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
                message_model=ModaBackNForthChat,
                group_field="moda",
                group=current_member.moda,
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
            
            # Create contact info when member is voted in
            ModaMemberContact.objects.get_or_create(
                member=self,
                defaults={
                    'moda': self.moda,
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
        total_members = ModaMembers.objects.filter(
            moda=self.moda,
            is_member=True,
        ).count()
        majority_threshold = total_members // 2 + 1

        if self.count_vote_out() >= majority_threshold:
            with transaction.atomic():
                second_link = self.moda
                removed_position = self.succession_position
                removed_name = user_display_name(self.user)
                was_delegate = self.is_delegate

                successor = None
                if was_delegate:
                    successor = ModaMembers.objects.filter(
                        moda=second_link,
                        is_member=True,
                        succession_position=1,
                    ).first()

                compacted_memberships = []

                if removed_position is not None:
                    compacted_memberships = list(
                        ModaMembers.objects.filter(
                            moda=second_link,
                            is_member=True,
                            succession_position__gt=removed_position,
                        ).order_by("succession_position")
                    )

                if was_delegate:
                    from holc.models import (
                        HolcBackNForthChat,
                        HolcMembers,
                    )

                    remove_dependent_memberships(
                        membership_model=HolcMembers,
                        user=self.user,
                        group_field="holc",
                        delegate_user_type="U4D4",
                        message_model=HolcBackNForthChat,
                        dependent_group_title="Caucus",
                        required_mandate_title="Caucus Delegate",
                        delegate_title="HoLC",
                    )

                self.delete()

                if removed_position is not None:
                    ModaMembers.objects.filter(
                        moda=second_link,
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
                            message_model=ModaBackNForthChat,
                            group_field="moda",
                            group=second_link,
                            message=(
                                f"Succession update: "
                                f"{user_display_name(compacted_member.user)} "
                                f"moved from position {old_position} to "
                                f"position {new_position} after "
                                f"{removed_name} was removed."
                            ),
                        )

                if was_delegate and successor is not None:
                    ModaMembers.objects.filter(
                        pk=successor.pk
                    ).update(
                        is_delegate=True,
                    )

                    successor.user.users.userType = "U4D3"
                    successor.user.users.save(
                        update_fields=["userType"]
                    )
                    notify_delegate_promotion_after_removal(
                        message_model=ModaBackNForthChat,
                        group_field="moda",
                        group=second_link,
                        group_name=f"Second Link {second_link.code}",
                        delegate_title="Caucus Delegate",
                        outgoing_user=self.user,
                        incoming_user=successor.user,
                        direct_removal=True,
                    )

    def check_put_farward(self):
        total_members = ModaMembers.objects.filter(moda=self.moda).filter(is_member = True).count()
        majority_votes = total_members // 2 + 1  # Majority is (total_members // 2 + 1)
        if self.count_put_forward() >= majority_votes:
            current_delegate = ModaMembers.objects.filter(
                moda=self.moda,
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

            # Caucus membership depends on holding the Caucus Delegate
            # mandate. The incoming Caucus Delegate does not
            # automatically inherit that membership.
            from holc.models import HolcMembers

            remove_dependent_memberships(
                membership_model=HolcMembers,
                user=current_delegate.user,
                group_field="holc",
                delegate_user_type="U4D4",
            )

            current_delegate.user.users.userType = "U3D2"
            current_delegate.user.users.save(
                update_fields=["userType"]
            )

            self.is_delegate = True
            self.succession_position = incumbent_position
            self.user.users.userType = "U4D3"
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
                message_model=ModaBackNForthChat,
                group_field="moda",
                group=self.moda,
                group_name=f"Second Link {self.moda.code}",
                delegate_title="Caucus Delegate",
                outgoing_user=current_delegate.user,
                incoming_user=self.user,
                outgoing_position=candidate_position,
            )


class VoteOutModaMember(models.Model):
    voter = models.ForeignKey(User, on_delete=models.CASCADE)
    agent = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="moda_vote_out_actions",
    )
    candidate = models.ForeignKey(ModaMembers, related_name='vote_outs', on_delete=models.CASCADE)
    moda = models.ForeignKey(ModaModel, on_delete=models.CASCADE, null=True, blank=True)
    voted_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["voter", "candidate", "moda"],
                name="moda_vote_out_one_effective",
            ),
        ]
    def save(self, *args, **kwargs):
        super(VoteOutModaMember, self).save(*args, **kwargs)
        self.candidate.check_for_removing()


class VoteInModaMember(models.Model):
    voter = models.ForeignKey(User, on_delete=models.CASCADE)
    agent = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="moda_vote_in_actions",
    )
    candidate = models.ForeignKey(ModaMembers, related_name='vote_ins', on_delete=models.CASCADE)
    moda = models.ForeignKey(ModaModel, on_delete=models.CASCADE, null=True, blank=True)
    voted_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["voter", "candidate", "moda"],
                name="moda_vote_in_one_effective",
            ),
        ]
    def save(self, *args, **kwargs):
        super(VoteInModaMember, self).save(*args, **kwargs)
        self.candidate.check_for_majority()
        return self 


class PutFarwardModaMember(models.Model):
    voter = models.ForeignKey(User, on_delete=models.CASCADE)
    agent = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="moda_put_forward_actions",
    )
    candidate = models.ForeignKey(ModaMembers, related_name='put_farward', on_delete=models.CASCADE)
    moda = models.ForeignKey(ModaModel, on_delete=models.CASCADE, null=True, blank=True)
    voted_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["voter", "candidate", "moda"],
                name="moda_put_forward_one_effective",
            ),
        ]
    def save(self, *args, **kwargs):
        super(PutFarwardModaMember, self).save(*args, **kwargs)
        self.candidate.check_put_farward()


class ModaMemberContact(models.Model):
    member = models.OneToOneField(
        'ModaMembers', 
        on_delete=models.CASCADE, 
        related_name='moda_contact'
    )
    moda = models.ForeignKey('ModaModel', on_delete=models.CASCADE)
    
    # Contact information
    legal_name = models.CharField(max_length=255, blank=True, null=True)
    contact_rules = models.TextField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    contact = models.TextField(blank=True, null=True)
    phone = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(max_length=255, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.legal_name} - {self.member}"


class ModaBackNForthChat(models.Model):
    """
    Chat messages for S-Link (Moda) BackNForth conversations.
    """
    moda = models.ForeignKey(
        ModaModel,
        on_delete=models.CASCADE,
        related_name="chat_messages",
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    message = models.TextField()
    reply_to = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="replies",
    )

    # Timestamps
    timestamp = models.DateTimeField(auto_now_add=True)

    # Edit tracking
    is_edited = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)

    # Soft delete
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    is_system = models.BooleanField(default=False)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["moda", "-timestamp"]),
            models.Index(fields=["sender"]),
            models.Index(fields=["is_deleted"]),
        ]

    def __str__(self):
        if self.is_system:
            return (
                f"System in S-Link-{self.moda.code}: "
                f"{self.message[:50]}"
            )

        return (
            f"{self.sender.username} in S-Link-{self.moda.code}: "
            f"{self.message[:50]}"
        )