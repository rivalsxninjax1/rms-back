from django.apps import AppConfig


class LoyaltyConfig(AppConfig):
    """
    Canonical Loyalty app using package path 'loyalty' but preserving the
    historical app label 'loyality' so existing DB tables remain unchanged.
    """

    # Django loads models from this module path
    name = "loyalty"
    # Keep the historical label so db_table/app_label stay stable
    label = "loyality"
    verbose_name = "Loyalty"
