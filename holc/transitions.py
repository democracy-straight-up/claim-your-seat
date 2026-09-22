from django.core.exceptions import ValidationError
from django.db import transaction

from holc.models import HolcMembers, HolcModel
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


def expel_eligible_delegate_to_general(membership):
    """
    Return an otherwise eligible Caucus Delegate to General Caucus
    after a completed expulsion from an ordinary Caucus.

    Expulsion and voluntary exit share the same membership transition;
    this named entry point keeps the domain intent explicit for the
    eventual vote-out workflow.
    """
    return return_eligible_delegate_to_general(membership)
