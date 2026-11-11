from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.middleware.csrf import get_token
from django.test import RequestFactory, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from events.models import (
    AgendaItem, Announcement, Event, EventCategory, Organization, Registration, Venue,
)
from events.services import TemporarilyBusy


class ApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.organizer = users.objects.create_user("api-organizer", password="test-password")
        cls.other_organizer = users.objects.create_user("api-other-organizer", password="test-password")
        group = Group.objects.get_or_create(name="Organizers")[0]
        cls.organizer.groups.add(group)
        cls.other_organizer.groups.add(group)
        cls.student = users.objects.create_user("api-student", password="test-password")
        cls.other_student = users.objects.create_user("api-other-student", password="test-password")
        cls.admin = users.objects.create_superuser("api-admin", "admin@example.test", "test-password")
        cls.start = timezone.now() + timedelta(days=3)
        cls.organization = Organization.objects.create(
            owner=cls.organizer, name="API club", contact_email="private@example.test"
        )
        cls.venue = Venue.objects.create(
            owner=cls.organizer, name="API hall", address="Campus", latitude=9.7, longitude=118.7
        )
        cls.category = EventCategory.objects.create(owner=cls.organizer, name="API category")
        cls.other_organization = Organization.objects.create(owner=cls.other_organizer, name="Other club")
        cls.other_venue = Venue.objects.create(
            owner=cls.other_organizer, name="Other hall", address="Campus", latitude=9.8, longitude=118.8
        )
        cls.other_category = EventCategory.objects.create(owner=cls.other_organizer, name="Other category")
        cls.event = Event.objects.create(
            organization=cls.organization, venue=cls.venue, category=cls.category,
            title="Public event", description="Meet together", starts_at=cls.start,
            ends_at=cls.start + timedelta(hours=4), status=Event.Status.PUBLISHED,
        )
        cls.draft = Event.objects.create(
            organization=cls.organization, venue=cls.venue, category=cls.category,
            title="Private draft", description="Not public", starts_at=cls.start,
            ends_at=cls.start + timedelta(hours=4), status=Event.Status.DRAFT,
        )
        cls.other_event = Event.objects.create(
            organization=cls.other_organization, venue=cls.other_venue, category=cls.other_category,
            title="Other public event", description="Other organizer", starts_at=cls.start,
            ends_at=cls.start + timedelta(hours=4), status=Event.Status.PUBLISHED,
        )
        cls.draft_agenda = AgendaItem.objects.create(
            event=cls.draft, title="Private agenda", starts_at=cls.start,
            ends_at=cls.start + timedelta(hours=1),
        )
        cls.draft_announcement = Announcement.objects.create(event=cls.draft, title="Private news", body="Draft")

    def setUp(self):
        self.client = APIClient()

    def login_as(self, user):
        self.client.force_authenticate(user=user)

    def rows(self, response):
        self.assertEqual(response.status_code, 200, response.data)
        return response.data["results"] if isinstance(response.data, dict) and "results" in response.data else response.data

    def event_payload(self, **changes):
        data = {
            "organization": self.organization.pk, "venue": self.venue.pk, "category": self.category.pk,
            "title": "New event", "description": "Details", "starts_at": self.start.isoformat(),
            "ends_at": (self.start + timedelta(hours=3)).isoformat(), "status": "draft",
        }
        data.update(changes)
        return data

    def test_all_seven_resources_support_authorized_crud(self):
        cases = [
            ("organizations", {"name": "New club", "description": "Club", "contact_email": "club@example.test"}, {"name": "Edited club"}),
            ("venues", {"name": "New hall", "address": "Campus", "latitude": 10.2, "longitude": 119.2}, {"address": "East campus"}),
            ("categories", {"name": "New category", "description": "Category"}, {"name": "Edited category"}),
            ("events", self.event_payload(), {"title": "Edited event"}),
            ("agenda-items", {"event": self.event.pk, "title": "Talk", "starts_at": self.start.isoformat(), "ends_at": (self.start + timedelta(hours=1)).isoformat()}, {"title": "Edited talk"}),
            ("announcements", {"event": self.event.pk, "title": "News", "body": "Welcome"}, {"body": "Updated news"}),
            ("registrations", {"event": self.event.pk, "attendance_note": "Joining"}, {"attendance_note": "Arriving early"}),
        ]
        for resource, payload, changes in cases:
            with self.subTest(resource=resource):
                self.login_as(self.student if resource == "registrations" else self.organizer)
                collection = f"/api/{resource}/"
                created = self.client.post(collection, payload, format="json")
                self.assertEqual(created.status_code, 201, created.data)
                detail = f"{collection}{created.data['id']}/"
                self.assertIn(created.data["id"], [row["id"] for row in self.rows(self.client.get(collection))])
                self.assertEqual(self.client.get(detail).status_code, 200)
                changed = self.client.patch(detail, changes, format="json")
                self.assertEqual(changed.status_code, 200, changed.data)
                for key, value in changes.items():
                    self.assertEqual(changed.data[key], value)
                self.assertEqual(self.client.delete(detail).status_code, 204)
                self.assertEqual(self.client.get(detail).status_code, 404)

    def test_public_catalogs_hide_contact_email_and_owner(self):
        for resource in ("organizations", "venues", "categories"):
            rows = self.rows(self.client.get(f"/api/{resource}/"))
            self.assertTrue(rows)
            for row in rows:
                self.assertNotIn("owner", row)
                self.assertNotIn("contact_email", row)
        detail = f"/api/organizations/{self.organization.pk}/"
        self.assertNotIn("contact_email", self.client.get(detail).data)
        self.login_as(self.other_organizer)
        self.assertNotIn("contact_email", self.client.get(detail).data)
        for user in (self.organizer, self.admin):
            self.login_as(user)
            self.assertEqual(self.client.get(detail).data["contact_email"], "private@example.test")

    def test_drafts_and_their_children_are_scoped_on_list_and_detail(self):
        resources = (("events", self.draft), ("agenda-items", self.draft_agenda), ("announcements", self.draft_announcement))
        for user in (None, self.student, self.other_organizer):
            self.login_as(user)
            for resource, obj in resources:
                self.assertNotIn(obj.pk, [row["id"] for row in self.rows(self.client.get(f"/api/{resource}/"))])
                self.assertEqual(self.client.get(f"/api/{resource}/{obj.pk}/").status_code, 404)
        for user in (self.organizer, self.admin):
            self.login_as(user)
            for resource, obj in resources:
                self.assertEqual(self.client.get(f"/api/{resource}/{obj.pk}/").status_code, 200)

    def test_anonymous_writes_and_student_catalog_writes_are_forbidden(self):
        for resource in ("organizations", "venues", "categories", "events", "agenda-items", "registrations", "announcements"):
            self.assertEqual(self.client.post(f"/api/{resource}/", {}, format="json").status_code, 403)
        self.login_as(self.student)
        self.assertEqual(self.client.post("/api/organizations/", {"name": "Forged"}, format="json").status_code, 403)

    def test_cross_organizer_writes_and_relation_spoofing_are_rejected(self):
        self.login_as(self.other_organizer)
        for resource, obj in (("organizations", self.organization), ("venues", self.venue), ("categories", self.category), ("events", self.event), ("agenda-items", self.draft_agenda), ("announcements", self.draft_announcement)):
            response = self.client.patch(f"/api/{resource}/{obj.pk}/", {"title": "Stolen", "name": "Stolen"}, format="json")
            self.assertEqual(response.status_code, 404, response.data)
            self.assertEqual(self.client.delete(f"/api/{resource}/{obj.pk}/").status_code, 404)
        self.login_as(self.organizer)
        response = self.client.post("/api/events/", self.event_payload(organization=self.other_organization.pk), format="json")
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("organization", response.data)
        for field, value in (("venue", self.other_venue.pk), ("category", self.other_category.pk)):
            response = self.client.post("/api/events/", self.event_payload(**{field: value}), format="json")
            self.assertEqual(response.status_code, 400, response.data)
            self.assertIn(field, response.data)
        for resource, payload in (("agenda-items", {"event": self.other_event.pk, "title": "Bad", "starts_at": self.start.isoformat(), "ends_at": (self.start + timedelta(hours=1)).isoformat()}), ("announcements", {"event": self.other_event.pk, "title": "Bad", "body": "Bad"})):
            self.assertEqual(self.client.post(f"/api/{resource}/", payload, format="json").status_code, 400)

    def test_admin_relation_choices_preserve_the_records_organizer(self):
        self.login_as(self.admin)
        response = self.client.patch(f"/api/events/{self.event.pk}/", {"venue": self.other_venue.pk}, format="json")
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("venue", response.data)
        response = self.client.patch(f"/api/events/{self.event.pk}/", {"title": "Admin edit"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.event.refresh_from_db()
        self.assertEqual(self.event.organization_id, self.organization.pk)

    def test_owner_assignment_is_controlled_and_immutable(self):
        self.login_as(self.organizer)
        response = self.client.post("/api/organizations/", {"name": "Forged", "owner": self.other_organizer.pk}, format="json")
        self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(Organization.objects.filter(name="Forged").exists())
        self.login_as(self.admin)
        response = self.client.post("/api/organizations/", {"name": "Assigned", "owner": self.other_organizer.pk}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        assigned = Organization.objects.get(pk=response.data["id"])
        self.assertEqual(assigned.owner_id, self.other_organizer.pk)
        response = self.client.post("/api/organizations/", {"name": "Student owned", "owner": self.student.pk}, format="json")
        self.assertEqual(response.status_code, 400, response.data)
        response = self.client.patch(f"/api/organizations/{assigned.pk}/", {"owner": self.organizer.pk}, format="json")
        self.assertEqual(response.status_code, 400, response.data)
        assigned.refresh_from_db()
        self.assertEqual(assigned.owner_id, self.other_organizer.pk)

    def test_immutable_parent_and_read_only_identity_conflicts_are_rejected(self):
        self.login_as(self.organizer)
        for resource, obj, data in (
            ("events", self.event, {"organization": self.other_organization.pk}),
            ("agenda-items", self.draft_agenda, {"event": self.event.pk}),
            ("announcements", self.draft_announcement, {"event": self.event.pk}),
            ("events", self.event, {"id": self.other_event.pk}),
        ):
            response = self.client.patch(f"/api/{resource}/{obj.pk}/", data, format="json")
            self.assertEqual(response.status_code, 400, response.data)
        self.login_as(self.student)
        response = self.client.post("/api/registrations/", {"event": self.event.pk, "student": self.other_student.pk}, format="json")
        self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(Registration.objects.exists())
        created = self.client.post("/api/registrations/", {"event": self.event.pk}, format="json")
        detail = f"/api/registrations/{created.data['id']}/"
        for data in ({"event": self.other_event.pk}, {"student": self.other_student.pk}, {"created_at": "2000-01-01T00:00:00Z"}):
            self.assertEqual(self.client.patch(detail, data, format="json").status_code, 400)

    def test_registration_lists_details_and_roster_writes_respect_privacy(self):
        own = Registration.objects.create(event=self.other_event, student=self.student, attendance_note="Mine")
        roster = Registration.objects.create(event=self.event, student=self.other_student, attendance_note="Private")
        hidden = Registration.objects.create(event=self.other_event, student=self.other_student, attendance_note="Other roster")
        organizer_own = Registration.objects.create(event=self.other_event, student=self.organizer)
        self.assertEqual(self.client.get("/api/registrations/").status_code, 403)
        self.login_as(self.student)
        self.assertEqual([row["id"] for row in self.rows(self.client.get("/api/registrations/"))], [own.pk])
        self.assertEqual(self.client.get(f"/api/registrations/{roster.pk}/").status_code, 404)
        self.login_as(self.organizer)
        self.assertEqual({row["id"] for row in self.rows(self.client.get("/api/registrations/"))}, {roster.pk, organizer_own.pk})
        self.assertEqual(self.client.get(f"/api/registrations/{hidden.pk}/").status_code, 404)
        self.assertEqual(self.client.patch(f"/api/registrations/{roster.pk}/", {"attendance_note": "No"}, format="json").status_code, 403)
        self.assertEqual(self.client.delete(f"/api/registrations/{roster.pk}/").status_code, 403)
        self.login_as(self.admin)
        self.assertEqual({row["id"] for row in self.rows(self.client.get("/api/registrations/"))}, {own.pk, roster.pk, hidden.pk, organizer_own.pk})
        self.assertEqual(self.client.patch(f"/api/registrations/{roster.pk}/", {"attendance_note": "Admin note"}, format="json").status_code, 200)
        self.assertEqual(self.client.delete(f"/api/registrations/{hidden.pk}/").status_code, 204)

    def test_registration_create_always_assigns_the_acting_user_and_rejects_duplicates(self):
        for user, event in ((self.student, self.event), (self.organizer, self.event), (self.admin, self.other_event)):
            self.login_as(user)
            response = self.client.post("/api/registrations/", {"event": event.pk}, format="json")
            self.assertEqual(response.status_code, 201, response.data)
            self.assertEqual(response.data["student"], user.pk)
            duplicate = self.client.post("/api/registrations/", {"event": event.pk}, format="json")
            self.assertEqual(duplicate.status_code, 400, duplicate.data)
            self.assertEqual(Registration.objects.filter(event=event, student=user).count(), 1)

    def test_cancelled_and_started_events_close_registration_and_notes_but_allow_delete(self):
        registration = Registration.objects.create(event=self.event, student=self.student)
        self.login_as(self.organizer)
        cancelled = self.client.patch(f"/api/events/{self.event.pk}/", {"status": "cancelled"}, format="json")
        self.assertEqual(cancelled.status_code, 200, cancelled.data)
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(f"/api/events/{self.event.pk}/").status_code, 200)
        self.login_as(self.student)
        self.assertEqual(self.client.patch(f"/api/registrations/{registration.pk}/", {"attendance_note": "Late"}, format="json").status_code, 400)
        self.assertEqual(self.client.get(f"/api/registrations/{registration.pk}/").status_code, 200)
        self.assertEqual(self.client.delete(f"/api/registrations/{registration.pk}/").status_code, 204)
        for user in (self.student, self.admin):
            self.login_as(user)
            for event in (self.event, self.draft):
                self.assertEqual(self.client.post("/api/registrations/", {"event": event.pk}, format="json").status_code, 400)
        self.other_event.starts_at = timezone.now() - timedelta(hours=2)
        self.other_event.ends_at = timezone.now() - timedelta(hours=1)
        self.other_event.save()
        late = Registration.objects.create(event=self.other_event, student=self.student)
        self.login_as(self.admin)
        self.assertEqual(self.client.post("/api/registrations/", {"event": self.other_event.pk}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(f"/api/registrations/{late.pk}/", {"attendance_note": "Late admin edit"}, format="json").status_code, 400)
        self.assertEqual(self.client.delete(f"/api/registrations/{late.pk}/").status_code, 204)

    def test_registration_note_length_is_limited(self):
        self.login_as(self.student)
        response = self.client.post("/api/registrations/", {"event": self.event.pk, "attendance_note": "a" * 301}, format="json")
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("attendance_note", response.data)

    def test_patch_validates_merged_dates_agenda_bounds_and_coordinates(self):
        self.login_as(self.organizer)
        response = self.client.patch(f"/api/events/{self.event.pk}/", {"ends_at": self.start.isoformat()}, format="json")
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("ends_at", response.data)
        response = self.client.patch(f"/api/agenda-items/{self.draft_agenda.pk}/", {"starts_at": (self.start - timedelta(minutes=1)).isoformat()}, format="json")
        self.assertEqual(response.status_code, 400, response.data)
        response = self.client.patch(f"/api/events/{self.draft.pk}/", {"starts_at": (self.start + timedelta(minutes=1)).isoformat()}, format="json")
        self.assertEqual(response.status_code, 400, response.data)
        for field, value in (("latitude", 91), ("latitude", "NaN"), ("longitude", 181), ("longitude", "Infinity")):
            response = self.client.patch(f"/api/venues/{self.venue.pk}/", {field: value}, format="json")
            self.assertEqual(response.status_code, 400, response.data)
            self.assertIn(field, response.data)
        self.event.refresh_from_db()
        self.assertEqual(self.event.ends_at, self.start + timedelta(hours=4))

    def test_put_requires_complete_fields_while_patch_keeps_existing_values(self):
        self.login_as(self.organizer)
        detail = f"/api/events/{self.event.pk}/"
        self.assertEqual(self.client.put(detail, {"title": "Incomplete"}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(detail, {"title": "Partial"}, format="json").status_code, 200)
        response = self.client.put(detail, self.event_payload(title="Full replacement", status="published"), format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.event.refresh_from_db()
        self.assertEqual(self.event.organization_id, self.organization.pk)

    def test_published_cannot_become_draft_and_cancelled_is_terminal(self):
        self.login_as(self.organizer)
        detail = f"/api/events/{self.event.pk}/"
        self.assertEqual(self.client.patch(detail, {"status": "draft"}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(detail, {"status": "cancelled"}, format="json").status_code, 200)
        self.assertEqual(self.client.patch(detail, {"status": "published"}, format="json").status_code, 400)

    def test_protected_deletes_return_conflict_without_deleting_records(self):
        self.login_as(self.organizer)
        for resource, obj in (("organizations", self.organization), ("venues", self.venue), ("categories", self.category)):
            response = self.client.delete(f"/api/{resource}/{obj.pk}/")
            self.assertEqual(response.status_code, 409, response.data)
            self.assertIn("detail", response.data)
            self.assertTrue(type(obj).objects.filter(pk=obj.pk).exists())
        Registration.objects.create(event=self.event, student=self.student)
        response = self.client.delete(f"/api/events/{self.event.pk}/")
        self.assertEqual(response.status_code, 409, response.data)
        self.assertTrue(Event.objects.filter(pk=self.event.pk).exists())

    def test_event_delete_cascades_agenda_and_announcements(self):
        self.login_as(self.organizer)
        self.assertEqual(self.client.delete(f"/api/events/{self.draft.pk}/").status_code, 204)
        self.assertFalse(AgendaItem.objects.filter(pk=self.draft_agenda.pk).exists())
        self.assertFalse(Announcement.objects.filter(pk=self.draft_announcement.pk).exists())

    def test_temporary_write_lock_returns_json_retry_response(self):
        self.login_as(self.organizer)
        with patch("events.api.serializers.save_record", side_effect=TemporarilyBusy("Please try again.")):
            response = self.client.post("/api/categories/", {"name": "New category"}, format="json")
        self.assertEqual(response.status_code, 503, response.data)
        self.assertIn("try again", str(response.data["detail"]))

    def test_real_session_authentication_requires_csrf_for_writes(self):
        client = APIClient(enforce_csrf_checks=True)
        self.assertTrue(client.login(username="api-organizer", password="test-password"))
        denied = client.post("/api/categories/", {"name": "Without token"}, format="json")
        self.assertEqual(denied.status_code, 403, denied.data)
        self.assertIn("CSRF", str(denied.data["detail"]))
        request = RequestFactory().get("/")
        token = get_token(request)
        client.cookies[settings.CSRF_COOKIE_NAME] = request.META["CSRF_COOKIE"]
        allowed = client.post("/api/categories/", {"name": "With token"}, format="json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(allowed.status_code, 201, allowed.data)

    def test_browsable_api_remains_available(self):
        response = self.client.get("/api/events/", HTTP_ACCEPT="text/html")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("text/html"))

    def test_browsable_form_body_csrf_works_without_accepting_unknown_json_fields(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.organizer)
        client.get("/api/organizations/", HTTP_ACCEPT="text/html")
        token = client.cookies[settings.CSRF_COOKIE_NAME].value
        response = client.post("/api/organizations/", {"name": "Browsable form club", "csrfmiddlewaretoken": token}, format="multipart", HTTP_ACCEPT="text/html")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(Organization.objects.filter(name="Browsable form club", owner=self.organizer).exists())
        self.assertEqual(client.post("/api/organizations/", {"name": "No token"}, format="multipart").status_code, 403)
        unknown_json = client.post("/api/organizations/", {"name": "Unknown JSON", "csrfmiddlewaretoken": token}, format="json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(unknown_json.status_code, 400)

    def test_api_event_creation_starts_in_draft_then_can_publish(self):
        self.login_as(self.organizer)
        for state in ["published", "cancelled"]:
            response = self.client.post("/api/events/", self.event_payload(status=state), format="json")
            self.assertEqual(response.status_code, 400, response.data)
        draft = self.client.post("/api/events/", self.event_payload(), format="json")
        self.assertEqual(draft.status_code, 201, draft.data)
        published = self.client.patch(f"/api/events/{draft.data['id']}/", {"status": "published"}, format="json")
        self.assertEqual(published.status_code, 200, published.data)
