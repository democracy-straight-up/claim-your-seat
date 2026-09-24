import random
from django.db import models, transaction
from vote.models import Districts
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator

def generate_unique_code():
    """Generate a unique code from 1 to 10"""
    for code in range(1, 11):
        if not HolcModel.objects.filter(code=code).exists():
            return code
    raise ValidationError("All codes from 1 to 10 are already in use. Cannot create new HOLC.")

# this is for generating unique invitation key, it not used right now.
# but do not delete it, we might need it in the future.
def generate_unique_invitation_key():
    while True:
        invitation_key = random.randint(1000000000, 9999999999)
        if not HolcModel.objects.filter(invitation_key=invitation_key).exists():
            return invitation_key

class CaucusNumberSequence(models.Model):
    district = models.OneToOneField(
        Districts,
        on_delete=models.CASCADE,
        related_name="caucus_number_sequence",
    )
    last_issued = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(99)],
    )
class HolcModel(models.Model):
    code = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(99)],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    district = models.ForeignKey(Districts, on_delete=models.DO_NOTHING)
    invitation_key = models.PositiveBigIntegerField(unique=False, null=True, blank=True)
    status = models.BooleanField(default=False, null=True, blank=True)
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["district", "code"],
                name="unique_caucus_code_per_district",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            original = HolcModel.objects.get(pk=self.pk)
            if self.district_id != original.district_id:
                raise ValidationError(
                    "A Caucus district cannot be changed after creation."
                )
            if self.code != original.code:
                raise ValidationError(
                    "A Caucus number cannot be changed after creation."
                )

            self.full_clean()
            return super().save(*args, **kwargs)

        if not self.district_id:
            raise ValidationError("A Caucus must belong to a district.")


        with transaction.atomic():
            # Serialize Caucus creation within this district.
            Districts.objects.select_for_update().get(pk=self.district_id)

            existing_codes = set(
                HolcModel.objects.filter(
                    district_id=self.district_id,
                ).values_list("code", flat=True)
            )

            sequence, _ = CaucusNumberSequence.objects.get_or_create(
                district_id=self.district_id,
                defaults={
                    "last_issued": max(existing_codes, default=1),
                },
            )

            if self.code != 1:
                if sequence.last_issued < 99:
                    next_code = sequence.last_issued + 1
                else:
                    next_code = next(
                        (
                            number
                            for number in range(2, 100)
                            if number not in existing_codes
                        ),
                        None,
                    )

                if next_code is None:
                    raise ValidationError(
                        "All ordinary Caucus numbers (02–99) "
                        "are currently in use in this district."
                    )

                if self.code is not None and self.code != next_code:
                    raise ValidationError(
                        f"The next available ordinary Caucus number "
                        f"is {next_code:02d}."
                    )

                self.code = next_code

            self.full_clean()
            result = super().save(*args, **kwargs)

            if self.code > sequence.last_issued:
                sequence.last_issued = self.code
                sequence.save(update_fields=["last_issued"])

            return result

    def __str__(self):
        return str(self.code)
    
    def delete(self):
        members = self.holcmembers_set.all()
        for member in members:
            member.user.users.userType ="U3D3"
            member.user.users.verificationScore = 1000
            member.user.users.save()
            member.delete()

    @property
    def is_active(self):
        # A Caucus is active with at least one accepted member.
        member_count = self.holcmembers_set.filter(is_member=True).count()
        is_currently_active = member_count >= 1
        if is_currently_active:
            if(self.status == False):
                self.status = True
                self.save()
                self._update_member_verification_scores(10000)
            return True
        else:
            if(self.status==True):
                self.status = False
                self.save()
                self._update_member_verification_scores(1000)
            return False
    
    def _update_member_verification_scores(self, score):
        """Helper method to update verification scores for all sec_del members"""
        members = self.holcmembers_set.filter(is_member=True)
        for member in members:
            member.user.users.verificationScore = score
            member.user.users.save()

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
    succession_position = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['-is_delegate', 'joined_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.holc.code}"
    
    def delete(self, *args, **kwargs):
        # set the userType to U0D0 and verification score to 0
        self.user.users.userType = "U3D3"
        self.user.users.verificationScore = 1000
        self.user.users.save()
        super().delete(*args, **kwargs)

        if self.holc:
            self.holc.is_active

    def save(self, *args, **kwargs):
        was_member = False
        if self.pk:
            was_member = (
                HolcMembers.objects.filter(pk=self.pk)
                .values_list("is_member", flat=True)
                .first()
                is True
            )

        # The first member becomes the HoLC automatically.
        if not self.pk and not self.holc.holcmembers_set.exists():
            self.is_delegate = True
            self.is_member = True
            self.user.users.userType = "U4D4"
            self.user.users.save()

        # Assign succession position when a member is first accepted.
        if (
            self.is_member
            and not was_member
            and self.succession_position is None
        ):
            max_position = (
                HolcMembers.objects.filter(
                    holc=self.holc,
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

        super(HolcMembers, self).save(*args, **kwargs)

        # Create contact if member becomes a member.
        if self.is_member:
            HolcMemberContact.objects.get_or_create(
                member=self,
                defaults={
                    "holc": self.holc,
                    "legal_name": self.user.users.legalName,
                    "address": self.user.users.address,
                    "email": self.user.email,
                    "contact_rules": "Please contact during regular hours.",
                    "contact": "Available via email.",
                },
            )

    def move_forward_one_position(self):
        with transaction.atomic():
            current_member = HolcMembers.objects.select_for_update().get(
                pk=self.pk
            )

            if (
                not current_member.is_member
                or current_member.succession_position is None
                or current_member.succession_position == 0
            ):
                return False

            member_ahead = (
                HolcMembers.objects.select_for_update()
                .filter(
                    holc=current_member.holc,
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
                HolcMembers.objects.filter(pk=member_ahead.pk).update(
                    succession_position=current_position,
                    is_delegate=False,
                )
                HolcMembers.objects.filter(pk=current_member.pk).update(
                    succession_position=0,
                    is_delegate=True,
                )

                member_ahead.user.users.userType = "U4D3"
                member_ahead.user.users.save(update_fields=["userType"])

                current_member.user.users.userType = "U4D4"
                current_member.user.users.save(update_fields=["userType"])

                self.succession_position = 0
                self.is_delegate = True

                return True

            HolcMembers.objects.filter(pk=member_ahead.pk).update(
                succession_position=current_position
            )
            HolcMembers.objects.filter(pk=current_member.pk).update(
                succession_position=ahead_position
            )

            self.succession_position = ahead_position

            return True

    def count_put_forward(self):
        current_accepted_voter_ids = HolcMembers.objects.filter(
            holc=self.holc,
            is_member=True,
        ).values_list("user_id", flat=True)

        return PutForwardHolcMember.objects.filter(
            candidate=self,
            voter_id__in=current_accepted_voter_ids,
        ).count()

    def check_put_forward(self):
        from moda.models import ModaMembers

        has_active_delegate_mandate = ModaMembers.objects.filter(
            user=self.user,
            is_member=True,
            is_delegate=True,
            moda__district=self.holc.district,
            moda__status=True,
        ).exists()

        if not has_active_delegate_mandate:
            return

        total_members = HolcMembers.objects.filter(
            holc=self.holc,
            is_member=True,
        ).count()
        majority_votes = total_members // 2 + 1
        if self.count_put_forward() >= majority_votes:
            # find the current delegate and set is_delegate false.
            current_delegate = HolcMembers.objects.filter(holc=self.holc).filter(is_delegate = True).first()
            old_delegate_user = current_delegate.user
            
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
            
            # Trigger succession line for higher groups
            try:
                from succession_line import succession_manager
                succession_manager.handle_delegate_change(
                    'holc', 
                    old_delegate_user, 
                    self.user, 
                    self.holc
                )
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error in succession line: {str(e)}")


class CaucusAdmissionVote(models.Model):
    voter = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="caucus_admission_votes",
    )
    application = models.ForeignKey(
        HolcMembers,
        on_delete=models.CASCADE,
        related_name="admission_votes",
    )
    voted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["voted_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["voter", "application"],
                name="unique_caucus_admission_vote",
            ),
        ]

    def __str__(self):
        return (
            f"{self.voter.username} -> "
            f"{self.application.user.username} "
            f"for Caucus {self.application.holc.code}"
        )


class CaucusExpulsionVote(models.Model):
    voter = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="caucus_expulsion_votes",
    )
    target_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="caucus_expulsion_votes_received",
    )
    caucus = models.ForeignKey(
        HolcModel,
        on_delete=models.CASCADE,
        related_name="expulsion_votes",
    )
    # Store the membership ID as a snapshot rather than a foreign key so
    # the vote history survives removal of the target membership.
    target_membership_id = models.PositiveBigIntegerField()
    voted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["voted_at"]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "voter",
                    "caucus",
                    "target_membership_id",
                ],
                name="unique_caucus_expulsion_vote",
            ),
        ]

    def __str__(self):
        return (
            f"{self.voter.username} -> "
            f"{self.target_user.username} "
            f"from Caucus {self.caucus.code}"
        )


class PutForwardHolcMember(models.Model):
    voter = models.ForeignKey(User, on_delete=models.CASCADE)
    candidate = models.ForeignKey(
        HolcMembers,
        related_name="put_forward",
        on_delete=models.CASCADE,
    )
    holc = models.ForeignKey(
        HolcModel,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    voted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["voter", "candidate", "holc"],
                name="unique_holc_replacement_vote",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self.candidate.is_member:
            return

        if self.candidate.is_delegate:
            return

        if self.holc_id != self.candidate.holc_id:
            return

        is_accepted_voter = HolcMembers.objects.filter(
            user=self.voter,
            holc=self.candidate.holc,
            is_member=True,
        ).exists()

        if not is_accepted_voter:
            return

        if (
            self._state.adding
            and PutForwardHolcMember.objects.filter(
                voter=self.voter,
                candidate=self.candidate,
                holc=self.holc,
            ).exists()
        ):
            return

        super().save(*args, **kwargs)
        self.candidate.check_put_forward()


class HolcMemberContact(models.Model):
    member = models.OneToOneField(
        'HolcMembers', 
        on_delete=models.CASCADE, 
        related_name='holc_contact'
    )
    holc = models.ForeignKey('HolcModel', on_delete=models.CASCADE)
    
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


class HolcBackNForthChat(models.Model):
    """
    Chat messages for HoLC (House of Local Councils) BackNForth conversations
    """
    holc = models.ForeignKey(HolcModel, on_delete=models.CASCADE, related_name='chat_messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    reply_to = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='replies')
    
    # Timestamps
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Edit tracking
    is_edited = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)
    
    # Soft delete
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['holc', '-timestamp']),
            models.Index(fields=['sender']),
            models.Index(fields=['is_deleted']),
        ]
    
    def __str__(self):
        return f"{self.sender.username} in HoLC-{self.holc.code}: {self.message[:50]}"
