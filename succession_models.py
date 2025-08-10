"""
Succession Line Models

Models to track succession line changes for auditing and transparency.
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class SuccessionLog(models.Model):
    """
    Log entry for each succession line event.
    """
    # Event details
    trigger_group_type = models.CharField(max_length=20, help_text="Type of group where change originated")
    trigger_group_id = models.PositiveIntegerField(help_text="ID of group where change originated")
    old_delegate_username = models.CharField(max_length=150, help_text="Username of old delegate")
    new_delegate_username = models.CharField(max_length=150, help_text="Username of new delegate")
    
    # Timestamp
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Status
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('partial', 'Partial Success'),
        ('failed', 'Failed'),
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='success')
    error_message = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['trigger_group_type']),
            models.Index(fields=['old_delegate_username']),
        ]
    
    def __str__(self):
        return f"Succession {self.trigger_group_type} {self.old_delegate_username}->{self.new_delegate_username}"


class SuccessionAction(models.Model):
    """
    Individual action taken during succession process.
    """
    log = models.ForeignKey(SuccessionLog, on_delete=models.CASCADE, related_name='actions')
    
    # Action details
    ACTION_CHOICES = [
        ('removed', 'Removed from group'),
        ('promoted', 'Promoted to delegate'),
        ('demoted', 'Demoted from delegate'),
        ('cascade_removal', 'Cascade removal due to ineligibility'),
    ]
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    
    # Target details
    target_group_type = models.CharField(max_length=20)
    target_group_id = models.PositiveIntegerField(null=True, blank=True)
    target_username = models.CharField(max_length=150)
    
    # Context
    was_delegate = models.BooleanField(default=False)
    promotion_method = models.CharField(max_length=50, blank=True, null=True, 
                                      help_text="How delegate was chosen (votes, earliest_joined, etc)")
    
    # Timestamp
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['timestamp']
    
    def __str__(self):
        return f"{self.action} {self.target_username} in {self.target_group_type}"


class DelegateEligibilityCheck(models.Model):
    """
    Track eligibility checks during succession.
    """
    log = models.ForeignKey(SuccessionLog, on_delete=models.CASCADE, related_name='eligibility_checks')
    
    # Check details
    username = models.CharField(max_length=150)
    target_group_type = models.CharField(max_length=20)
    required_lower_group_type = models.CharField(max_length=20, blank=True, null=True)
    
    # Result
    is_eligible = models.BooleanField()
    reason = models.CharField(max_length=200, blank=True, null=True)
    
    # Timestamp
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['timestamp']
    
    def __str__(self):
        status = "eligible" if self.is_eligible else "ineligible"
        return f"{self.username} {status} for {self.target_group_type}"
