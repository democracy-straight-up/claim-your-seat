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
        if 6 <= self.modamembers_set.filter(is_member = True).count() <= 12:
            return True
        return False
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
    
    def delete(self, using=None, keep_parents=False):
        # check if the user type is correct.
        self.user.users.userType = 'U2D1'
        self.user.users.save()
        super().delete(using, keep_parents)
    
    def save(self, *args, **kwargs):
        # check for max membership 
        if ModaMembers.objects.filter(is_member=True).count() > 12:
            print("max member reached..")
            raise MaxMembershipReached()  # Raise maxMember validation
        
        # on each first member, make the member the delegate member by default.
        if not self.pk and not self.moda.modamembers_set.exists():
            print("first member and setting it as delegate")
            self.is_delegate = True
            self.is_member = True
            self.user.users.userType = 'U3D3'
            self.user.users.save()
        
        super(ModaMembers, self).save(*args, **kwargs)
