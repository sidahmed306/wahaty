"""Documentation Swagger : types des champs propres à TRC."""

from drf_spectacular.extensions import OpenApiSerializerFieldExtension
from drf_spectacular.plumbing import build_basic_type
from drf_spectacular.types import OpenApiTypes


class OwnRelatedFieldExtension(OpenApiSerializerFieldExtension):
    """Lien vers une de ses propres lignes : un identifiant entier."""

    target_class = "core.fields.OwnRelatedField"

    def map_serializer_field(self, auto_schema, direction):
        return build_basic_type(OpenApiTypes.INT)
