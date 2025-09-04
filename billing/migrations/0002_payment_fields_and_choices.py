from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='payment',
            name='method',
            field=models.CharField(choices=[('stripe', 'Stripe'), ('cash', 'Cash'), ('pos_card', 'POS Card')], default='stripe', max_length=16),
        ),
        migrations.AddField(
            model_name='payment',
            name='status',
            field=models.CharField(choices=[('created', 'Created'), ('authorized', 'Authorized'), ('captured', 'Captured'), ('failed', 'Failed'), ('refunded', 'Refunded')], default='created', max_length=16),
        ),
        migrations.AlterField(
            model_name='payment',
            name='currency',
            field=models.CharField(default='USD', max_length=8),
        ),
        migrations.AddField(
            model_name='payment',
            name='external_ref',
            field=models.CharField(blank=True, max_length=128, null=True),
        ),
        migrations.AddField(
            model_name='payment',
            name='notes',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='payment',
            name='created_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name='created_payments', to=settings.AUTH_USER_MODEL),
        ),
    ]

