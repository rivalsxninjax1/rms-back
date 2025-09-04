from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reservations", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="reservation",
            name="deposit_amount",
            field=models.DecimalField(default=0, decimal_places=2, max_digits=10, help_text="Required deposit for this reservation"),
        ),
        migrations.AddField(
            model_name="reservation",
            name="deposit_paid",
            field=models.BooleanField(default=False, help_text="Whether deposit has been paid"),
        ),
        migrations.AddField(
            model_name="reservation",
            name="deposit_applied",
            field=models.BooleanField(default=False, help_text="Whether deposit credit has been applied to final bill"),
        ),
        migrations.AddIndex(
            model_name="reservation",
            index=models.Index(fields=["created_by", "status"], name="reservation_created_by_status_idx"),
        ),
    ]
