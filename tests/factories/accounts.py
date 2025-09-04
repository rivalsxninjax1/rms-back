import factory
from django.contrib.auth import get_user_model


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = get_user_model()
        django_get_or_create = ("username",)

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    is_active = True

    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        raw = extracted or "password123!"
        self.set_password(raw)
        if create:
            self.save(update_fields=["password"])

