from django.db import models
from django.contrib.auth.models import User
# from vote.models import Circle
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
    congress_url = models.URLField()
    introduced_date = models.DateField(null=True, blank=True)
    sponsors = models.TextField(blank=True, null=True)
    committees = models.TextField(blank=True, null=True)
    committee_meeting = models.DateTimeField(null=True, blank=True)
    latest_action_date = models.DateField(null=True)
    latest_action_text = models.TextField()
    voting_start = models.DateField(blank=True, null=True)
    voting_close = models.DateField(blank=True, null=True)
    schedule_date = models.DateField(blank=True, null=True)
    summary = models.TextField(blank=True, null=True)
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
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name="bill_votes")
    voter = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_votes")
    vote = models.CharField(max_length=2, choices=VOTE_CHOICES, default='Px')
    vote_date = models.DateTimeField(auto_now_add=True)
    last_update = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('bill', 'voter', 'vote')

# type refer to type of the advicement by:
# FD for first delegate
# SD for second delegate
# MD for MoDa
# HL for HoLC
# HR for House Rep
class BillAdvisement(models.Model):
    TYPE_CHOICES = [
        ('FD', 'First Delegate'),
        ('SD', 'Second Delegate'), 
        ('MD', 'MoDa'),
        ('HL', 'HoLC'),
        ('HR', 'House Rep'),
    ]
    
    # refering to the bill
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name="bill_advisements")
    # refering to the user model of adviser.
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bill_advisements") 
    # userType of the adviser
    type = models.CharField(max_length=2, choices=TYPE_CHOICES)  
    # either true for yeah and false for nay
    advisement = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)
    last_update = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('bill', 'user', 'type')
        ordering = ('-created_at',)

    def __str__(self):
        return f"{self.get_type_display()} advisement by {self.user.username} on {self.bill.number}"


class BillUserNotes(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bill_notes')
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name='user_notes')
    note = models.TextField()

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f"Note by {self.user.username} on {self.bill.number}"


class BillFirstDelNotes(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bill_first_del_notes')
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name='first_del_notes')
    note = models.TextField()

    class Meta:
        ordering = ('-created_at',)
        # Removed unique_together to allow multiple notes per first delegate per bill

    def __str__(self):
        return f"First Delegate note by {self.user.username} on {self.bill.number}"


class BillSecondDelNotes(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bill_second_del_notes')
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name='second_del_notes')
    note = models.TextField()

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f"Second Delegate note by {self.user.username} on {self.bill.number}"

class BillModaNotes(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bill_moda_notes')
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name='moda_notes')
    note = models.TextField()

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f"MoDa note by {self.user.username} on {self.bill.number}"
    

class BillHolcNotes(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bill_holc_notes')
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name='holc_notes')
    note = models.TextField()

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f"Holc note by {self.user.username} on {self.bill.number}"

class BillHouseRepNotes(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bill_house_rep_notes')
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name='house_rep_notes')
    note = models.TextField()

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f"HouseRep note by {self.user.username} on {self.bill.number}"


