from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0002_add_source_order_fk"),
        ("orders", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="stripepaymentintent",
            name="order_ref",
            field=models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL, related_name="stripe_intents", to="orders.order"),
        ),
    ]

