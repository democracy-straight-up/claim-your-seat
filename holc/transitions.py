from django.core.exceptions import ValidationError
from django.db import transaction

from holc.models import (
    CaucusAdmissionVote,
    CaucusExpulsionVote,
    HolcMembers,
    HolcModel,
)

from moda.models import ModaMembers


@transaction.atomic
def return_eligible_delegate_to_general(membership):
    """
    Move an eligible Caucus Delegate from an ordinary Caucus back to
    General Caucus while preserving the underlying Second Link mandate.

    This transition is used when an eligible delegate leaves or is
    removed from an ordinary Caucus without simultaneously joining
    another Caucus.
    """
    membership = (
        HolcMembers.objects.select_for_update()
        .select_related("holc", "user", "user__users")
        .get(pk=membership.pk)
    )

    if not membership.is_member:
        raise ValidationError(
            "Only an accepted Caucus member can return to General Caucus."
        )

    if membership.is_delegate:
        raise ValidationError(
            "A HoLC must relinquish that office before leaving the Caucus."
        )

    if membership.holc.code == 1:
        raise ValidationError(
            "A General Caucus membership cannot transition to General Caucus."
        )

    user = membership.user
    ordinary_caucus = membership.holc
    district = ordinary_caucus.district

    has_active_delegate_mandate = ModaMembers.objects.select_for_update().filter(
        user=user,
        is_member=True,
        is_delegate=True,
        moda__district=district,
        moda__status=True,
    ).exists()

    if not has_active_delegate_mandate:
        raise ValidationError(
            "An active Second Link delegate mandate is required "
            "to return to General Caucus."
        )

    general_caucus = HolcModel.objects.select_for_update().get(
        district=district,
        code=1,
    )

    # Bypass the legacy HolcMembers.delete() role transition,
    # which still writes obsolete U3D3.
    HolcMembers.objects.filter(pk=membership.pk).delete()

    general_membership, _ = HolcMembers.objects.get_or_create(
        user=user,
        holc=general_caucus,
        defaults={
            "is_member": True,
            "is_delegate": False,
        },
    )

    if not general_membership.is_member:
        general_membership.is_member = True
        general_membership.save(
            update_fields=[
                "is_member",
                "updated_at",
            ]
        )

    # Preserve the model's existing first-member/HoLC behavior if General
    # Caucus ever has no incumbent HoLC.
    user.users.userType = (
        "U4D4" if general_membership.is_delegate else "U4D3"
    )
    user.users.save(update_fields=["userType"])

    ordinary_caucus.is_active
    general_caucus.is_active

    return general_membership


@transaction.atomic
def cast_caucus_admission_vote(*, voter, pending_membership):
    """
    Record one admission vote from an accepted member of the destination
    Caucus and complete the transfer when a majority is reached.
    """
    pending_membership = (
        HolcMembers.objects.select_for_update()
        .select_related("holc", "user")
        .get(pk=pending_membership.pk)
    )

    if pending_membership.is_member:
        raise ValidationError(
            "Admission votes can only be cast on a pending application."
        )

    destination_caucus = pending_membership.holc

    if destination_caucus.code == 1:
        raise ValidationError(
            "General Caucus membership is assigned automatically."
        )

    is_accepted_member = HolcMembers.objects.select_for_update().filter(
        user=voter,
        holc=destination_caucus,
        is_member=True,
    ).exists()

    if not is_accepted_member:
        raise ValidationError(
            "Only an accepted member of the destination Caucus "
            "may vote on an application."
        )

    _, created = CaucusAdmissionVote.objects.get_or_create(
        voter=voter,
        application=pending_membership,
    )

    if not created:
        raise ValidationError(
            "This member has already voted on this application."
        )

    accepted_member_count = HolcMembers.objects.filter(
        holc=destination_caucus,
        is_member=True,
    ).count()
    majority_votes = accepted_member_count // 2 + 1

    current_accepted_voter_ids = HolcMembers.objects.filter(
        holc=destination_caucus,
        is_member=True,
    ).values_list("user_id", flat=True)

    admission_vote_count = CaucusAdmissionVote.objects.filter(
        application=pending_membership,
        voter_id__in=current_accepted_voter_ids,
    ).count()

    if admission_vote_count >= majority_votes:
        return accept_eligible_delegate_into_caucus(
            pending_membership
        )

    return pending_membership


@transaction.atomic
def accept_eligible_delegate_into_caucus(pending_membership):
    """
    Accept a pending Caucus application and transfer the eligible
    delegate from their current accepted Caucus to the destination.

    The applicant keeps the existing Caucus membership until this
    transition completes successfully.
    """
    pending_membership = (
        HolcMembers.objects.select_for_update()
        .select_related("holc", "user", "user__users")
        .get(pk=pending_membership.pk)
    )

    if pending_membership.is_member:
        raise ValidationError(
            "Only a pending Caucus application can be accepted."
        )

    if pending_membership.is_delegate:
        raise ValidationError(
            "A pending Caucus applicant cannot already hold HoLC office."
        )

    destination_caucus = pending_membership.holc

    if destination_caucus.code == 1:
        raise ValidationError(
            "General Caucus membership is assigned automatically."
        )

    user = pending_membership.user
    district = destination_caucus.district

    has_active_delegate_mandate = (
        ModaMembers.objects.select_for_update()
        .filter(
            user=user,
            is_member=True,
            is_delegate=True,
            moda__district=district,
            moda__status=True,
        )
        .exists()
    )

    if not has_active_delegate_mandate:
        raise ValidationError(
            "An active Second Link delegate mandate is required "
            "to join a Caucus."
        )

    current_memberships = list(
        HolcMembers.objects.select_for_update()
        .select_related("holc")
        .filter(
            user=user,
            is_member=True,
            holc__district=district,
        )
    )

    if len(current_memberships) != 1:
        raise ValidationError(
            "A Caucus Delegate must have exactly one accepted "
            "Caucus membership before transferring."
        )

    current_membership = current_memberships[0]

    if current_membership.is_delegate:
        raise ValidationError(
            "A HoLC must relinquish that office before switching Caucuses."
        )

    source_caucus = current_membership.holc

    # Bypass the legacy HolcMembers.delete() role transition,
    # which still writes obsolete U3D3.
    HolcMembers.objects.filter(pk=current_membership.pk).delete()

    pending_membership.is_member = True
    pending_membership.is_delegate = False
    pending_membership.save(
        update_fields=[
            "is_member",
            "is_delegate",
            "updated_at",
        ]
    )

    user.users.userType = "U4D3"
    user.users.save(update_fields=["userType"])

    source_caucus.is_active
    destination_caucus.is_active

    return pending_membership


@transaction.atomic
def cast_caucus_expulsion_vote(*, voter, target_membership):
    """
    Record one expulsion vote from an accepted member of an ordinary
    Caucus and return the target to General Caucus when a majority
    is reached.
    """
    target_membership = (
        HolcMembers.objects.select_for_update()
        .select_related("holc", "user")
        .get(pk=target_membership.pk)
    )

    if not target_membership.is_member:
        raise ValidationError(
            "Expulsion votes can only target an accepted Caucus member."
        )

    if target_membership.is_delegate:
        raise ValidationError(
            "A HoLC must relinquish that office before ordinary expulsion."
        )

    caucus = target_membership.holc

    if caucus.code == 1:
        raise ValidationError(
            "General Caucus membership cannot use ordinary expulsion."
        )

    is_accepted_member = HolcMembers.objects.select_for_update().filter(
        user=voter,
        holc=caucus,
        is_member=True,
    ).exists()

    if not is_accepted_member:
        raise ValidationError(
            "Only an accepted member of the Caucus may vote "
            "on an expulsion."
        )

    _, created = CaucusExpulsionVote.objects.get_or_create(
        voter=voter,
        target_user=target_membership.user,
        caucus=caucus,
        target_membership_id=target_membership.pk,
    )

    if not created:
        raise ValidationError(
            "This member has already voted on this expulsion."
        )

    accepted_member_count = HolcMembers.objects.filter(
        holc=caucus,
        is_member=True,
    ).count()
    majority_votes = accepted_member_count // 2 + 1

    current_accepted_voter_ids = HolcMembers.objects.filter(
        holc=caucus,
        is_member=True,
    ).values_list("user_id", flat=True)

    expulsion_vote_count = CaucusExpulsionVote.objects.filter(
        caucus=caucus,
        target_membership_id=target_membership.pk,
        voter_id__in=current_accepted_voter_ids,
    ).count()

    if expulsion_vote_count >= majority_votes:
        return expel_eligible_delegate_to_general(
            target_membership
        )

    return target_membership


def expel_eligible_delegate_to_general(membership):
    """
    Return an otherwise eligible Caucus Delegate to General Caucus
    after a completed expulsion from an ordinary Caucus.

    Expulsion and voluntary exit share the same membership transition;
    this named entry point keeps the domain intent explicit for the
    eventual vote-out workflow.
    """
    return return_eligible_delegate_to_general(membership)
