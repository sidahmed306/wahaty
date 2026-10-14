import factory

from accounts.models import AccountStatus, Role, User

DEFAULT_PASSWORD = "Oasis-Adrar-2026"


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    phone = factory.Sequence(lambda n: f"+2222{n:07d}")
    full_name = factory.Faker("name", locale="fr_FR")
    roles = factory.LazyFunction(lambda: [Role.FARMER])
    status = AccountStatus.APPROVED
    password = factory.django.Password(DEFAULT_PASSWORD)
