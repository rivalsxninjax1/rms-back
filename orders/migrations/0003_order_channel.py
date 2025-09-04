from django.db import migrations, models


def set_initial_channel(apps, schema_editor):
    Order = apps.get_model('orders', 'Order')
    db_alias = schema_editor.connection.alias
    # Set IN_HOUSE for dine-in orders, else ONLINE
    for o in Order.objects.using(db_alias).all().only('id', 'delivery_option'):
        chan = 'IN_HOUSE' if getattr(o, 'delivery_option', None) == 'DINE_IN' else 'ONLINE'
        Order.objects.using(db_alias).filter(id=o.id).update(channel=chan)


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0002_orderstatushistory'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='channel',
            field=models.CharField(choices=[('ONLINE', 'Online'), ('IN_HOUSE', 'In-house')], default='ONLINE', help_text='Sales channel (ONLINE vs IN_HOUSE)', max_length=16),
        ),
        migrations.RunPython(set_initial_channel, migrations.RunPython.noop),
    ]

