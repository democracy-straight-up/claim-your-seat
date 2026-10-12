from django.db.models import F
from succession_notifications import (
    notify_delegate_promotion_after_removal,
    notify_delegate_vacancy_after_removal,
    post_succession_update,
    user_display_name,
)

def remove_dependent_memberships(
    *,
    membership_model,
    user,
    group_field,
    delegate_user_type,
    message_model=None,
    dependent_group_title=None,
    required_mandate_title=None,
    delegate_title=None,
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

        if (
            message_model is not None
            and dependent_group_title is not None
            and required_mandate_title is not None
        ):
            post_succession_update(
                message_model=message_model,
                group_field=group_field,
                group=group,
                message=(
                    f"Succession update: {user_display_name(user)} was "
                    f"removed from {dependent_group_title} after losing "
                    f"the {required_mandate_title} mandate required for "
                    f"membership."
                ),
            )

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

                if (
                    message_model is not None
                    and dependent_group_title is not None
                    and delegate_title is not None
                ):
                    notify_delegate_promotion_after_removal(
                        message_model=message_model,
                        group_field=group_field,
                        group=group,
                        group_name=dependent_group_title,
                        delegate_title=delegate_title,
                        outgoing_user=user,
                        incoming_user=successor.user,
                    )
            elif (
                message_model is not None
                and dependent_group_title is not None
                and delegate_title is not None
            ):
                notify_delegate_vacancy_after_removal(
                    message_model=message_model,
                    group_field=group_field,
                    group=group,
                    group_name=dependent_group_title,
                    delegate_title=delegate_title,
                    outgoing_user=user,
                )

        if removed_position is not None:
            compacted_memberships = list(
                membership_model.objects.select_for_update()
                .filter(
                    **{
                        group_field: group,
                        "is_member": True,
                        "succession_position__gt": removed_position,
                    }
                )
                .order_by("succession_position")
            )

            membership_model.objects.filter(
                **{
                    group_field: group,
                    "is_member": True,
                    "succession_position__gt": removed_position,
                }
            ).update(
                succession_position=F("succession_position") - 1
            )

            if message_model is not None:
                removed_name = user_display_name(user)

                for compacted_membership in compacted_memberships:
                    old_position = (
                        compacted_membership.succession_position
                    )
                    new_position = old_position - 1
                    compacted_name = user_display_name(
                        compacted_membership.user
                    )

                    post_succession_update(
                        message_model=message_model,
                        group_field=group_field,
                        group=group,
                        message=(
                            f"Succession update: {compacted_name} moved "
                            f"from position {old_position} to position "
                            f"{new_position} after {removed_name} was "
                            f"removed."
                        ),
                    )

        group.is_active
