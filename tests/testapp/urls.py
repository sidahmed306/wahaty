from rest_framework import serializers, viewsets
from rest_framework.routers import SimpleRouter

from config.urls import urlpatterns as project_urlpatterns
from core.mixins import OwnedQuerysetMixin

from .models import Note


class NoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Note
        fields = ["id", "owner", "text"]
        read_only_fields = ["owner"]


class NoteViewSet(OwnedQuerysetMixin, viewsets.ModelViewSet):
    queryset = Note.objects.order_by("id")
    serializer_class = NoteSerializer


router = SimpleRouter()
router.register("api/notes", NoteViewSet, basename="note")

urlpatterns = [*project_urlpatterns, *router.urls]
