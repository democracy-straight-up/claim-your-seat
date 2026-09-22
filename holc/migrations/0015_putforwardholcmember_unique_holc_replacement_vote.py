from django.db import migrations, models


def remove_duplicate_holc_replacement_votes(apps, schema_editor):
    PutForwardHolcMember = apps.get_model(
        "holc",
        "PutForwardHolcMember",
    )

    duplicate_groups = (
        PutForwardHolcMember.objects.values(
            "voter_id",
            "candidate_id",
            "holc_id",
        )
        .annotate(row_count=models.Count("id"))
        .filter(row_count__gt=1)
    )

    for group in duplicate_groups.iterator():
        duplicate_ids = list(
            PutForwardHolcMember.objects.filter(
                voter_id=group["voter_id"],
                candidate_id=group["candidate_id"],
                holc_id=group["holc_id"],
            )
            .order_by("voted_at", "id")
            .values_list("id", flat=True)
        )

        PutForwardHolcMember.objects.filter(
            id__in=duplicate_ids[1:]
        ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("holc", "0014_caucusexpulsionvote_and_more"),
    ]

    operations = [
        migrations.RunPython(
            remove_duplicate_holc_replacement_votes,
            migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name="putforwardholcmember",
            constraint=models.UniqueConstraint(
                fields=("voter", "candidate", "holc"),
                name="unique_holc_replacement_vote",
            ),
        ),
    ]