# This migration intentionally creates nothing. It only exists so that
# legacy migrations (e.g., reports.0002_user_tips_view) which declare
# a dependency on ('orders_extras', '0001_initial') can resolve cleanly.

from __future__ import annotations

from django.db import migrations


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = []
