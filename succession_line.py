"""
Succession Line Management System

This module implements the succession line feature where delegate changes trigger
removal from higher groups and succession within each group's own hierarchy.

Group Hierarchy:
Circle (Group) → SecDel → Moda → HoLC → DistrictCouncil (Rep)
"""

import logging
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

# Import all models
from vote import models as vote_models
from api import models as api_models
from moda import models as moda_models
from holc import models as holc_models
from rep import models as rep_models

# Import succession logging models
try:
    from vote.models import SuccessionLog, SuccessionAction, DelegateEligibilityCheck
except ImportError:
    # Fallback if models haven't been migrated yet
    SuccessionLog = None
    SuccessionAction = None
    DelegateEligibilityCheck = None

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SuccessionLineManager:
    """
    Manages succession line when delegates change in any group level.
    """
    
    # Define the hierarchy mapping
    GROUP_HIERARCHY = {
        'circle': {
            'model': vote_models.Group,
            'member_model': vote_models.GroupMember,
            'putforward_model': vote_models.CircleMember_put_forward,
            'next_level': 'secdel',
            'user_type_delegate': 'U1D1',
            'user_type_member': 'U1D0',
            'user_type_fallback': 'U0D0'
        },
        'secdel': {
            'model': api_models.SecDelModel,
            'member_model': api_models.SecDelMembers,
            'putforward_model': api_models.PutFarwardSecDelMember,
            'next_level': 'moda',
            'user_type_delegate': 'U2D2',
            'user_type_member': 'U2D1',
            'user_type_fallback': 'U1D1'
        },
        'moda': {
            'model': moda_models.ModaModel,
            'member_model': moda_models.ModaMembers,
            'putforward_model': moda_models.PutFarwardModaMember,
            'next_level': 'holc',
            'user_type_delegate': 'U3D3',
            'user_type_member': 'U3D2',
            'user_type_fallback': 'U2D2'
        },
        'holc': {
            'model': holc_models.HolcModel,
            'member_model': holc_models.HolcMembers,
            'putforward_model': holc_models.PutForwardHolcMember,
            'next_level': 'districtcouncil',
            'user_type_delegate': 'U4D4',
            'user_type_member': 'U4D3',
            'user_type_fallback': 'U3D3'
        },
        'districtcouncil': {
            'model': rep_models.DistrictCouncil,
            'member_model': rep_models.DistrictCouncilMembers,
            'putforward_model': rep_models.PutForwardDistrictCouncilMember,
            'next_level': None,
            'user_type_delegate': 'U5D5',
            'user_type_member': 'U5D4',
            'user_type_fallback': 'U4D4'
        }
    }

    def __init__(self):
        self.succession_log = []
        self.db_log = None  # Database log entry
        self.affected_groups = {}  # Track which specific groups were affected by removal
        
    @transaction.atomic
    def handle_delegate_change(self, group_type, old_delegate_user, new_delegate_user, group_instance):
        """
        Main entry point for handling delegate changes.
        
        Args:
            group_type (str): Type of group ('circle', 'secdel', 'moda', 'holc', 'districtcouncil')
            old_delegate_user (User): User who was the previous delegate
            new_delegate_user (User): User who is the new delegate
            group_instance: Instance of the group where change occurred
        """
        try:
            self.succession_log = []
            self.affected_groups = {}  # Reset affected groups tracking
            
            # Create database log entry
            if SuccessionLog:
                self.db_log = SuccessionLog.objects.create(
                    trigger_group_type=group_type,
                    trigger_group_id=group_instance.pk,
                    old_delegate_username=old_delegate_user.username,
                    new_delegate_username=new_delegate_user.username,
                    status='success'
                )
            
            logger.info(f"Starting succession process for {group_type} group {group_instance}")
            
            # Step 1: Remove old delegate from all higher level groups
            self._remove_from_higher_groups(group_type, old_delegate_user)
            
            # Step 2: Handle succession in higher groups that were affected
            self._handle_higher_group_succession(group_type, old_delegate_user)
            
            # Step 3: Log the succession process
            self._log_succession(group_type, old_delegate_user, new_delegate_user, group_instance)
            
            logger.info(f"Succession process completed successfully for {group_type}")
            return self.succession_log
            
        except Exception as e:
            logger.error(f"Error in succession process: {str(e)}")
            if self.db_log:
                self.db_log.status = 'failed'
                self.db_log.error_message = str(e)
                self.db_log.save()
            raise

    def _remove_from_higher_groups(self, current_group_type, user):
        """
        Remove user from all higher level groups.
        """
        current_level = self._get_group_level(current_group_type)
        
        for group_type, config in self.GROUP_HIERARCHY.items():
            group_level = self._get_group_level(group_type)
            
            # Only process higher level groups
            if group_level > current_level:
                self._remove_user_from_group_type(group_type, user)

    def _remove_user_from_group_type(self, group_type, user):
        """
        Remove user from all groups of a specific type where they are a member.
        Track which specific groups were affected for later succession processing.
        Properly update user's type and verification score based on their remaining highest membership.
        """
        config = self.GROUP_HIERARCHY[group_type]
        member_model = config['member_model']
        
        try:
            # Find all memberships for this user in this group type
            memberships = member_model.objects.filter(user=user)
            
            # Initialize affected groups list for this group type
            if group_type not in self.affected_groups:
                self.affected_groups[group_type] = []
            
            for membership in memberships:
                was_delegate = membership.is_delegate
                was_member = membership.is_member
                group_instance = self._get_group_from_membership(membership, group_type)
                
                # Track this group as affected only if user was a delegate
                if was_delegate and group_instance:
                    self.affected_groups[group_type].append(group_instance)
                
                self.succession_log.append({
                    'action': 'removed',
                    'group_type': group_type,
                    'group_id': group_instance.pk if group_instance else None,
                    'user': user.username,
                    'was_delegate': was_delegate,
                    'was_member': was_member,
                    'timestamp': timezone.now()
                })
                
                # Log to database
                if SuccessionAction and self.db_log:
                    SuccessionAction.objects.create(
                        log=self.db_log,
                        action='removed',
                        target_group_type=group_type,
                        target_group_id=group_instance.pk if group_instance else None,
                        target_username=user.username,
                        was_delegate=was_delegate
                    )
                
                # Delete the membership - this will trigger cascade succession if they were delegate
                membership.delete()
                
                logger.info(f"Removed {user.username} from {group_type} group {group_instance} (was_delegate: {was_delegate}, was_member: {was_member})")
            
            # After removing from all groups of this type, update user's type and verification score
            # based on their highest remaining membership
            self._update_user_type_after_removal(user, group_type)
                
        except Exception as e:
            logger.error(f"Error removing user {user.username} from {group_type}: {str(e)}")

    def _update_user_type_after_removal(self, user, removed_from_group_type):
        """
        Update user's type and verification score based on their highest remaining membership
        after being removed from a group type.
        """
        try:
            # Find the user's highest remaining membership level
            highest_membership = self._find_highest_membership(user)
            
            if highest_membership:
                group_type, is_delegate, is_member, verification_score = highest_membership
                config = self.GROUP_HIERARCHY[group_type]
                
                if is_delegate:
                    new_user_type = config['user_type_delegate']
                elif is_member:
                    new_user_type = config['user_type_member']
                else:
                    new_user_type = config['user_type_fallback']
                
                # Update user type and verification score
                user.users.userType = new_user_type
                user.users.verificationScore = verification_score
                user.users.save()
                
                logger.info(f"Updated {user.username} userType to {new_user_type} with verification score {verification_score} after removal from {removed_from_group_type}")
                
                # Log this update
                if SuccessionAction and self.db_log:
                    SuccessionAction.objects.create(
                        log=self.db_log,
                        action='user_type_update',
                        target_group_type=group_type,
                        target_username=user.username,
                        was_delegate=is_delegate,
                        promotion_method=f'fallback_after_{removed_from_group_type}_removal'
                    )
            else:
                # User has no remaining memberships, set to base type
                user.users.userType = 'U0D0'
                user.users.verificationScore = 0
                user.users.save()
                
                logger.info(f"Updated {user.username} to base userType U0D0 after removal from {removed_from_group_type} (no remaining memberships)")
                
        except Exception as e:
            logger.error(f"Error updating user type for {user.username} after removal from {removed_from_group_type}: {str(e)}")

    def _find_highest_membership(self, user):
        """
        Find the user's highest remaining membership level across all group types.
        Returns tuple: (group_type, is_delegate, is_member, verification_score) or None
        """
        highest_level = -1
        highest_membership = None
        
        # Check memberships in order from highest to lowest level
        for group_type, config in self.GROUP_HIERARCHY.items():
            group_level = self._get_group_level(group_type)
            member_model = config['member_model']
            
            try:
                # Find active memberships for this user in this group type
                memberships = member_model.objects.filter(user=user, is_member=True)
                
                for membership in memberships:
                    if group_level > highest_level:
                        highest_level = group_level
                        
                        # Determine verification score based on group status
                        group_instance = self._get_group_from_membership(membership, group_type)
                        verification_score = self._get_verification_score_for_group(group_instance, group_type, membership.is_delegate)
                        
                        highest_membership = (group_type, membership.is_delegate, membership.is_member, verification_score)
                        
            except Exception as e:
                logger.error(f"Error checking {group_type} memberships for {user.username}: {str(e)}")
        
        return highest_membership

    def _get_verification_score_for_group(self, group_instance, group_type, is_delegate):
        """
        Get the appropriate verification score for a group membership.
        """
        try:
            # Check if group is active and get appropriate verification score
            if hasattr(group_instance, 'is_active') and group_instance.is_active:
                # Active group scores
                if group_type == 'circle':
                    return 10
                elif group_type == 'secdel':
                    return 100 
                elif group_type == 'moda':
                    return 1000
                elif group_type == 'holc':
                    return 10000
                elif group_type == 'districtcouncil':
                    return 100000
            else:
                # Inactive group scores (usually lower)
                if group_type == 'circle':
                    return 2
                elif group_type == 'secdel':
                    return 10
                elif group_type == 'moda':
                    return 100
                elif group_type == 'holc':
                    return 1000
                elif group_type == 'districtcouncil':
                    return 10000
                    
        except Exception as e:
            logger.error(f"Error getting verification score for {group_type}: {str(e)}")
            
        # Fallback verification scores
        return 0

    def _handle_higher_group_succession(self, current_group_type, removed_user):
        """
        Handle succession only in the specific higher groups that were affected by delegate removal.
        """
        current_level = self._get_group_level(current_group_type)
        
        for group_type, config in self.GROUP_HIERARCHY.items():
            group_level = self._get_group_level(group_type)
            
            # Only process higher level groups that were actually affected
            if group_level > current_level and group_type in self.affected_groups:
                affected_group_instances = self.affected_groups[group_type]
                if affected_group_instances:
                    logger.info(f"Processing succession for {len(affected_group_instances)} {group_type} groups that lost delegate {removed_user.username}")
                    self._trigger_succession_for_specific_groups(group_type, affected_group_instances)

    def _trigger_succession_for_specific_groups(self, group_type, affected_group_instances):
        """
        Trigger succession only for specific group instances that lost their delegate.
        """
        try:
            # Handle succession for each affected group
            for group_instance in affected_group_instances:
                logger.info(f"Assigning new delegate for {group_type} group {group_instance}")
                self._assign_next_delegate(group_type, group_instance)
                
        except Exception as e:
            logger.error(f"Error triggering succession for specific {group_type} groups: {str(e)}")

    def _assign_next_delegate(self, group_type, group_instance, recursion_depth=0):
        """
        Assign the next delegate for a group using succession line.
        
        Args:
            group_type: Type of group
            group_instance: Specific group instance
            recursion_depth: Track recursion depth to prevent infinite loops
        """
        # Prevent infinite recursion
        if recursion_depth > 10:
            logger.warning(f"Maximum recursion depth reached for {group_type} group {group_instance}")
            return None
            
        config = self.GROUP_HIERARCHY[group_type]
        member_model = config['member_model']
        putforward_model = config['putforward_model']
        
        try:
            # Get all current members
            members = self._get_group_members(group_instance, member_model)
            
            if not members.exists():
                logger.info(f"No members available for succession in {group_type} group {group_instance}")
                return None
            
            # Strategy 1: Try to find member with most putforward votes
            next_delegate = self._find_member_with_most_votes(members, putforward_model)
            
            # Strategy 2: If no votes, use earliest joined member
            if not next_delegate:
                next_delegate = self._find_earliest_joined_member(members)
            
            if next_delegate:
                # Verify they are eligible (delegate in required lower group)
                if self._is_eligible_for_delegation(next_delegate, group_type):
                    self._promote_to_delegate(next_delegate, group_type)
                    
                    self.succession_log.append({
                        'action': 'promoted',
                        'group_type': group_type,
                        'group_id': group_instance.pk,
                        'user': next_delegate.user.username,
                        'method': 'succession_line',
                        'timestamp': timezone.now()
                    })
                    
                    # Log to database
                    if SuccessionAction and self.db_log:
                        promotion_method = 'most_votes' if self._find_member_with_most_votes([next_delegate], putforward_model) else 'earliest_joined'
                        SuccessionAction.objects.create(
                            log=self.db_log,
                            action='promoted',
                            target_group_type=group_type,
                            target_group_id=group_instance.pk,
                            target_username=next_delegate.user.username,
                            was_delegate=False,
                            promotion_method=promotion_method
                        )
                    
                    logger.info(f"Promoted {next_delegate.user.username} to delegate in {group_type} group {group_instance}")
                    return next_delegate
                else:
                    # Cascade removal if not eligible - but DON'T trigger full succession chain
                    logger.info(f"Member {next_delegate.user.username} not eligible for {group_type} delegate, removing from this group only")
                    
                    # Log the cascade removal
                    if SuccessionAction and self.db_log:
                        SuccessionAction.objects.create(
                            log=self.db_log,
                            action='cascade_removal',
                            target_group_type=group_type,
                            target_group_id=group_instance.pk,
                            target_username=next_delegate.user.username,
                            was_delegate=False,
                            promotion_method='ineligible'
                        )
                    
                    next_delegate.delete()
                    # Recursive call with increased depth counter
                    return self._assign_next_delegate(group_type, group_instance, recursion_depth + 1)
            
            logger.info(f"No eligible delegates found for {group_type} group {group_instance}")
            return None
            
        except Exception as e:
            logger.error(f"Error assigning delegate for {group_type} group {group_instance}: {str(e)}")
            return None

    def _find_member_with_most_votes(self, members, putforward_model):
        """
        Find member with highest number of putforward votes.
        """
        try:
            best_member = None
            most_votes = 0
            
            for member in members:
                vote_count = putforward_model.objects.filter(candidate=member).count()
                if vote_count > most_votes:
                    most_votes = vote_count
                    best_member = member
            
            return best_member if most_votes > 0 else None
            
        except Exception as e:
            logger.error(f"Error finding member with most votes: {str(e)}")
            return None

    def _find_earliest_joined_member(self, members):
        """
        Find the member who joined earliest (after any removed delegate).
        """
        try:
            return members.order_by('joined_at').first()
        except Exception as e:
            logger.error(f"Error finding earliest joined member: {str(e)}")
            return None

    def _is_eligible_for_delegation(self, member, group_type):
        """
        Check if member is eligible for delegation (must be delegate in required lower group).
        """
        if group_type == 'circle':
            return True  # Circle is the base level
        
        # Get required lower group type
        required_lower_group = self._get_required_lower_group(group_type)
        if not required_lower_group:
            return True
        
        # Check if user is delegate in required lower group
        is_eligible = self._is_delegate_in_group_type(member.user, required_lower_group)
        
        # Log eligibility check
        if DelegateEligibilityCheck and self.db_log:
            reason = f"Must be delegate in {required_lower_group}" if not is_eligible else "Meets requirements"
            DelegateEligibilityCheck.objects.create(
                log=self.db_log,
                username=member.user.username,
                target_group_type=group_type,
                required_lower_group_type=required_lower_group,
                is_eligible=is_eligible,
                reason=reason
            )
        
        return is_eligible

    def _is_delegate_in_group_type(self, user, group_type):
        """
        Check if user is currently a delegate in any group of the specified type.
        """
        config = self.GROUP_HIERARCHY[group_type]
        member_model = config['member_model']
        
        try:
            return member_model.objects.filter(user=user, is_delegate=True, is_member=True).exists()
        except Exception as e:
            logger.error(f"Error checking delegate status for {user.username} in {group_type}: {str(e)}")
            return False

    def _promote_to_delegate(self, member, group_type):
        """
        Promote member to delegate and update their user type.
        """
        config = self.GROUP_HIERARCHY[group_type]
        
        member.is_delegate = True
        member.user.users.userType = config['user_type_delegate']
        member.user.users.save()
        member.save()

    def _get_group_level(self, group_type):
        """
        Get numeric level of group type (0=circle, 1=secdel, etc.)
        """
        levels = {'circle': 0, 'secdel': 1, 'moda': 2, 'holc': 3, 'districtcouncil': 4}
        return levels.get(group_type, 0)

    def _get_required_lower_group(self, group_type):
        """
        Get the required lower group type for delegation eligibility.
        """
        requirements = {
            'secdel': 'circle',
            'moda': 'secdel', 
            'holc': 'moda',
            'districtcouncil': 'holc'
        }
        return requirements.get(group_type)

    def _get_group_from_membership(self, membership, group_type):
        """
        Get the group instance from membership based on group type.
        """
        if group_type == 'circle':
            return membership.group
        elif group_type == 'secdel':
            return membership.sec_del
        elif group_type == 'moda':
            return membership.moda
        elif group_type == 'holc':
            return membership.holc
        elif group_type == 'districtcouncil':
            return membership.district_council
        return None

    def _get_current_delegate(self, group_instance, member_model):
        """
        Get current delegate for a group instance.
        """
        try:
            if hasattr(group_instance, 'groupmember_set'):
                return group_instance.groupmember_set.filter(is_delegate=True, is_member=True).first()
            elif hasattr(group_instance, 'secdelmembers_set'):
                return group_instance.secdelmembers_set.filter(is_delegate=True, is_member=True).first()
            elif hasattr(group_instance, 'modamembers_set'):
                return group_instance.modamembers_set.filter(is_delegate=True, is_member=True).first()
            elif hasattr(group_instance, 'holcmembers_set'):
                return group_instance.holcmembers_set.filter(is_delegate=True, is_member=True).first()
            elif hasattr(group_instance, 'districtcouncilmembers_set'):
                return group_instance.districtcouncilmembers_set.filter(is_delegate=True, is_member=True).first()
        except Exception as e:
            logger.error(f"Error getting current delegate: {str(e)}")
        return None

    def _get_group_members(self, group_instance, member_model):
        """
        Get all members of a group instance.
        """
        try:
            if hasattr(group_instance, 'groupmember_set'):
                return group_instance.groupmember_set.filter(is_member=True)
            elif hasattr(group_instance, 'secdelmembers_set'):
                return group_instance.secdelmembers_set.filter(is_member=True)
            elif hasattr(group_instance, 'modamembers_set'):
                return group_instance.modamembers_set.filter(is_member=True)
            elif hasattr(group_instance, 'holcmembers_set'):
                return group_instance.holcmembers_set.filter(is_member=True)
            elif hasattr(group_instance, 'districtcouncilmembers_set'):
                return group_instance.districtcouncilmembers_set.filter(is_member=True)
        except Exception as e:
            logger.error(f"Error getting group members: {str(e)}")
        return member_model.objects.none()

    def _log_succession(self, group_type, old_delegate, new_delegate, group_instance):
        """
        Log the succession process for auditing.
        """
        log_entry = {
            'trigger_group_type': group_type,
            'trigger_group_id': group_instance.pk,
            'old_delegate': old_delegate.username,
            'new_delegate': new_delegate.username,
            'timestamp': timezone.now(),
            'succession_actions': self.succession_log.copy()
        }
        
        # Here you could save to a succession log table if needed
        logger.info(f"Succession log: {log_entry}")
        
        return log_entry

# Singleton instance
succession_manager = SuccessionLineManager()
