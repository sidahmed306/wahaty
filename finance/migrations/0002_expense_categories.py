"""Catégories de dépenses de départ (celles du schéma T02). La Direction peut en ajouter."""

from django.db import migrations

CATEGORIES = [
    # (nom arabe, nom français, pour qui, ordre)
    ("ماء وري", "Eau et irrigation", "farmer", 1),
    ("أسمدة", "Engrais", "farmer", 2),
    ("يد عاملة", "Main-d'œuvre", "both", 3),
    ("نقل", "Transport", "both", 4),
    ("تغليف", "Emballage", "both", 5),
    ("إيجار", "Loyer", "both", 6),
    ("أخرى", "Autre", "both", 99),
]


def create_categories(apps, schema_editor):
    ExpenseCategory = apps.get_model("finance", "ExpenseCategory")
    for name_ar, name_fr, applies_to, order in CATEGORIES:
        ExpenseCategory.objects.get_or_create(
            name_fr=name_fr,
            defaults={"name_ar": name_ar, "applies_to": applies_to, "order": order},
        )


def remove_categories(apps, schema_editor):
    ExpenseCategory = apps.get_model("finance", "ExpenseCategory")
    ExpenseCategory.objects.filter(
        name_fr__in=[c[1] for c in CATEGORIES], expenses__isnull=True
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("finance", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_categories, remove_categories),
    ]
