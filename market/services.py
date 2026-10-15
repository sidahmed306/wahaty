"""Cycle d'une annonce :

brouillon ──envoyer──▶ en attente ──Direction : publier──▶ publiée ──vendue──▶ vendue
    ▲                       │                                 │
    │                       └──Direction : refuser──▶ refusée ─┘(modifier puis renvoyer)
    └────────────── retirer (publiée → brouillon) ◀───────────┘

Le public ne voit que les annonces publiées (Q12 : validation obligatoire).
"""

from django.db import transaction
from django.utils import timezone

from orders.models import Notification

from .models import MAX_PHOTOS, Listing, ListingPhoto, ListingStatus


class ListingError(Exception):
    pass


def _require(listing, *statuses):
    if listing.status not in statuses:
        raise ListingError(
            f"Action impossible : l'annonce est « {ListingStatus(listing.status).label} »."
        )


def _set(listing, status, **fields):
    listing.status = status
    for name, value in fields.items():
        setattr(listing, name, value)
    listing.save()
    return listing


@transaction.atomic
def submit(listing):
    listing = Listing.objects.select_for_update().get(pk=listing.pk)
    _require(listing, ListingStatus.DRAFT, ListingStatus.REJECTED)
    return _set(listing, ListingStatus.PENDING, rejection_reason="")


@transaction.atomic
def approve(listing, reviewer):
    listing = Listing.objects.select_for_update().get(pk=listing.pk)
    _require(listing, ListingStatus.PENDING)
    listing = _set(
        listing, ListingStatus.PUBLISHED, published_at=timezone.now(), reviewed_by=reviewer
    )
    Notification.objects.create(
        user=listing.owner,
        kind=Notification.Kind.LISTING_PUBLISHED,
        message_fr=f"Votre annonce « {listing.title} » est publiée sur le marché.",
        message_ar=f"تم نشر إعلانكم « {listing.title} » في السوق.",
    )
    return listing


@transaction.atomic
def reject(listing, reviewer, reason):
    listing = Listing.objects.select_for_update().get(pk=listing.pk)
    _require(listing, ListingStatus.PENDING)
    if not reason.strip():
        raise ListingError("Indiquez le motif du refus.")
    listing = _set(listing, ListingStatus.REJECTED, rejection_reason=reason, reviewed_by=reviewer)
    Notification.objects.create(
        user=listing.owner,
        kind=Notification.Kind.LISTING_REJECTED,
        message_fr=f"Votre annonce « {listing.title} » est refusée : {reason}",
        message_ar=f"تم رفض إعلانكم « {listing.title} »: {reason}",
    )
    return listing


@transaction.atomic
def unpublish(listing):
    listing = Listing.objects.select_for_update().get(pk=listing.pk)
    _require(listing, ListingStatus.PUBLISHED, ListingStatus.PENDING)
    return _set(listing, ListingStatus.DRAFT, published_at=None)


@transaction.atomic
def mark_sold(listing):
    listing = Listing.objects.select_for_update().get(pk=listing.pk)
    _require(listing, ListingStatus.PUBLISHED)
    return _set(listing, ListingStatus.SOLD)


@transaction.atomic
def add_photo(listing, image, order=0):
    listing = Listing.objects.select_for_update().get(pk=listing.pk)
    if not listing.is_editable:
        raise ListingError("Les photos se changent seulement en brouillon ou après un refus.")
    if listing.photos.count() >= MAX_PHOTOS:
        raise ListingError(f"{MAX_PHOTOS} photos maximum par annonce.")
    return ListingPhoto.objects.create(listing=listing, image=image, order=order)


def remove_photo(photo):
    if not photo.listing.is_editable:
        raise ListingError("Les photos se changent seulement en brouillon ou après un refus.")
    photo.image.delete(save=False)
    photo.delete()
