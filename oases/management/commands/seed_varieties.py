"""Crée (ou met à jour) les variétés de dattes du flyer TRC, avec leur photo.

    python manage.py seed_varieties            # textes + photos manquantes
    python manage.py seed_varieties --photos   # remplace aussi les photos existantes

Les photos de سلمدينة، الحمر et بجيره sont de vraies photos TRC (17 octobre 2026).

Peut être relancée sans risque : une variété déjà présente (même nom arabe) est mise à jour.
Les mois de maturité sont une première estimation (saison de la guetna) à corriger dans
l'administration si besoin ; les produits transformés sont disponibles toute l'année.
"""

from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand
from django.db import transaction

from oases.models import DateVariety

SEED_DIR = Path(__file__).resolve().parents[2] / "seed"
GUETNA = (6, 8)
ALL_YEAR = (1, 12)

VARIETIES = [
    {
        "slug": "salmedina",
        "name_ar": "سلمدينة",
        "name_fr": "Salmedina",
        "months": GUETNA,
        "description_ar": (
            "من أجود أنواع التمور، تتميز بمذاق فريد وشهير بين الناس انها تقول : "
            '"سَلّملي ألا أعلّ إِلّي ما يَعرفني. أمَا ليَ يَعرفني دور يجيني"'
        ),
        "description_fr": (
            "L'une des meilleures dattes, au goût unique et réputé. Le dicton lui fait dire : "
            "« Seul celui qui ne me connaît pas me néglige ; "
            "celui qui me connaît revient vers moi »."
        ),
    },
    {
        "slug": "hmar",
        "name_ar": "الحمر",
        "name_fr": "Hmar",
        "months": GUETNA,
        "description_ar": (
            "نخلة فخمة المذاق، يفضلها كبار السن لقيمتها العالية، لونها أحمر في البلح "
            "ويتحول إلى السواد عند النضج."
        ),
        "description_fr": (
            "Datte au goût riche, appréciée des anciens pour sa grande valeur. Rouge avant "
            "maturité, elle devient presque noire une fois mûre."
        ),
    },
    {
        "slug": "sekani",
        "name_ar": "سكاني",
        "name_fr": "Sekani",
        "months": GUETNA,
        "description_ar": (
            "نخلة سكاني – صفراء بمذاق ملكي. تمر سكاني بلونه الذهبي المشرق ونكهته الفريدة "
            "يجسّد توازنًا رائعًا بين الحلاوة والليونة. خيار فاخر يعبّر عن الأصالة "
            "ويمنح ضيافتك لمسة ملكية."
        ),
        "description_fr": (
            "Datte jaune au goût royal. Sa couleur dorée et sa saveur unique allient douceur "
            "et moelleux. Un choix raffiné qui donne à votre hospitalité une touche royale."
        ),
    },
    {
        "slug": "bjeira",
        "name_ar": "بجيره",
        "name_fr": "Bjeira",
        "months": GUETNA,
        "description_ar": (
            'بلون أصفر مميز، تُعرف ب"نخلة العيال الشناقطة"، كانت مؤونة الشتاء قديمًا، '
            "تمنح الدفء والطاقة."
        ),
        "description_fr": (
            "D'une couleur jaune particulière, on l'appelle « le palmier des enfants de "
            "Chinguetti ». Autrefois provision d'hiver, elle apporte chaleur et énergie."
        ),
    },
    {
        "slug": "sembekhra",
        "name_ar": "سمبخره",
        "name_fr": "Sembekhra",
        "months": GUETNA,
        "description_ar": "نخلة النشاط، تمرة تمد بالطاقة والحيوية، من أشهر تمور أهل الصحراء.",
        "description_fr": (
            "Le palmier de l'énergie : une datte qui donne force et vitalité, parmi les plus "
            "célèbres du désert."
        ),
    },
    {
        "slug": "anzar-kizkar",
        "name_ar": "أنزر (الكيزكار)",
        "name_fr": "Anzar (Kizkar)",
        "months": GUETNA,
        "description_ar": (
            "تمر قوي القوام، يمد بالطاقة والشبع، مثالي للمسافرين والعمال، وقود يومي لمن "
            "يعتمد على الطبيعة."
        ),
        "description_fr": (
            "Datte ferme et nourrissante, qui rassasie et donne de l'énergie : idéale pour "
            "les voyageurs et les travailleurs."
        ),
    },
    {
        "slug": "tmar-mfassas",
        "name_ar": "تمر المفصص",
        "name_fr": "Tmar mfassas",
        "months": ALL_YEAR,
        "texture": DateVariety.Texture.SOFT,
        "description_ar": "تمر لين ومنزوع النوى، جاهز للأكل مباشرة بطعمه الطبيعي الغني.",
        "description_fr": (
            "Dattes moelleuses et dénoyautées, prêtes à manger, au goût naturel et riche."
        ),
    },
    {
        "slug": "kousour-tmar",
        "name_ar": "كسور التمر",
        "name_fr": "Kousour tmar",
        "months": ALL_YEAR,
        "description_ar": (
            "كسور التمر على شكل سكرات، ممزوجة بدقيق الشعير المحمص، لمذاق مميز وطعم غني طبيعي."
        ),
        "description_fr": (
            "Bouchées de dattes en forme de boules, mélangées à de la farine d'orge grillée : "
            "un goût unique et naturel."
        ),
    },
    {
        "slug": "miel-de-dattes",
        "name_ar": "عسل التمر",
        "name_fr": "Miel de dattes",
        "months": ALL_YEAR,
        "description_ar": "سائل حلو مركّز يُستخلص من التمر، طبيعي ومغذٍّ، يُستخدم كمُحلٍّ بديل للسكر.",
        "description_fr": (
            "Sirop doux et concentré extrait des dattes, naturel et nourrissant, utilisé à la "
            "place du sucre."
        ),
    },
]


class Command(BaseCommand):
    help = "Crée ou met à jour les variétés de dattes TRC (textes ar/fr et photos)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--photos", action="store_true", help="Remplacer aussi les photos déjà présentes."
        )

    @transaction.atomic
    def handle(self, *args, photos=False, **options):
        created_count = 0
        for data in VARIETIES:
            start, end = data["months"]
            variety, created = DateVariety.objects.update_or_create(
                name_ar=data["name_ar"],
                defaults={
                    "name_fr": data["name_fr"],
                    "slug": data["slug"],
                    "description_ar": data["description_ar"],
                    "description_fr": data["description_fr"],
                    "texture": data.get("texture", ""),
                    "ripening_start_month": start,
                    "ripening_end_month": end,
                    "is_active": True,
                },
            )
            created_count += created
            missing = not variety.photo or not variety.photo.storage.exists(variety.photo.name)
            if photos or missing:
                path = SEED_DIR / f"{data['slug']}.webp"
                with path.open("rb") as handle:
                    variety.photo = File(handle, name=path.name)
                    variety.save()
            self.stdout.write(f"{'+' if created else '='} {data['name_fr']}")
        self.stdout.write(
            self.style.SUCCESS(f"{len(VARIETIES)} variétés prêtes ({created_count} nouvelles).")
        )
