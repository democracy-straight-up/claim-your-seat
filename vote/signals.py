from django.db.models.signals import post_save, post_delete, pre_delete
from django.contrib.auth.models import User
from django.dispatch import receiver
from vote import models

@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    if created:
        models.Users.objects.create(user = instance)
        # print("user profile createds")

@receiver(post_save, sender=User)
def save_profile(sender, instance, *args, **kwargs):
    instance.users.save()
    # print("user profile saved")


@receiver(pre_delete, sender=models.Circle)
def setUserType(sender, instance,*args, **kwargs):
    """this signal sets the circle member's userType to zero"""
    members = models.CircleMember.objects.filter(circle = instance)
    for i in members:
        ut = i.user
        ut.users.userType = 0
        ut.save()
