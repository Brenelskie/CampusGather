"""The seven application tables; full_clean is called by the shared write service."""
import math
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

def latitude(value):
    if not math.isfinite(value) or not -90 <= value <= 90:
        raise ValidationError("Latitude must be a finite number between -90 and 90.")

def longitude(value):
    if not math.isfinite(value) or not -180 <= value <= 180:
        raise ValidationError("Longitude must be a finite number between -180 and 180.")

class Organization(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="organizations")
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, max_length=3000)
    contact_email = models.EmailField(blank=True)
    class Meta:
        ordering = ["name", "pk"]
    def __str__(self):
        return self.name

class Venue(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="venues")
    name = models.CharField(max_length=120)
    address = models.CharField(max_length=250)
    latitude = models.FloatField(validators=[latitude])
    longitude = models.FloatField(validators=[longitude])
    class Meta:
        ordering = ["name", "pk"]
        constraints = [models.CheckConstraint(condition=Q(latitude__gte=-90, latitude__lte=90), name="venue_latitude_range"), models.CheckConstraint(condition=Q(longitude__gte=-180, longitude__lte=180), name="venue_longitude_range")]
    def __str__(self):
        return self.name

class EventCategory(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="event_categories")
    name = models.CharField(max_length=80)
    description = models.CharField(max_length=250, blank=True)
    class Meta:
        ordering = ["name", "pk"]
        verbose_name_plural = "event categories"
    def __str__(self):
        return self.name

class Event(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        CANCELLED = "cancelled", "Cancelled"
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name="events")
    venue = models.ForeignKey(Venue, on_delete=models.PROTECT, related_name="events")
    category = models.ForeignKey(EventCategory, on_delete=models.PROTECT, related_name="events")
    title = models.CharField(max_length=160)
    description = models.TextField(max_length=6000)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    class Meta:
        ordering = ["starts_at", "pk"]
        constraints = [models.CheckConstraint(condition=Q(ends_at__gt=F("starts_at")), name="event_end_after_start")]
    def __str__(self):
        return self.title
    @property
    def registration_open(self):
        return self.status == self.Status.PUBLISHED and self.starts_at > timezone.now()
    def clean(self):
        errors = {}
        if not self.pk and self.status != self.Status.DRAFT:
            errors["status"] = "New events must start as drafts. Save the draft, then publish or cancel it."
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            errors["ends_at"] = "End time must be after start time."
        if self.organization_id and self.venue_id and self.category_id:
            owner = self.organization.owner_id
            if self.venue.owner_id != owner:
                errors["venue"] = "Choose a venue owned by the event's organizer."
            if self.category.owner_id != owner:
                errors["category"] = "Choose a category owned by the event's organizer."
        if self.pk:
            original = type(self).objects.get(pk=self.pk)
            if self.organization_id != original.organization_id:
                errors["organization"] = "An event's organization cannot be changed."
            allowed = {self.Status.DRAFT: {self.Status.DRAFT, self.Status.PUBLISHED, self.Status.CANCELLED}, self.Status.PUBLISHED: {self.Status.PUBLISHED, self.Status.CANCELLED}, self.Status.CANCELLED: {self.Status.CANCELLED}}
            if self.status not in allowed[original.status]:
                errors["status"] = "Published events can only be cancelled. Cancelled events cannot be reopened."
            if self.starts_at and self.ends_at and self.agenda_items.filter(Q(starts_at__lt=self.starts_at) | Q(ends_at__gt=self.ends_at)).exists():
                errors["starts_at"] = "Existing agenda items fall outside these times. Remove affected items before rescheduling."
        if errors:
            raise ValidationError(errors)

class AgendaItem(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="agenda_items")
    title = models.CharField(max_length=160)
    description = models.TextField(blank=True, max_length=2000)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    class Meta:
        ordering = ["starts_at", "pk"]
        constraints = [models.CheckConstraint(condition=Q(ends_at__gt=F("starts_at")), name="agenda_end_after_start")]
    def __str__(self):
        return self.title
    def clean(self):
        errors = {}
        if self.pk and self.event_id != type(self).objects.get(pk=self.pk).event_id:
            errors["event"] = "An agenda item's event cannot be changed."
        if self.starts_at and self.ends_at:
            if self.ends_at <= self.starts_at:
                errors["ends_at"] = "End time must be after start time."
            if self.event_id and (self.starts_at < self.event.starts_at or self.ends_at > self.event.ends_at):
                errors["starts_at"] = "Agenda times must be inside the event's start and end times."
        if errors:
            raise ValidationError(errors)

class Registration(models.Model):
    event = models.ForeignKey(Event, on_delete=models.PROTECT, related_name="registrations")
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="event_registrations")
    attendance_note = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [models.UniqueConstraint(fields=["event", "student"], name="one_registration_per_student_event")]
    def __str__(self):
        return f"{self.student} · {self.event}"
    def clean(self):
        errors = {}
        if self.pk:
            original = type(self).objects.get(pk=self.pk)
            if self.event_id != original.event_id:
                errors["event"] = "A registration's event cannot be changed."
            if self.student_id != original.student_id:
                errors["student"] = "A registration's student cannot be changed."
        if self.event_id and not self.event.registration_open:
            errors["__all__"] = "Registration and note changes are open only before a published event starts. You can still cancel."
        if errors:
            raise ValidationError(errors)

class Announcement(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="announcements")
    title = models.CharField(max_length=160)
    body = models.TextField(max_length=3000)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["-created_at", "-pk"]
    def __str__(self):
        return self.title
    def clean(self):
        if self.pk and self.event_id != type(self).objects.get(pk=self.pk).event_id:
            raise ValidationError({"event": "An announcement's event cannot be changed."})
