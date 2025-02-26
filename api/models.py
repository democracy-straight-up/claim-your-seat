import random
from django.db import models
from vote.models import Districts
from django.contrib.auth.models import User

# imports for the dummy model
from api.serializers import entry_code_generator 
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
        instance = User.objects.create(username=entry_code_generator(), email=f'dummy_voter{i}@gmail.com', is_active=True, is_staff=True)
        instance.set_password('A123123a@')
        instance.save()
        instance.users.userType = 0
        instance.users.district = vote_models.Districts.objects.get(code=district_code)
        instance.users.legalName = f"dummy Voter-{instance.username}"
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
            voter.users.userType = 1
            voter.users.save()
            members.append(instance)

        groups.append(crcl)
    return [members,groups]

# def create_f_link(f_link, circle, district_code, voters):
#     f_links =[]
#     crcls = create_circle(circle, district_code, voters)

#     for i in range(f_link):
#         dist = vote_models.Districts.objects.get(code=district_code)
#         link = SecDelModel.objects.create(district = dist)
#         link.save()
#         # add members to this links.
#         print("cic:", crcls[0])
#         f_links.append(link)
#     pass


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




        
