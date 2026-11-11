from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from events.models import Organization, Venue, EventCategory, Event, AgendaItem, Registration, Announcement
from events.services import ProtectedDeletion, delete_record, save_record

FAST_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

@override_settings(PASSWORD_HASHERS=FAST_HASHERS)
class WebsiteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.owner = User.objects.create_user("organizer", password="test-password")
        cls.other = User.objects.create_user("other", password="test-password")
        cls.student = User.objects.create_user("student", password="test-password")
        cls.admin = User.objects.create_superuser("admin", "admin@example.invalid", "test-password")
        group = Group.objects.create(name="Organizers")
        cls.owner.groups.add(group)
        cls.other.groups.add(group)
        cls.org = Organization.objects.create(name="Club", description="Campus club", owner=cls.owner)
        cls.venue = Venue.objects.create(name="Hall", address="Campus", latitude=9.7, longitude=118.7, owner=cls.owner)
        cls.category = EventCategory.objects.create(name="Workshop", owner=cls.owner)
        cls.start = timezone.now().replace(second=0, microsecond=0) + timedelta(days=2)
        cls.event = Event.objects.create(organization=cls.org, venue=cls.venue, category=cls.category, title="Workshop", description="Learn together", starts_at=cls.start, ends_at=cls.start + timedelta(hours=3), status="published")

    def local_input(self, dt):
        return timezone.localtime(dt).strftime("%Y-%m-%dT%H:%M")

    def test_all_six_organizer_crud_interfaces(self):
        self.client.force_login(self.owner)
        cases = [
            ("organizations", Organization, {"name": "New club", "description": "Description", "contact_email": "club@example.invalid"}, "name"),
            ("venues", Venue, {"name": "New venue", "address": "Campus", "latitude": "9.75", "longitude": "118.75"}, "name"),
            ("categories", EventCategory, {"name": "New category", "description": "Category description"}, "name"),
            ("events", Event, {"title": "New event", "description": "Event description", "organization": self.org.pk, "venue": self.venue.pk, "category": self.category.pk, "starts_at": self.local_input(self.start), "ends_at": self.local_input(self.start + timedelta(hours=2)), "status": "draft"}, "title"),
            ("agenda-items", AgendaItem, {"event": self.event.pk, "title": "New agenda", "description": "Agenda description", "starts_at": self.local_input(self.start), "ends_at": self.local_input(self.start + timedelta(hours=1))}, "title"),
            ("announcements", Announcement, {"event": self.event.pk, "title": "New announcement", "body": "Bring a notebook."}, "title"),
        ]
        for resource, model, payload, name in cases:
            with self.subTest(resource=resource):
                self.assertEqual(self.client.get(reverse("resource-list", args=[resource])).status_code, 200)
                self.assertEqual(self.client.get(reverse("resource-create", args=[resource])).status_code, 200)
                response = self.client.post(reverse("resource-create", args=[resource]), payload)
                self.assertEqual(response.status_code, 302, response.context and response.context["form"].errors)
                obj = model.objects.get(**{name: payload[name]})
                self.assertEqual(self.client.get(reverse("resource-detail", args=[resource, obj.pk])).status_code, 200)
                self.assertEqual(self.client.get(reverse("resource-update", args=[resource, obj.pk])).status_code, 200)
                payload[name] += " updated"
                self.assertEqual(self.client.post(reverse("resource-update", args=[resource, obj.pk]), payload).status_code, 302)
                obj.refresh_from_db()
                self.assertEqual(getattr(obj, name), payload[name])
                self.assertEqual(self.client.get(reverse("resource-delete", args=[resource, obj.pk])).status_code, 200)
                self.assertTrue(model.objects.filter(pk=obj.pk).exists())
                self.assertEqual(self.client.post(reverse("resource-delete", args=[resource, obj.pk])).status_code, 302)
                self.assertFalse(model.objects.filter(pk=obj.pk).exists())

    def test_registration_crud_and_note(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse("registration-create", args=[self.event.pk])).status_code, 200)
        response = self.client.post(reverse("registration-create", args=[self.event.pk]), {"attendance_note": "Wheelchair access, please."})
        self.assertEqual(response.status_code, 302)
        obj = Registration.objects.get(student=self.student)
        for route in ["registration-list", "registration-detail", "registration-edit", "registration-delete"]:
            args = [] if route == "registration-list" else [obj.pk]
            self.assertEqual(self.client.get(reverse(route, args=args)).status_code, 200)
        self.assertEqual(self.client.post(reverse("registration-edit", args=[obj.pk]), {"attendance_note": "Arriving early."}).status_code, 302)
        obj.refresh_from_db()
        self.assertEqual(obj.attendance_note, "Arriving early.")
        self.assertEqual(self.client.post(reverse("registration-create", args=[self.event.pk])).status_code, 302)
        self.assertEqual(Registration.objects.count(), 1)
        self.assertEqual(self.client.post(reverse("registration-delete", args=[obj.pk])).status_code, 302)
        self.assertEqual(Registration.objects.count(), 0)

    def test_student_registration_privacy_and_roster_permissions(self):
        registration = Registration.objects.create(event=self.event, student=self.student, attendance_note="Private note")
        self.client.force_login(self.other)
        for route in ["registration-detail", "registration-edit", "registration-delete"]:
            self.assertEqual(self.client.get(reverse(route, args=[registration.pk])).status_code, 404)
        self.assertNotContains(self.client.get(reverse("registration-list")), "Private note")
        self.assertEqual(self.client.get(reverse("roster", args=[self.event.pk])).status_code, 404)
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(reverse("roster", args=[self.event.pk])), "Private note")
        self.assertEqual(self.client.post(reverse("registration-edit", args=[registration.pk]), {"attendance_note": "Hijack"}).status_code, 404)
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 403)
        self.assertEqual(self.client.get(reverse("admin-registration-list")).status_code, 403)

    def test_organizer_ownership_and_spoofed_identity(self):
        self.client.force_login(self.other)
        for route in ["resource-detail", "resource-update", "resource-delete"]:
            self.assertEqual(self.client.get(reverse(route, args=["organizations", self.org.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("resource-create", args=["organizations"]), {"name": "My club", "owner": self.owner.pk}).status_code, 302)
        self.assertEqual(Organization.objects.get(name="My club").owner, self.other)
        payload = {"title": "Hijack", "description": "Denied", "organization": self.org.pk, "venue": self.venue.pk, "category": self.category.pk, "starts_at": self.local_input(self.start), "ends_at": self.local_input(self.start + timedelta(hours=1)), "status": "published"}
        response = self.client.post(reverse("resource-create", args=["events"]), payload)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Event.objects.filter(title="Hijack").exists())

    @patch("events.weather.forecast_for_event", return_value={"available": False, "message": "Weather unavailable"})
    def test_public_pages_search_category_and_draft_hidden(self, forecast):
        draft = Event.objects.create(organization=self.org, venue=self.venue, category=self.category, title="Private draft", description="Hidden", starts_at=self.start, ends_at=self.start + timedelta(hours=2))
        Announcement.objects.create(event=draft, title="Secret draft announcement", body="Secret")
        self.assertContains(self.client.get(reverse("event-list")), self.event.title)
        self.assertNotContains(self.client.get(reverse("event-list")), "Private draft")
        empty_search = self.client.get(reverse("event-list"), {"q": "nomatch"})
        self.assertEqual(list(empty_search.context["events"]), [])
        self.assertContains(empty_search, "No events match your search")
        self.assertContains(self.client.get(reverse("event-list"), {"category": self.category.pk}), self.event.title)
        self.assertEqual(self.client.get(reverse("event-detail", args=[draft.pk])).status_code, 404)
        response = self.client.get(reverse("event-detail", args=[self.event.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Weather unavailable")
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(reverse("event-detail", args=[draft.pk])), "Private draft")

    def test_dates_agenda_coords_and_delete_protection(self):
        self.event.ends_at = self.event.starts_at
        with self.assertRaises(ValidationError):
            self.event.full_clean()
        self.event.refresh_from_db()
        with self.assertRaises(ValidationError):
            save_record(self.owner, AgendaItem, {"event": self.event, "title": "Outside", "starts_at": self.start - timedelta(hours=1), "ends_at": self.start})
        with self.assertRaises(ValidationError):
            save_record(self.owner, Venue, {"name": "Invalid", "address": "Here", "latitude": 91, "longitude": 181})
        with self.assertRaises(ProtectedDeletion):
            delete_record(self.owner, self.venue)
        Registration.objects.create(event=self.event, student=self.student)
        with self.assertRaises(ProtectedDeletion):
            delete_record(self.owner, self.event)
        self.assertTrue(Event.objects.filter(pk=self.event.pk).exists())
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(reverse("resource-delete", args=["events", self.event.pk])).status_code, 409)

    def test_malformed_category_filter_does_not_crash(self):
        for value in ["²", "x", "9" * 100]:
            with self.subTest(value=value):
                response = self.client.get(reverse("event-list"), {"category": value})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(list(response.context["events"]), [])

    def test_admin_management_and_role_changes(self):
        registration = Registration.objects.create(event=self.event, student=self.student)
        self.client.force_login(self.admin)
        for route in ["dashboard", "roles", "admin-registration-list"]:
            self.assertEqual(self.client.get(reverse(route)).status_code, 200)
        self.assertEqual(self.client.get(reverse("admin-registration-detail", args=[registration.pk])).status_code, 200)
        self.assertEqual(self.client.post(reverse("admin-registration-edit", args=[registration.pk]), {"attendance_note": "Admin updated note"}).status_code, 302)
        self.event.status = "cancelled"
        self.event.save()
        response = self.client.post(reverse("admin-registration-edit", args=[registration.pk]), {"attendance_note": "Closed"})
        self.assertEqual(response.status_code, 200)
        registration.refresh_from_db()
        self.assertEqual(registration.attendance_note, "Admin updated note")
        self.assertEqual(self.client.post(reverse("roles"), {"user_id": self.student.pk, "action": "grant"}).status_code, 302)
        self.assertTrue(self.student.groups.filter(name="Organizers").exists())
        self.client.post(reverse("roles"), {"user_id": self.student.pk, "action": "revoke"})
        self.assertFalse(self.student.groups.exists())
        self.assertEqual(self.client.post(reverse("admin-registration-delete", args=[registration.pk])).status_code, 302)

    def test_registration_closed_state_and_database_unique_constraint(self):
        Registration.objects.create(event=self.event, student=self.student)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Registration.objects.create(event=self.event, student=self.student)
        save_record(self.owner, Event, {"status": "cancelled"}, self.event)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("registration-create", args=[self.event.pk])).status_code, 200)
        self.client.post(reverse("registration-create", args=[self.event.pk]), {"attendance_note": "Too late"})
        self.assertEqual(Registration.objects.count(), 1)
        with self.assertRaises(ValidationError):
            save_record(self.owner, Event, {"status": "published"}, self.event)
        self.client.force_login(self.student)
        registration = Registration.objects.get()
        self.assertEqual(self.client.post(reverse("registration-delete", args=[registration.pk])).status_code, 302)

    def test_child_cascade_delete_and_foreign_owner_validation(self):
        child = AgendaItem.objects.create(event=self.event, title="Talk", starts_at=self.start, ends_at=self.start + timedelta(hours=1))
        announcement = Announcement.objects.create(event=self.event, title="Notice", body="Hello")
        foreign = Venue.objects.create(owner=self.other, name="Foreign", address="Other campus", latitude=10, longitude=119)
        with self.assertRaises(ValidationError):
            save_record(self.owner, Event, {"venue": foreign}, self.event)
        delete_record(self.owner, self.event)
        self.assertFalse(AgendaItem.objects.filter(pk=child.pk).exists())
        self.assertFalse(Announcement.objects.filter(pk=announcement.pk).exists())
