from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reports", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name='shiftreport',
            name='opened_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='shiftreport',
            name='closed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='shiftreport',
            name='cash_open_cents',
            field=models.IntegerField(default=0, help_text='Starting cash in drawer (¢)'),
        ),
        migrations.AddField(
            model_name='shiftreport',
            name='cash_close_cents',
            field=models.IntegerField(default=0, help_text='Ending cash in drawer (¢)'),
        ),
        migrations.AddField(
            model_name='shiftreport',
            name='cash_sales_cents',
            field=models.IntegerField(default=0, help_text='Cash sales total (¢) recorded by POS'),
        ),
        migrations.AddField(
            model_name='shiftreport',
            name='over_short_cents',
            field=models.IntegerField(default=0, help_text='Cash over/short (¢) = close - open - cash_sales'),
        ),
        migrations.AddField(
            model_name='shiftreport',
            name='notes',
            field=models.TextField(blank=True, default=''),
        ),
    ]

