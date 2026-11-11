import os
import secrets
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from events.models import AgendaItem, Announcement, Event, EventCategory, Organization, Registration, Venue


class SeedDemoTests(TestCase):
    def setUp(self):
        self.password = secrets.token_urlsafe(24)
        self.output = StringIO()
        self.errors = StringIO()

    def seed(self, **options):
        call_command("seed_demo", stdout=self.output, stderr=self.errors, **options)

    @staticmethod
    def counts():
        models = (get_user_model(), Group, Organization, Venue, EventCategory, Event, AgendaItem, Registration, Announcement)
        return {model.__name__: model.objects.count() for model in models}

    @patch.dict(os.environ, {"CAMPUSGATHER_DEMO_PASSWORD": ""})
    def test_new_accounts_require_password_without_partial_data(self):
        with self.assertRaisesMessage(CommandError, "New demo users need a password"):
            self.seed()
        self.assertTrue(all(count == 0 for count in self.counts().values()))

    def test_weak_password_rejected_without_partial_data(self):
        with self.assertRaisesMessage(CommandError, "Demo password rejected"):
            self.seed(password="123")
        self.assertTrue(all(count == 0 for count in self.counts().values()))

    def test_repeat_preserves_counts_passwords_and_edited_data(self):
        self.seed(password=self.password)
        User = get_user_model()
        self.assertEqual(User.objects.count(), 3)
        self.assertEqual(Event.objects.count(), 5)
        self.assertEqual(Registration.objects.count(), 3)
        self.assertFalse(User.objects.filter(is_superuser=True).exists())
        user = User.objects.get(username="demo_organizer")
        self.assertTrue(user.groups.filter(name="Organizers").exists())
        encoded_password = user.password
        event = Event.objects.get(title="Demo: Campus Discovery Workshop")
        original_schedule = (event.starts_at, event.ends_at)
        event.description = "An organizer's retained edit."
        event.save(update_fields=["description"])
        registration = Registration.objects.filter(event=event).first()
        registration.attendance_note = "A student's retained edit."
        registration.save(update_fields=["attendance_note"])
        before = self.counts()

        # No password is needed when every demo account already exists.
        with patch.dict(os.environ, {"CAMPUSGATHER_DEMO_PASSWORD": ""}):
            self.seed()
        self.seed(password=secrets.token_urlsafe(24))
        self.assertEqual(before, self.counts())
        user.refresh_from_db()
        event.refresh_from_db()
        registration.refresh_from_db()
        self.assertEqual(user.password, encoded_password)
        self.assertTrue(user.check_password(self.password))
        self.assertEqual((event.starts_at, event.ends_at), original_schedule)
        self.assertEqual(event.description, "An organizer's retained edit.")
        self.assertEqual(registration.attendance_note, "A student's retained edit.")
        self.assertNotIn(self.password, self.output.getvalue() + self.errors.getvalue())
        self.assertNotEqual(encoded_password, self.password)

    def test_environment_password_and_existing_username_are_preserved(self):
        User = get_user_model()
        existing = User.objects.create_user("demo_organizer", password=self.password, first_name="Existing person")
        retained_password = existing.password
        unrelated = Organization.objects.create(owner=existing, name="A real existing group", description="Keep this")
        matching = Organization.objects.create(
            owner=existing, name="Demo: CampusGather Society", description="Existing matching name; keep this too",
        )
        with patch.dict(os.environ, {"CAMPUSGATHER_DEMO_PASSWORD": secrets.token_urlsafe(24)}):
            self.seed()
        existing.refresh_from_db()
        unrelated.refresh_from_db()
        matching.refresh_from_db()
        self.assertEqual(existing.password, retained_password)
        self.assertEqual(existing.first_name, "Existing person")
        self.assertFalse(existing.groups.filter(name="Organizers").exists())
        self.assertEqual(unrelated.description, "Keep this")
        self.assertEqual(matching.description, "Existing matching name; keep this too")
        self.assertEqual(Organization.objects.filter(owner=existing, name=matching.name).count(), 1)
        self.assertIn("Reused existing usernames", self.errors.getvalue())
        self.assertIn("has no organizer access", self.errors.getvalue())

    def test_existing_student_account_is_not_enrolled_by_seed(self):
        existing = get_user_model().objects.create_user("demo_student", password=self.password)
        self.seed(password=self.password)
        self.assertFalse(Registration.objects.filter(student=existing).exists())
        self.assertEqual(Registration.objects.filter(student__username="demo_student2").count(), 1)

    def test_seed_does_not_recreate_cancelled_demo_registrations(self):
        self.seed(password=self.password)
        Registration.objects.filter(student__username="demo_student").delete()
        before = Registration.objects.count()
        self.seed()
        self.assertEqual(Registration.objects.count(), before)
