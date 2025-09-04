from django.db import migrations, models
import django.db.models.deletion


def forward_link_core_table(apps, schema_editor):
    InvTable = apps.get_model("inventory", "Table")
    CoreTable = apps.get_model("core", "Table")
    for inv in InvTable.objects.all().iterator():
        core = CoreTable.objects.filter(location=inv.location, table_number=inv.table_number).first()
        if not core:
            core = CoreTable.objects.create(
                location=inv.location,
                table_number=inv.table_number,
                capacity=inv.capacity,
                is_active=inv.is_active,
                table_type="dining",
            )
        inv.core_table_id = core.id
        inv.save(update_fields=["core_table"])


def reverse_unlink_core_table(apps, schema_editor):
    InvTable = apps.get_model("inventory", "Table")
    InvTable.objects.update(core_table=None)


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0002_tableasset"),
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="table",
            name="core_table",
            field=models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.CASCADE, related_name="inventory_aliases", to="core.table"),
        ),
        migrations.RunPython(forward_link_core_table, reverse_unlink_core_table),
    ]

