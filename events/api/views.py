from django.core.exceptions import ValidationError as ModelValidationError
from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.permissions import SAFE_METHODS

from events.models import AgendaItem, Announcement, Event, EventCategory, Organization, Registration, Venue
from events.permissions import is_admin, is_organizer, managed_events, visible_events
from events.services import ProtectedDeletion, TemporarilyBusy, delete_record
from .permissions import OrganizerWrites, RegistrationAccess
from .serializers import (
    AgendaItemSerializer, AnnouncementSerializer, EventCategorySerializer, EventSerializer,
    OrganizationSerializer, RegistrationSerializer, VenueSerializer,
)


class Conflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "protected_deletion"


class TemporarilyUnavailable(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_code = "temporarily_busy"


class ResourceViewSet(viewsets.ModelViewSet):
    authentication_classes = (SessionAuthentication,)
    permission_classes = (OrganizerWrites,)

    def handle_exception(self, exc):
        if isinstance(exc, ModelValidationError):
            detail = exc.message_dict if hasattr(exc, "message_dict") else {"non_field_errors": exc.messages}
            if "__all__" in detail:
                detail["non_field_errors"] = detail.pop("__all__")
            exc = ValidationError(detail)
        elif isinstance(exc, ProtectedDeletion):
            exc = Conflict(str(exc))
        elif isinstance(exc, TemporarilyBusy):
            exc = TemporarilyUnavailable(str(exc))
        return super().handle_exception(exc)

    def perform_destroy(self, instance):
        delete_record(self.request.user, instance)


class OwnedViewSet(ResourceViewSet):
    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.method in SAFE_METHODS or is_admin(self.request.user):
            return queryset
        return queryset.filter(owner=self.request.user)


class OrganizationViewSet(OwnedViewSet):
    queryset = Organization.objects.select_related("owner")
    serializer_class = OrganizationSerializer


class VenueViewSet(OwnedViewSet):
    queryset = Venue.objects.select_related("owner")
    serializer_class = VenueSerializer


class EventCategoryViewSet(OwnedViewSet):
    queryset = EventCategory.objects.select_related("owner")
    serializer_class = EventCategorySerializer


class EventViewSet(ResourceViewSet):
    serializer_class = EventSerializer

    def get_queryset(self):
        queryset = Event.objects.select_related("organization__owner", "venue", "category")
        if self.request.method in SAFE_METHODS:
            return visible_events(self.request.user, queryset)
        return queryset.filter(pk__in=managed_events(self.request.user))


class EventChildViewSet(ResourceViewSet):
    def get_queryset(self):
        events = visible_events(self.request.user) if self.request.method in SAFE_METHODS else managed_events(self.request.user)
        return super().get_queryset().filter(event__in=events)


class AgendaItemViewSet(EventChildViewSet):
    queryset = AgendaItem.objects.select_related("event__organization__owner")
    serializer_class = AgendaItemSerializer


class AnnouncementViewSet(EventChildViewSet):
    queryset = Announcement.objects.select_related("event__organization__owner")
    serializer_class = AnnouncementSerializer


class RegistrationViewSet(ResourceViewSet):
    serializer_class = RegistrationSerializer
    permission_classes = (RegistrationAccess,)

    def get_queryset(self):
        queryset = Registration.objects.select_related("student", "event__organization__owner")
        user = self.request.user
        if is_admin(user):
            return queryset
        if not user.is_authenticated:
            return queryset.none()
        permitted = Q(student=user)
        if is_organizer(user):
            permitted |= Q(event__organization__owner=user)
        return queryset.filter(permitted)
