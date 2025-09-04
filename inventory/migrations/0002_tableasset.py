from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0001_initial"),
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="TableAsset",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("condition", models.CharField(choices=[('excellent', 'Excellent'), ('good', 'Good'), ('fair', 'Fair'), ('needs_repair', 'Needs Repair'), ('out_of_service', 'Out of Service')], default="good", max_length=20)),
                ("last_maintenance", models.DateField(blank=True, null=True)),
                ("purchase_date", models.DateField(blank=True, null=True)),
                ("purchase_cost", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("table", models.OneToOneField(help_text="Canonical table this asset record describes", on_delete=django.db.models.deletion.CASCADE, related_name="asset", to="core.table")),
            ],
            options={
                "verbose_name": "Table Asset",
                "verbose_name_plural": "Table Assets",
            },
        ),
        migrations.AddIndex(
            model_name="tableasset",
            index=models.Index(fields=["condition"], name="inventory_t_condition_idx"),
        ),
        migrations.AddIndex(
            model_name="tableasset",
            index=models.Index(fields=["-created_at"], name="inventory_t_created_at_idx"),
        ),
    ]

