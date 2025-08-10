"""
Django management command to test succession line functionality.

Usage:
python manage.py test_succession_line
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from succession_line import succession_manager
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Test succession line functionality'

    def add_arguments(self, parser):
        parser.add_argument(
            '--group-type',
            type=str,
            choices=['circle', 'secdel', 'moda', 'holc', 'districtcouncil'],
            default='circle',
            help='Type of group to test succession for'
        )
        parser.add_argument(
            '--old-delegate',
            type=str,
            required=True,
            help='Username of old delegate'
        )
        parser.add_argument(
            '--new-delegate',
            type=str,
            required=True,
            help='Username of new delegate'
        )

    def handle(self, *args, **options):
        group_type = options['group_type']
        old_delegate_username = options['old_delegate']
        new_delegate_username = options['new_delegate']
        
        try:
            # Get users
            old_delegate = User.objects.get(username=old_delegate_username)
            new_delegate = User.objects.get(username=new_delegate_username)
            
            # Create a mock group instance (you'd normally get this from the actual group)
            class MockGroup:
                def __init__(self, pk):
                    self.pk = pk
                
                def __str__(self):
                    return f"MockGroup({self.pk})"
            
            mock_group = MockGroup(1)
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"Testing succession line for {group_type} group..."
                )
            )
            
            # Test succession line
            with transaction.atomic():
                succession_log = succession_manager.handle_delegate_change(
                    group_type, 
                    old_delegate, 
                    new_delegate, 
                    mock_group
                )
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Succession completed successfully!"
                    )
                )
                
                # Print succession log
                self.stdout.write("Succession Log:")
                for entry in succession_log:
                    self.stdout.write(f"  - {entry}")
                
                # Note: This will be rolled back due to transaction.atomic()
                # Remove this if you want to actually apply changes
                raise Exception("Test completed - rolling back changes")
                
        except User.DoesNotExist as e:
            self.stdout.write(
                self.style.ERROR(f"User not found: {e}")
            )
        except Exception as e:
            if "Test completed" in str(e):
                self.stdout.write(
                    self.style.SUCCESS("Test completed successfully (changes rolled back)")
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f"Error: {e}")
                )
                logger.error(f"Succession test error: {e}", exc_info=True)
