import random
from django.db import models
from vote.models import Districts
from django.contrib.auth.models import User

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
        if 6 <= self.secdelmembers_set.filter(is_member = True).count() <= 12:
            return True
        return False

# the user can be changed to be Circle delegate only. but being a user is much better
class SecDelMembers(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    sec_del = models.ForeignKey(SecDelModel, on_delete=models.CASCADE)
    is_delegate = models.BooleanField(default=False)
    is_member = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    vote_in_count = models.PositiveSmallIntegerField(default=0)
    vote_out_count = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['-is_delegate', 'joined_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.sec_del.code}"
    
    def delete(self, using=None, keep_parents=False):
        self.user.users.userType = 1
        self.user.users.save()
        super().delete(using, keep_parents)
    
    def save(self, *args, **kwargs):
        # Calculate if is_member should be true (calculating the majority of vote)
        if self.vote_in_count >= (self.sec_del.secdelmembers_set.filter(is_member=True).count()/2):
            print("this message is from saving the instance on the model, the User is a member now...")
            self.is_member = True
        else:
            self.is_member = False

        # check the user type of the member. it has to be userType 1 
        # on save, update the userType to 2
        if self.user.users.userType >= 1:
            self.user.users.userType = 2
            self.user.users.save()
        else:
            return {"error": "User is not eligible for this operation."}
        
        # on each first member, make the member the delegate member by default.
        if not self.pk and not self.sec_del.secdelmembers_set.exists():
            self.is_delegate = True
            self.is_member = True

        super().save(*args, **kwargs)


