"""Shared, short atomic writes used by both forms and REST endpoints."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, OperationalError, transaction
from django.db.models.deletion import ProtectedError
from django.http import Http404
from .models import Organization, Venue, EventCategory, Event, AgendaItem, Registration, Announcement
from .permissions import can_manage, is_admin, is_organizer

FIELDS = {
    Organization: ("name", "description", "contact_email"),
    Venue: ("name", "address", "latitude", "longitude"),
    EventCategory: ("name", "description"),
    Event: ("organization", "venue", "category", "title", "description", "starts_at", "ends_at", "status"),
    AgendaItem: ("event", "title", "description", "starts_at", "ends_at"),
    Registration: ("event", "attendance_note"),
    Announcement: ("event", "title", "body"),
}
OWNED_MODELS = (Organization, Venue, EventCategory)

class ProtectedDeletion(Exception):
    pass

class TemporarilyBusy(Exception):
    pass

def save_record(user, model, data, instance=None):
    try:
        with transaction.atomic():
            obj = model.objects.get(pk=instance.pk) if instance and instance.pk else model()
            creating = not obj.pk
            if model is Registration:
                if not user.is_authenticated or (not creating and not (is_admin(user) or obj.student_id == user.pk)):
                    raise PermissionDenied("You can change only your own registration.")
                if creating:
                    obj.student = user
            elif not is_organizer(user) or (not creating and not can_manage(user, obj)):
                raise PermissionDenied("Organizer access and ownership are required.")
            if model in OWNED_MODELS:
                if creating:
                    obj.owner = data.get("owner", user) if is_admin(user) else user
                    if not is_organizer(obj.owner):
                        raise ValidationError({"owner": "Choose an organizer or administrator."})
                elif "owner" in data and data["owner"].pk != obj.owner_id:
                    raise ValidationError({"owner": "Ownership cannot be changed."})
            for field in FIELDS[model]:
                if field in data:
                    setattr(obj, field, data[field])
            # Refresh related records inside the write lock; form/serializer objects may be stale.
            if isinstance(obj, (AgendaItem, Registration, Announcement)) and obj.event_id:
                obj.event = Event.objects.select_related("organization").get(pk=obj.event_id)
            if model is Event:
                for name, related_model in [("organization", Organization), ("venue", Venue), ("category", EventCategory)]:
                    if getattr(obj, name + "_id"):
                        setattr(obj, name, related_model.objects.get(pk=getattr(obj, name + "_id")))
            if model is not Registration and not can_manage(user, obj):
                raise PermissionDenied("You cannot manage this organizer's records.")
            obj.full_clean()
            obj.save()
            return obj
    except model.DoesNotExist as exc:
        raise Http404("This record no longer exists.") from exc
    except Event.DoesNotExist as exc:
        raise ValidationError({"event": "This event no longer exists."}) from exc
    except IntegrityError as exc:
        if model is Registration and "events_registration.event_id, events_registration.student_id" in str(exc):
            raise ValidationError({"event": "You are already registered for this event."}) from exc
        raise
    except OperationalError as exc:
        if "locked" in str(exc).lower():
            raise TemporarilyBusy("Another update is finishing. Please try again.") from exc
        raise

def delete_record(user, obj):
    try:
        with transaction.atomic():
            current = type(obj).objects.filter(pk=obj.pk).first()
            if current is None:
                return
            if isinstance(current, Registration):
                permitted = user.is_authenticated and (is_admin(user) or current.student_id == user.pk)
            else:
                permitted = can_manage(user, current)
            if not permitted:
                raise PermissionDenied("You cannot delete this record.")
            current.delete()
    except ProtectedError as exc:
        raise ProtectedDeletion("This record is in use. Remove its registrations or related events first; no data was deleted.") from exc
    except OperationalError as exc:
        if "locked" in str(exc).lower():
            raise TemporarilyBusy("Another update is finishing. Please try again.") from exc
        raise
