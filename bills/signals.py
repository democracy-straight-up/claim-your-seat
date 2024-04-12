from django.db.models.signals import post_save
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import BillVote
from vote.models import CircleMember

@receiver(post_save, sender=BillVote)
def order_offer_observer(sender, instance, created, **kwargs):
    if not created:
        voter = instance.voter.username
        bill_id = instance.bill.number
        pm_obj = CircleMember.objects.get(user__username=voter)
        circleName = pm_obj.circle.code
        is_delegate = pm_obj.is_delegate
        room_group_name = f'bill_{bill_id}_circle_{circleName}'

        if is_delegate:
            layer = get_channel_layer()
            async_to_sync(layer.group_send)(room_group_name, {
                'type': 'update.advice',
                'data': {
                    'advice': instance.your_vote
                }
            })