from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reservations", "0003_rename_reservation_created_by_status_idx_reservation_created_54d651_idx"),
    ]

    operations = [
        migrations.AddField(
            model_name="reservation",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name="reservation",
            name="confirmation_number",
            field=models.CharField(blank=True, max_length=20, null=True, unique=True, help_text="Human-readable confirmation number"),
        ),
        migrations.AddField(
            model_name="reservation",
            name="guest_email",
            field=models.EmailField(blank=True, max_length=254, help_text="Guest email address (optional)"),
        ),
        migrations.AddField(
            model_name="reservation",
            name="seated_at",
            field=models.DateTimeField(blank=True, null=True, help_text="When party was seated"),
        ),
        migrations.AddField(
            model_name="reservation",
            name="completed_at",
            field=models.DateTimeField(blank=True, null=True, help_text="When reservation was completed"),
        ),
        migrations.AddField(
            model_name="reservation",
            name="cancelled_at",
            field=models.DateTimeField(blank=True, null=True, help_text="When reservation was cancelled"),
        ),
        migrations.AddField(
            model_name="reservation",
            name="special_requests",
            field=models.TextField(blank=True, default="", help_text="Special requests or notes"),
        ),
        migrations.AddField(
            model_name="reservation",
            name="internal_notes",
            field=models.TextField(blank=True, default="", help_text="Internal staff notes"),
        ),
    ]

