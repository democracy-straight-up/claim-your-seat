from django.db import models

# Create your models here.
class TestingModel(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField(max_length=255)
    status = models.PositiveSmallIntegerField(default=0)
    is_test = models.BooleanField(default=False)
    tagline = models.TextField(max_length=2000)
    schedule_date = models.DateField(blank=True, null=True)