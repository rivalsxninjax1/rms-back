from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ("loyality", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='loyaltyrank',
            name='earn_points_per_currency',
            field=models.DecimalField(max_digits=8, decimal_places=2, default=1.00),
        ),
        migrations.AddField(
            model_name='loyaltyrank',
            name='burn_cents_per_point',
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name='loyaltyprofile',
            name='points',
            field=models.IntegerField(default=0),
        ),
        migrations.CreateModel(
            name='LoyaltyPointsLedger',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('delta', models.IntegerField(help_text='Points change (positive or negative)')),
                ('type', models.CharField(choices=[('EARN', 'Earn'), ('BURN', 'Burn'), ('ADJUST', 'Adjust')], default='EARN', max_length=8)),
                ('reason', models.CharField(blank=True, default='', max_length=200)),
                ('reference', models.CharField(blank=True, default='', help_text='Order ID or external reference', max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='loyalty_adjustments', to=settings.AUTH_USER_MODEL)),
                ('profile', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ledger', to='loyality.loyaltyprofile')),
            ],
            options={
                'ordering': ['-created_at', '-id'],
            },
        ),
    ]

