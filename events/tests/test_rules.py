from datetime import timedelta
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone
from events.models import Organization, Venue, EventCategory, Event, AgendaItem, Registration
from events.services import save_record

class RuleTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user("organizer", password="test-password")
        self.owner.groups.add(Group.objects.get_or_create(name="Organizers")[0])
        self.student = User.objects.create_user("student", password="test-password")
        self.org = Organization.objects.create(name="Club", owner=self.owner)
        self.venue = Venue.objects.create(name="Hall", address="Campus", latitude=9.7, longitude=118.7, owner=self.owner)
        self.category = EventCategory.objects.create(name="Workshop", owner=self.owner)
        self.start = timezone.now() + timedelta(days=2)
        self.event = Event.objects.create(organization=self.org, venue=self.venue, category=self.category, title="Workshop", description="Learn together", starts_at=self.start, ends_at=self.start + timedelta(hours=3), status="published")

    def test_student_cannot_create_owned_resources(self):
        with self.assertRaises(PermissionDenied):
            save_record(self.student, Organization, {"name": "Hijack"})

    def test_duplicate_registration_is_validation_error(self):
        save_record(self.student, Registration, {"event": self.event})
        with self.assertRaises(ValidationError):
            save_record(self.student, Registration, {"event": self.event})
        self.assertEqual(Registration.objects.count(), 1)

    def test_cancelled_event_disallows_new_registration(self):
        save_record(self.owner, Event, {"status": "cancelled"}, self.event)
        with self.assertRaises(ValidationError):
            save_record(self.student, Registration, {"event": self.event})

    def test_cannot_move_event_away_from_agenda(self):
        AgendaItem.objects.create(event=self.event, title="Talk", starts_at=self.start, ends_at=self.start + timedelta(hours=1))
        with self.assertRaises(ValidationError):
            save_record(self.owner, Event, {"starts_at": self.start + timedelta(minutes=30)}, self.event)

    def test_nonfinite_coordinates_rejected(self):
        for value in [float("nan"), float("inf"), 91]:
            self.venue.latitude = value
            with self.assertRaises(ValidationError):
                self.venue.full_clean()

    def test_new_event_must_be_draft_before_publish_or_cancel(self):
        data = {"organization": self.org, "venue": self.venue, "category": self.category, "title": "New event", "description": "New description", "starts_at": self.start, "ends_at": self.start + timedelta(hours=1)}
        for state in ["published", "cancelled"]:
            with self.assertRaises(ValidationError):
                save_record(self.owner, Event, {**data, "status": state})
        event = save_record(self.owner, Event, data)
        self.assertEqual(event.status, "draft")
        event = save_record(self.owner, Event, {"status": "published"}, event)
        self.assertEqual(event.status, "published")
