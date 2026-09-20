from django.db import migrations
from django.db.models import Max


def seed_caucus_number_sequences(apps, schema_editor):
    Caucus = apps.get_model("holc", "HolcModel")
    Sequence = apps.get_model("holc", "CaucusNumberSequence")
    database = schema_editor.connection.alias

    district_numbers = (
        Caucus.objects.using(database)
        .values("district_id")
        .annotate(largest_code=Max("code"))
    )

    for row in district_numbers:
        last_issued = max(1, row["largest_code"])

        sequence, created = Sequence.objects.using(database).get_or_create(
            district_id=row["district_id"],
            defaults={"last_issued": last_issued},
        )

        # Preserve any counter that already remembers a larger number.
        if not created and sequence.last_issued < last_issued:
            sequence.last_issued = last_issued
            sequence.save(
                using=database,
                update_fields=["last_issued"],
            )


class Migration(migrations.Migration):
    dependencies = [
        ("holc", "0011_caucus_number_sequence"),
    ]

    operations = [
        migrations.RunPython(
            seed_caucus_number_sequences,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
