# HOLC Model Updates Summary

## Overview

This document summarizes the updates made to the HOLC (House of Local Councils) model and its integration with the Moda (S-Link) model.

## HOLC Model Changes

### 1. Code Field (1-10 Range)

- **Changed**: Code now ranges from 1 to 10 (previously 10-99)
- **Unique**: Each code must be unique
- **Validation**: System prevents creation if code is outside 1-10 range
- **Max Limit**: Maximum of 10 HOLC instances can exist globally

### 2. Invitation Key

- **Status**: Changed to `null=True, blank=True`
- **Usage**: Not currently in use
- **Note**: Helper function `generate_unique_invitation_key()` preserved for potential future use

### 3. Vote In/Out Models

- **Removed**: `VoteInHolcMember` model completely removed
- **Removed**: `VoteOutHolcMember` model completely removed
- **Removed Methods**:
  - `count_vote_in()`
  - `count_vote_out()`
  - `check_for_majority()`
  - `check_for_removing()`

### 4. Active Status

- **Status**: KEPT (this was initially removed but restored)
- **Field**: `status` BooleanField exists
- **Property**: `is_active` property checks if member count is between 3-12
- **Behavior**:
  - Active when 3 ≤ members ≤ 12
  - Updates verification scores when status changes

### 5. Maximum Membership

- **Max Members**: 12 (not 20)
- **Active Range**: 3 to 12 members
- **Validation**: MaxMembershipReached exception when > 12 members

## Moda → HOLC Integration

### When Moda Becomes Active

When a Moda's status changes to active (3-12 members), the delegate is automatically assigned to a HOLC:

#### Assignment Logic:

1. **Check if already in HOLC**: If delegate is already a HOLC member, skip assignment

2. **If HOLCs exist in the district**:

   - Find a HOLC with < 12 members
   - If found: Add delegate as **member** (not delegate)
   - If all HOLCs are full (12/12): Create **new HOLC** and make delegate the **HOLC delegate**

3. **If no HOLCs exist in the district**:
   - Create new HOLC
   - Make Moda delegate the **HOLC delegate**

#### Error Handling:

- If all 10 HOLC codes are used: Log error, cannot create more HOLCs
- Graceful error handling with logging

## Models Present in HOLC

### 1. HolcModel

- Main HOLC model with code (1-10), district, status
- Methods: `save()`, `delete()`, `is_active` property, `member_count` property

### 2. HolcMembers

- Members of HOLC with delegate status
- Fields: user, holc, is_delegate, is_member
- Methods: `save()`, `delete()`, `count_put_forward()`, `check_put_forward()`

### 3. PutForwardHolcMember

- Voting to put forward a new delegate
- Triggers delegate change when majority reached

### 4. HolcMemberContact

- Contact information for HOLC members
- Automatically created when member joins

### 5. HolcBackNForthChat

- Chat messages for HOLC conversations
- Supports replies, editing, soft delete

### 6. MaxMembershipReached

- Custom validation exception
- Raised when membership exceeds 12

## User Type Codes

### HOLC Member Types:

- **U4D4**: HOLC Delegate (verification score: 10000 when active)
- **U4D3**: HOLC Member (verification score: 10000 when active)
- **U3D3**: Default/Removed member (verification score: 1000)

### Moda Member Types:

- **U3D3**: Moda Delegate (verification score: 1000 when active)
- **U3D2**: Moda Member (verification score: 1000 when active)
- **U2D2**: Default/Removed member (verification score: 100)

## Succession Line Integration

- HOLC delegate changes trigger succession line updates
- Integrates with higher groups through `succession_manager.handle_delegate_change()`
- Proper error handling and logging

## Summary Checklist

✅ Code limited to 1-10 (unique)
✅ Invitation key set to null/blank (not used)
✅ Vote In/Out models removed
✅ Active status KEPT and working
✅ Max membership set to 12
✅ Moda → HOLC auto-assignment implemented
✅ Handles maxed-out HOLCs by creating new ones
✅ All default features present (PutForward, Contact, Chat, etc.)
✅ Proper user type management
✅ Succession line integration
