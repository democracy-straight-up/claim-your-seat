# Succession Line Feature Documentation

## Overview

The Succession Line feature manages the hierarchical delegation system when delegates change in any group level. When a delegate in any group changes through majority voting (putforward votes), it triggers a cascade of changes in higher-level groups.

## Group Hierarchy

```
Circle (Group) → SecDel → Moda → HoLC → DistrictCouncil (Rep)
```

## Core Functionality

### Trigger Event

The succession line is triggered when:

- A delegate in any group is changed through majority putforward votes
- This happens in the `check_put_farward()` method of each member model

### Process Flow

1. **Delegate Change**: When a new delegate is elected in any group
2. **Higher Group Removal**: The old delegate is removed entirely from all higher-level groups
3. **Succession Process**: For each higher group that lost its delegate:
   - Find the next eligible person in that group's succession line
   - Assign them as the new delegate
   - Verify they meet eligibility requirements
4. **Cascade Enforcement**: If the new delegate isn't eligible (not a delegate in required lower group), remove them and continue succession
5. **Logging**: All changes are recorded for auditing

### Succession Line Rules

For each group, the succession line follows this order:

1. **Primary**: Member with the most putforward votes in that group
2. **Fallback**: Earliest joined member (after the removed delegate)

### Eligibility Requirements

To be a delegate in a higher group, a person must be:

- A current delegate in the required lower group:
  - SecDel delegate → must be Circle delegate
  - Moda delegate → must be SecDel delegate
  - HoLC delegate → must be Moda delegate
  - DistrictCouncil delegate → must be HoLC delegate

## Implementation Details

### Files Modified

1. **succession_line.py** - Main succession management system
2. **vote/models.py** - Added succession logging models and updated Circle putforward
3. **api/models.py** - Updated SecDel putforward method
4. **moda/models.py** - Updated Moda putforward method
5. **holc/models.py** - Updated HoLC putforward method
6. **rep/models.py** - Updated DistrictCouncil putforward method

### Database Models

#### SuccessionLog

Tracks each succession event:

- `trigger_group_type` - Type of group where change originated
- `trigger_group_id` - ID of the originating group
- `old_delegate_username` - Previous delegate
- `new_delegate_username` - New delegate
- `status` - Success/Partial/Failed
- `created_at` - Timestamp

#### SuccessionAction

Individual actions during succession:

- `action` - Type of action (removed, promoted, demoted, cascade_removal)
- `target_group_type` - Group where action occurred
- `target_username` - User affected
- `was_delegate` - Whether user was previously a delegate
- `promotion_method` - How delegate was chosen (votes/earliest_joined)

#### DelegateEligibilityCheck

Tracks eligibility verification:

- `username` - User being checked
- `target_group_type` - Group for potential delegation
- `required_lower_group_type` - Required lower group
- `is_eligible` - Whether user meets requirements
- `reason` - Explanation

### Key Classes

#### SuccessionLineManager

Main class managing the succession process:

- `handle_delegate_change()` - Entry point for succession
- `_remove_from_higher_groups()` - Removes old delegate from higher groups
- `_assign_next_delegate()` - Finds and assigns new delegates
- `_is_eligible_for_delegation()` - Checks eligibility requirements

## Usage Examples

### Automatic Triggering

Succession is automatically triggered when any delegate changes through majority putforward votes:

```python
# In GroupMember.check_put_farward():
if self.count_put_forward() >= majority_threshold:
    # ... elect new delegate ...

    # Trigger succession line
    succession_manager.handle_delegate_change(
        'circle',
        old_delegate_user,
        self.user,
        self.group
    )
```

### Manual Testing

Use the management command to test succession:

```bash
python manage.py test_succession_line \
    --group-type circle \
    --old-delegate john_doe \
    --new-delegate jane_smith
```

## Edge Cases Handled

1. **No Eligible Successors**: If no one in a group is eligible for delegation, the delegate position remains vacant
2. **Cascade Removals**: If a promoted delegate isn't eligible, they're removed and succession continues
3. **Circular Dependencies**: The system prevents infinite loops by tracking processed groups
4. **Missing Groups**: If a user isn't in a higher group, they're simply skipped
5. **Multiple Groups**: If a user is in multiple groups of the same type, they're removed from all

## Logging and Auditing

All succession events are logged both:

- **Application Logs**: Using Python logging for debugging
- **Database Logs**: Using SuccessionLog, SuccessionAction, and DelegateEligibilityCheck models

### Viewing Succession History

Query the database models to view succession history:

```python
from vote.models import SuccessionLog

# Recent succession events
recent_successions = SuccessionLog.objects.order_by('-created_at')[:10]

# Actions for a specific succession
succession = SuccessionLog.objects.get(pk=1)
actions = succession.actions.all()
eligibility_checks = succession.eligibility_checks.all()
```

## Important Notes

1. **Transaction Safety**: All succession operations are wrapped in database transactions
2. **Error Handling**: Exceptions are caught and logged, with rollback on failure
3. **Performance**: The system is designed to handle complex hierarchies efficiently
4. **Independence**: Each group's succession is independent - no automatic inheritance from lower groups
5. **Flexibility**: The system can be extended to add new group types or change succession rules

## Future Enhancements

Potential improvements:

1. **Custom Succession Rules**: Allow groups to define their own succession criteria
2. **Notification System**: Alert users when they gain/lose delegate roles
3. **Admin Interface**: Django admin integration for viewing succession logs
4. **API Endpoints**: REST API for succession history and manual succession triggers
5. **Testing Suite**: Comprehensive unit tests for all succession scenarios
