from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import F

from moda.models import ModaBackNForthChat, ModaMembers, ModaModel
from succession_notifications import (
    post_succession_update,
    user_display_name,
)


def remove_second_link_member_as_delegate(*, moda, actor, membership_pk):
    with transaction.atomic():
        # Lock the group while performing this membership transition.
        second_link = ModaModel.objects.select_for_update().get(
            pk=moda.pk
        )

        # Recheck authority inside the transaction.
        is_delegate = ModaMembers.objects.filter(
            moda=second_link,
            user=actor,
            is_member=True,
            is_delegate=True,
        ).exists()

        if not is_delegate:
            raise PermissionDenied(
                "Only the current Caucus Delegate may perform this action."
            )

        member = ModaMembers.objects.select_for_update().get(
            pk=membership_pk,
            moda=second_link,
        )

        # A delegate cannot use this operation to abandon her office.
        if member.is_member and member.is_delegate:
            raise PermissionDenied(
                "A sitting Caucus Delegate cannot remove herself "
                "through ordinary Housekeeping departure."
            )

        was_member = member.is_member
        removed_position = member.succession_position
        removed_name = user_display_name(member.user)
        actor_name = user_display_name(actor)

        compacted_memberships = []

        if was_member and removed_position is not None:
            compacted_memberships = list(
                ModaMembers.objects.select_for_update()
                .filter(
                    moda=second_link,
                    is_member=True,
                    succession_position__gt=removed_position,
                )
                .order_by("succession_position")
            )

        # The existing model deletion also updates the departing
        # user's role.
        member.delete()

        if was_member:
            action_message = (
                f"Housekeeping: {actor_name}, acting on behalf of "
                f"{removed_name}, ended {removed_name}'s membership "
                f"in the Second Link."
            )
        else:
            action_message = (
                f"Housekeeping: {actor_name} withdrew "
                f"{removed_name}'s Second Link candidacy."
            )

        post_succession_update(
            message_model=ModaBackNForthChat,
            group_field="moda",
            group=second_link,
            message=action_message,
        )

        if compacted_memberships:
            ModaMembers.objects.filter(
                pk__in=[m.pk for m in compacted_memberships]
            ).update(
                succession_position=F("succession_position") - 1
            )

            for moved_member in compacted_memberships:
                old_position = moved_member.succession_position

                post_succession_update(
                    message_model=ModaBackNForthChat,
                    group_field="moda",
                    group=second_link,
                    message=(
                        f"Succession update: "
                        f"{user_display_name(moved_member.user)} moved "
                        f"from position {old_position} to position "
                        f"{old_position - 1} after "
                        f"{removed_name} was removed."
                    ),
                )
