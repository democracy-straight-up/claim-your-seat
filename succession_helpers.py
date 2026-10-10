from django.db.models import F


def remove_dependent_memberships(
    *,
    membership_model,
    user,
    group_field,
    delegate_user_type,
):
    """
    Remove accepted higher-level memberships that depend on a lost
    lower-level delegate mandate.

    If a removed membership held that higher group's delegate office,
    promote the accepted member at succession position 1. Compact the
    remaining succession positions after every removal.
    """
    dependent_memberships = list(
        membership_model.objects.select_for_update().filter(
            user=user,
            is_member=True,
        )
    )

    for dependent_membership in dependent_memberships:
        group = getattr(dependent_membership, group_field)
        was_delegate = dependent_membership.is_delegate
        removed_position = dependent_membership.succession_position

        # Bypass legacy model delete() role transitions. The caller
        # owns the outgoing user's new role after the lower mandate
        # has been lost.
        membership_model.objects.filter(
            pk=dependent_membership.pk
        ).delete()

        if was_delegate:
            successor = (
                membership_model.objects.select_for_update()
                .filter(
                    **{
                        group_field: group,
                        "is_member": True,
                        "succession_position": 1,
                    }
                )
                .first()
            )

            if successor is not None:
                membership_model.objects.filter(
                    pk=successor.pk
                ).update(
                    succession_position=0,
                    is_delegate=True,
                )

                successor.user.users.userType = delegate_user_type
                successor.user.users.save(
                    update_fields=["userType"]
                )

        if removed_position is not None:
            membership_model.objects.filter(
                **{
                    group_field: group,
                    "is_member": True,
                    "succession_position__gt": removed_position,
                }
            ).update(
                succession_position=F("succession_position") - 1
            )

        group.is_active
