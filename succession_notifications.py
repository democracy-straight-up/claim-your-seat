from django.core.mail import send_mail
from django.db import transaction


def user_display_name(user):
    return user.users.legalName or user.username


def post_succession_update(
    *,
    message_model,
    group_field,
    group,
    message,
):
    message_model.objects.create(
        **{
            group_field: group,
            "sender": None,
            "is_system": True,
            "message": message,
        }
    )


def notify_delegate_change(
    *,
    message_model,
    group_field,
    group,
    group_name,
    delegate_title,
    outgoing_user,
    incoming_user,
    outgoing_position,
):
    outgoing_name = user_display_name(outgoing_user)
    incoming_name = user_display_name(incoming_user)

    post_succession_update(
        message_model=message_model,
        group_field=group_field,
        group=group,
        message=(
            f"Succession update: {incoming_name} became "
            f"{delegate_title}, replacing {outgoing_name}. "
            f"{outgoing_name} moved from position 0 to position "
            f"{outgoing_position}."
        ),
    )

    def send_delegate_emails():
        if outgoing_user.email:
            send_mail(
                subject=f"{group_name} delegate change",
                message=(
                    f"{incoming_name} has become {delegate_title}, "
                    f"replacing you. You are now at succession "
                    f"position {outgoing_position}."
                ),
                from_email=None,
                recipient_list=[outgoing_user.email],
                fail_silently=True,
            )

        if incoming_user.email:
            send_mail(
                subject=f"{group_name} delegate change",
                message=(
                    f"You are now {delegate_title}, replacing "
                    f"{outgoing_name}."
                ),
                from_email=None,
                recipient_list=[incoming_user.email],
                fail_silently=True,
            )

    transaction.on_commit(send_delegate_emails)

def notify_delegate_promotion_after_removal(
    *,
    message_model,
    group_field,
    group,
    group_name,
    delegate_title,
    outgoing_user,
    incoming_user,
    direct_removal=False,
):
    outgoing_name = user_display_name(outgoing_user)
    incoming_name = user_display_name(incoming_user)

    post_succession_update(
        message_model=message_model,
        group_field=group_field,
        group=group,
        message=(
            f"Succession update: {incoming_name} became "
            f"{delegate_title} after {outgoing_name} was removed. "
            f"{incoming_name} moved from position 1 to position 0."
        ),
    )

    def send_delegate_emails():
        if outgoing_user.email:
            send_mail(
                subject=f"{group_name} delegate change",
                message=(
                    (
                        f"You are no longer {delegate_title} because "
                        f"you were removed from {group_name}. "
                    )
                    if direct_removal
                    else (
                        f"You are no longer {delegate_title} because your "
                        f"membership in {group_name} ended after loss of "
                        f"the prerequisite delegate mandate. "
                    )
                ) + f"{incoming_name} is now {delegate_title}.",
                from_email=None,
                recipient_list=[outgoing_user.email],
                fail_silently=True,
            )

        if incoming_user.email:
            send_mail(
                subject=f"{group_name} delegate change",
                message=(
                    f"You are now {delegate_title} after "
                    f"{outgoing_name} was removed."
                ),
                from_email=None,
                recipient_list=[incoming_user.email],
                fail_silently=True,
            )

    transaction.on_commit(send_delegate_emails)

def notify_delegate_vacancy_after_removal(
    *,
    message_model,
    group_field,
    group,
    group_name,
    delegate_title,
    outgoing_user,
):
    outgoing_name = user_display_name(outgoing_user)

    post_succession_update(
        message_model=message_model,
        group_field=group_field,
        group=group,
        message=(
            f"Succession update: {delegate_title} position became "
            f"vacant after {outgoing_name} was removed; no accepted "
            f"successor is available."
        ),
    )

    def send_outgoing_delegate_email():
        if outgoing_user.email:
            send_mail(
                subject=f"{group_name} delegate change",
                message=(
                    f"You are no longer {delegate_title} because your "
                    f"membership in {group_name} ended after loss of "
                    f"the required lower-level delegate mandate. "
                    f"No accepted successor is currently available."
                ),
                from_email=None,
                recipient_list=[outgoing_user.email],
                fail_silently=True,
            )

    transaction.on_commit(send_outgoing_delegate_email)
