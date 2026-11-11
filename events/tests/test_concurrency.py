"""Exercise real competing SQLite writes, including its explicit retry outcome."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import close_old_connections
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from events.models import AgendaItem, Event, EventCategory, Organization, Registration, Venue
from events.services import TemporarilyBusy, save_record

@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ConcurrentWriteTests(TransactionTestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user("organizer")
        self.owner.groups.add(Group.objects.create(name="Organizers"))
        self.student = get_user_model().objects.create_user("student")
        org = Organization.objects.create(name="Club", owner=self.owner)
        venue = Venue.objects.create(name="Hall", address="Campus", latitude=10, longitude=119, owner=self.owner)
        category = EventCategory.objects.create(name="Workshop", owner=self.owner)
        self.start = timezone.now() + timedelta(days=2)
        self.event = Event.objects.create(organization=org, venue=venue, category=category, title="Workshop", description="Learn", starts_at=self.start, ends_at=self.start + timedelta(hours=3), status="published")

    def race(self, operations):
        barrier = Barrier(len(operations))
        def run(operation):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                operation()
                return "saved"
            except ValidationError:
                return "invalid"
            except TemporarilyBusy:
                return "busy"
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=len(operations)) as pool:
            return list(pool.map(run, operations))

    def test_simultaneous_registrations_do_not_duplicate_or_crash(self):
        def register():
            save_record(self.student, Registration, {"event": self.event})
        results = self.race([register, register])
        self.assertIn("saved", results)
        self.assertEqual(Registration.objects.filter(event=self.event, student=self.student).count(), 1)

    def test_registration_and_cancellation_leave_consistent_state(self):
        self.race([lambda: save_record(self.student, Registration, {"event": self.event}), lambda: save_record(self.owner, Event, {"status": "cancelled"}, self.event)])
        # Retry a busy cancellation after the competing write has ended.
        save_record(self.owner, Event, {"status": "cancelled"}, self.event)
        with self.assertRaises(ValidationError):
            save_record(self.student, Registration, {"event": self.event})
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, "cancelled")
        self.assertLessEqual(Registration.objects.count(), 1)

    def test_agenda_creation_and_reschedule_cannot_strand_agenda(self):
        results = self.race([lambda: save_record(self.owner, AgendaItem, {"event": self.event, "title": "Talk", "starts_at": self.start, "ends_at": self.start + timedelta(hours=1)}), lambda: save_record(self.owner, Event, {"starts_at": self.start + timedelta(hours=2)}, self.event)])
        self.assertIn("saved", results)
        self.event.refresh_from_db()
        items = list(AgendaItem.objects.filter(event=self.event))
        if not items:
            self.assertEqual(self.event.starts_at, self.start + timedelta(hours=2))
        for item in items:
            self.assertEqual(self.event.starts_at, self.start)
            self.assertGreaterEqual(item.starts_at, self.event.starts_at)
            self.assertLessEqual(item.ends_at, self.event.ends_at)

    def test_both_agenda_and_reschedule_orderings_preserve_bounds(self):
        item_data = {"event": self.event, "title": "Talk", "starts_at": self.start, "ends_at": self.start + timedelta(hours=1)}
        item = save_record(self.owner, AgendaItem, item_data)
        with self.assertRaises(ValidationError):
            save_record(self.owner, Event, {"starts_at": self.start + timedelta(hours=2)}, self.event)
        item.refresh_from_db()
        self.event.refresh_from_db()
        self.assertGreaterEqual(item.starts_at, self.event.starts_at)
        item.delete()
        save_record(self.owner, Event, {"starts_at": self.start + timedelta(hours=2)}, self.event)
        with self.assertRaises(ValidationError):
            save_record(self.owner, AgendaItem, item_data)
        self.assertEqual(AgendaItem.objects.count(), 0)
