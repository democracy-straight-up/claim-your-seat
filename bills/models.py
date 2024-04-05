from django.db import models
from django.contrib.auth.models import User
from vote.models import Pod
# Create your models here.


class Bill(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, editable=False)
    congress = models.IntegerField(null=True)
    number = models.CharField(max_length=50)
    origin_chamber = models.CharField(max_length=50)
    origin_chamber_code = models.CharField(max_length=3)
    title = models.CharField(max_length=200)
    bill_type = models.CharField(max_length=10)
    url = models.URLField()
    latest_action_date = models.DateField(null=True)
    latest_action_text = models.TextField()
    voting_start = models.DateField(blank=True, null=True)
    voting_close = models.DateField(blank=True, null=True)
    schedule_date = models.DateField(blank=True, null=True)
    text = models.TextField()
    # advice = models.TextField()

    class Meta:
        ordering = ('-created_at',)
        get_latest_by = ['number']

    def __str__(self):
        return self.number

    # these methods (def) return numbers of votes of bill instance

    def count_yea_votes(self):
        return BillVote.objects.filter(bill=self, your_vote='Y').count()

    def count_nay_votes(self):
        return BillVote.objects.filter(bill=self, your_vote='N').count()

    def count_present_votes(self):
        return BillVote.objects.filter(bill=self, your_vote='Pr').count()

    def count_proxy_votes(self):
        return BillVote.objects.filter(bill=self, your_vote='Px').count()

    def count_district_yea_votes(self,district_code):
        return BillVote.objects.filter(bill=self, voter__users__district=district_code,your_vote='Y').count()

    def count_district_nay_votes(self,district_code):
        return BillVote.objects.filter(bill=self, voter__users__district=district_code,your_vote='N').count()

    def count_district_present_votes(self,district_code):
        return BillVote.objects.filter(bill=self, voter__users__district=district_code,your_vote='Pr').count()

    def count_district_proxy_votes(self,district_code):
        return BillVote.objects.filter(bill=self, voter__users__district=district_code,your_vote='Px').count()

class BillVote(models.Model):

    VOTE_CHOICES = [
        ('Y', 'Yea'),
        ('N', 'Nay'),
        ('Pr', 'Present'),
        ('Px', 'Proxy'),
    ]

    bill = models.ForeignKey(Bill, on_delete=models.CASCADE)
    voter = models.ForeignKey(User, on_delete=models.CASCADE)
    voted_by_fDel = models.BooleanField(default=False)
    your_vote = models.CharField(max_length=2, choices=VOTE_CHOICES, default='Px')
    vote_date = models.DateTimeField(auto_now_add=True)
    last_update = models.DateTimeField(auto_now=True)
