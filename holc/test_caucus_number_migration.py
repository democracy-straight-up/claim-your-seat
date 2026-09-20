from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class CaucusNumberMigrationTests(TransactionTestCase):
    migrate_from = [
        ("holc", "0011_caucus_number_sequence"),
    ]
    migrate_to = [
        ("holc", "0012_seed_caucus_number_sequences"),
    ]

    def setUp(self):
        super().setUp()
        self.addCleanup(self.restore_latest_migrations)

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state(self.migrate_from).apps

        District = old_apps.get_model("vote", "Districts")
        Caucus = old_apps.get_model("holc", "HolcModel")

        district = District.objects.create(
            name="Vermont At-Large",
            code="VT00",
        )
        self.district_id = district.pk

        # Historical models represent records present before the update.
        Caucus.objects.create(district_id=district.pk, code=3)
        Caucus.objects.create(district_id=district.pk, code=7)

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        self.apps = executor.loader.project_state(self.migrate_to).apps

    def restore_latest_migrations(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_migration_preserves_last_number_after_existing_caucus_deleted(self):
        Caucus = self.apps.get_model("holc", "HolcModel")
        Sequence = self.apps.get_model("holc", "CaucusNumberSequence")

        # Delete the largest existing number after migration.
        Caucus.objects.filter(
            district_id=self.district_id,
            code=7,
        ).delete()

        self.assertEqual(
            Sequence.objects.filter(
                district_id=self.district_id,
            ).count(),
            1,
            "The migration must initialize the district's numbering counter.",
        )

        sequence = Sequence.objects.get(district_id=self.district_id)
        self.assertEqual(sequence.last_issued, 7)