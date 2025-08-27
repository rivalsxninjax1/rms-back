# Generated custom initial migration that avoids re-creating existing through tables.
from __future__ import annotations

from django.db import migrations, models
import django.contrib.auth.models
import django.contrib.auth.validators
import django.utils.timezone
from django.conf import settings


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        # Create the custom accounts_user table (this should already exist; if it does, Django
        # will treat this as an initial migration with --fake-initial automatically).
        migrations.CreateModel(
            name="User",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("password", models.CharField(max_length=128, verbose_name="password")),
                ("last_login", models.DateTimeField(blank=True, null=True, verbose_name="last login")),
                (
                    "is_superuser",
                    models.BooleanField(
                        default=False,
                        help_text="Designates that this user has all permissions without explicitly assigning them.",
                        verbose_name="superuser status",
                    ),
                ),
                (
                    "username",
                    models.CharField(
                        error_messages={"unique": "A user with that username already exists."},
                        help_text="Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.",
                        max_length=150,
                        unique=True,
                        validators=[django.contrib.auth.validators.UnicodeUsernameValidator()],
                        verbose_name="username",
                    ),
                ),
                ("first_name", models.CharField(blank=True, max_length=150, verbose_name="first name")),
                ("last_name", models.CharField(blank=True, max_length=150, verbose_name="last name")),
                ("email", models.EmailField(blank=True, max_length=254, verbose_name="email address")),
                ("is_staff", models.BooleanField(default=False, help_text="Designates whether the user can log into this admin site.", verbose_name="staff status")),
                ("is_active", models.BooleanField(default=True, help_text="Designates whether this user should be treated as active.", verbose_name="active")),
                ("date_joined", models.DateTimeField(default=django.utils.timezone.now, verbose_name="date joined")),
            ],
            options={
                "verbose_name": "user",
                "verbose_name_plural": "users",
                "swappable": "AUTH_USER_MODEL",
            },
            managers=[("objects", django.contrib.auth.models.UserManager())],
        ),

        # --- IMPORTANT PART ---
        # Register the *through* models in Django's migration STATE, but do not apply any DB DDL.
        # This prevents "table already exists" when the tables are already present in the DB.
        migrations.SeparateDatabaseAndState(
            # No DB operations (we assume tables already exist)
            database_operations=[],
            # But we do add them to the project state so ORM knows about them.
            state_operations=[
                migrations.CreateModel(
                    name="User_groups",
                    fields=[
                        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                        (
                            "user",
                            models.ForeignKey(on_delete=models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
                        ),
                        (
                            "group",
                            models.ForeignKey(on_delete=models.deletion.CASCADE, to="auth.group"),
                        ),
                    ],
                    options={
                        "db_table": "accounts_user_groups",
                        "unique_together": {("user", "group")},
                    },
                ),
                migrations.CreateModel(
                    name="User_user_permissions",
                    fields=[
                        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                        (
                            "user",
                            models.ForeignKey(on_delete=models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
                        ),
                        (
                            "permission",
                            models.ForeignKey(on_delete=models.deletion.CASCADE, to="auth.permission"),
                        ),
                    ],
                    options={
                        "db_table": "accounts_user_user_permissions",
                        "unique_together": {("user", "permission")},
                    },
                ),

                # Now wire up the M2M relations on User to use those through tables.
                migrations.AddField(
                    model_name="user",
                    name="groups",
                    field=models.ManyToManyField(
                        blank=True,
                        help_text="The groups this user belongs to.",
                        related_name="user_set",
                        related_query_name="user",
                        to="auth.group",
                        verbose_name="groups",
                        through="accounts.User_groups",
                    ),
                ),
                migrations.AddField(
                    model_name="user",
                    name="user_permissions",
                    field=models.ManyToManyField(
                        blank=True,
                        help_text="Specific permissions for this user.",
                        related_name="user_set",
                        related_query_name="user",
                        to="auth.permission",
                        verbose_name="user permissions",
                        through="accounts.User_user_permissions",
                    ),
                ),
            ],
        ),

        # Standard auth constraints for superuser and permissions M2M
        migrations.AlterUniqueTogether(
            name="user_groups",
            unique_together={("user", "group")},
        ),
        migrations.AlterUniqueTogether(
            name="user_user_permissions",
            unique_together={("user", "permission")},
        ),
    ]
