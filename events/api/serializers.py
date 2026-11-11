from collections.abc import Mapping

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers
from rest_framework.utils.html import is_html_input

from events.models import (
    AgendaItem, Announcement, Event, EventCategory, Organization, Registration, Venue,
)
from events.permissions import is_admin, is_organizer, managed_events
from events.services import save_record


class ResourceSerializer(serializers.ModelSerializer):
    def to_internal_value(self, data):
        if not isinstance(data, Mapping):
            return super().to_internal_value(data)
        unknown = set(data) - set(self.fields)
        if is_html_input(data):
            # SessionAuthentication has already checked this transport field.
            unknown.discard("csrfmiddlewaretoken")
        if unknown:
            raise serializers.ValidationError({name: "This field is not accepted." for name in sorted(unknown)})
        return super().to_internal_value(data)

    def validate(self, attrs):
        # DRF ignores read-only input by default. Reject conflicting identities explicitly.
        errors = {}
        for name, field in self.fields.items():
            if not field.read_only or name not in self.initial_data:
                continue
            if self.instance is not None:
                expected = field.to_representation(field.get_attribute(self.instance))
            elif self.Meta.model is Registration and name == "student":
                expected = self.context["request"].user.pk
            else:
                errors[name] = "This field is set by the server."
                continue
            if str(self.initial_data[name]) != str(expected):
                errors[name] = "This field cannot be changed."
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def create(self, validated_data):
        return save_record(self.context["request"].user, self.Meta.model, validated_data)

    def update(self, instance, validated_data):
        return save_record(self.context["request"].user, self.Meta.model, validated_data, instance=instance)


class OwnedSerializer(ResourceSerializer):
    owner = serializers.PrimaryKeyRelatedField(queryset=get_user_model().objects.none(), required=False, write_only=True)

    def get_fields(self):
        fields = super().get_fields()
        user = self.context["request"].user
        if isinstance(self.instance, self.Meta.model):
            owners = get_user_model().objects.filter(pk=self.instance.owner_id)
        elif is_admin(user):
            owners = get_user_model().objects.filter(Q(is_superuser=True) | Q(groups__name="Organizers")).distinct()
        else:
            owners = get_user_model().objects.filter(pk=user.pk) if is_organizer(user) else get_user_model().objects.none()
        fields["owner"].queryset = owners
        return fields


class OrganizationSerializer(OwnedSerializer):
    class Meta:
        model = Organization
        fields = ("id", "owner", "name", "description", "contact_email")

    def to_representation(self, instance):
        data = super().to_representation(instance)
        user = self.context["request"].user
        if not (is_admin(user) or (user.is_authenticated and instance.owner_id == user.pk)):
            data.pop("contact_email")
        return data


class VenueSerializer(OwnedSerializer):
    class Meta:
        model = Venue
        fields = ("id", "owner", "name", "address", "latitude", "longitude")


class EventCategorySerializer(OwnedSerializer):
    class Meta:
        model = EventCategory
        fields = ("id", "owner", "name", "description")


class EventSerializer(ResourceSerializer):
    class Meta:
        model = Event
        fields = ("id", "organization", "venue", "category", "title", "description", "starts_at", "ends_at", "status")

    def get_fields(self):
        fields = super().get_fields()
        user = self.context["request"].user
        if self.instance is None:
            fields["status"].choices = [(Event.Status.DRAFT, "Draft")]
        for name, model in (("organization", Organization), ("venue", Venue), ("category", EventCategory)):
            choices = model.objects.all()
            if isinstance(self.instance, Event):
                choices = choices.filter(owner_id=self.instance.organization.owner_id)
                if name == "organization":
                    choices = choices.filter(pk=self.instance.organization_id)
            elif not is_admin(user):
                choices = choices.filter(owner=user) if is_organizer(user) else choices.none()
            fields[name].queryset = choices
        return fields


class EventChildSerializer(ResourceSerializer):
    def get_fields(self):
        fields = super().get_fields()
        if isinstance(self.instance, self.Meta.model):
            fields["event"].queryset = Event.objects.filter(pk=self.instance.event_id)
        else:
            fields["event"].queryset = managed_events(self.context["request"].user)
        return fields


class AgendaItemSerializer(EventChildSerializer):
    class Meta:
        model = AgendaItem
        fields = ("id", "event", "title", "description", "starts_at", "ends_at")


class RegistrationSerializer(ResourceSerializer):
    student = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Registration
        fields = ("id", "event", "student", "attendance_note", "created_at")
        read_only_fields = ("created_at",)
        # The shared service validates uniqueness with the server-assigned student.
        validators = []

    def get_fields(self):
        fields = super().get_fields()
        if isinstance(self.instance, Registration):
            fields["event"].queryset = Event.objects.filter(pk=self.instance.event_id)
        else:
            fields["event"].queryset = Event.objects.filter(status=Event.Status.PUBLISHED, starts_at__gt=timezone.now())
        return fields


class AnnouncementSerializer(EventChildSerializer):
    class Meta:
        model = Announcement
        fields = ("id", "event", "title", "body", "created_at")
        read_only_fields = ("created_at",)
